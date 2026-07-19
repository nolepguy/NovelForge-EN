"""Inspiration assistant service

Provides LangChain-based tool invocation and streaming chat capabilities.
The React text-protocol mode shares its core implementation with the Workflow Agent.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from sqlmodel import Session

from app.schemas.ai import AssistantChatRequest
from app.services import llm_config_service
from app.services.ai.core.chat_model_factory import build_chat_model
from app.services.ai.core.quota_manager import precheck_quota, record_usage
from app.services.ai.core.react_text_agent import stream_chat_with_react_protocol
from app.services.ai.core.tool_agent_stream import stream_agent_with_tools
from app.services.ai.core.token_utils import calc_input_tokens, estimate_tokens
from .tools import (
    ASSISTANT_TOOL_DESCRIPTIONS,
    ASSISTANT_TOOL_REGISTRY,
    ASSISTANT_TOOLS,
    AssistantDeps,
    set_assistant_deps,
)


MAX_REACT_STEPS = 100


ASSISTANT_REACT_PROTOCOL_INSTRUCTIONS = """
You are in the writing-assistant React-Tool mode.

Tool-call format (strict):
<Action>{"tool":"tool_name","args":{"param_name":param_value}}</Action>

Execution rules:
1) You may only call tools from the "available tools list"; calling any wf_* tool is forbidden.
2) When the user asks to create/modify card content, you must do it through tools (e.g. create_card / update_card / modify_card_field / replace_field_text / propose_card_text_patches).
3) Output at most one Action block per round; the tool execution result is returned as an Observation, then decide the next step.
4) If parameters contain long text, you must output valid JSON (newlines and quotes must be escaped correctly).
5) Do not output pseudo-call text (e.g. tool(...)).
6) When the user asks for multiple reviewable body-text edit suggestions, you must call propose_card_text_patches; do not use update_card, modify_card_field, replace_field_text, or replace_card_text_by_lines to directly modify the body text.
7) Each patches item of propose_card_text_patches must include old_text and new_text; you may also provide start_line/end_line and context_before/context_after to help the frontend re-locate.
8) Multiple body-text suggestions must be returned as a single batch, letting the frontend display them one by one as "Suggestion #current / of N" for the user to accept or reject.
""".strip()


ASSISTANT_TEXT_PATCH_TOOL_INSTRUCTIONS = """
Body-text batch edit suggestion rules:
- When the user asks the inspiration assistant to propose body-text edits, especially multiple suggestions, per-item confirmation, or to reuse the right-click polish/expand preview mechanism, you must use propose_card_text_patches.
- propose_card_text_patches only submits suggestions to the current body editor for preview; it does not write to the database and does not directly modify the body text.
- Do not use update_card, modify_card_field, replace_field_text, or replace_card_text_by_lines for this kind of body-text suggestion.
- Each suggestion must include old_text and new_text; old_text should be an exact excerpt of the current body text where possible.
- It is recommended to also provide start_line/end_line and context_before/context_after so the user can re-locate after accepting suggestions, avoiding misalignment caused by earlier accepted suggestions.
""".strip()


_LANGUAGE_DIRECTIVE = "IMPORTANT: You must always respond and communicate in English only, regardless of the user's language or the model's default language."


def _with_assistant_tool_guidance(system_prompt: str) -> str:
    base = system_prompt or ""
    if _LANGUAGE_DIRECTIVE not in base:
        base = _LANGUAGE_DIRECTIVE + "\n\n" + base
    if ASSISTANT_TEXT_PATCH_TOOL_INSTRUCTIONS in base:
        return base
    return base + "\n\n" + ASSISTANT_TEXT_PATCH_TOOL_INSTRUCTIONS


def _should_fallback_to_plain_chat(session: Session, llm_config_id: int) -> bool:
    cfg = llm_config_service.get_llm_config(session, llm_config_id)
    if not cfg:
        return False
    transport = llm_config_service.resolve_transport_settings(
        provider=cfg.provider,
        api_base=cfg.api_base,
        base_url=cfg.base_url,
        api_protocol=getattr(cfg, "api_protocol", None),
        custom_request_path=getattr(cfg, "custom_request_path", None),
        models_path=getattr(cfg, "models_path", None),
        user_agent=getattr(cfg, "user_agent", None),
    )
    return bool(transport["use_responses_api"] and transport["provider"] == "openai_compatible")


async def stream_chat_plain(
    session: Session,
    request: AssistantChatRequest,
    system_prompt: str,
) -> AsyncGenerator[dict, None]:
    final_user_prompt = "\n\n".join(
        part for part in [request.context_info or "", request.user_prompt or ""] if part
    ) or "(User input is empty; assistant should clarify intent first.)"

    ok, reason = precheck_quota(
        session,
        request.llm_config_id,
        calc_input_tokens(system_prompt, final_user_prompt),
        need_calls=1,
    )
    if not ok:
        raise ValueError(f"Insufficient LLM quota: {reason}")

    model = build_chat_model(
        session=session,
        llm_config_id=request.llm_config_id,
        temperature=request.temperature or 0.6,
        max_tokens=16384 if request.max_tokens is None else request.max_tokens,
        timeout=request.timeout or 90,
        thinking_enabled=getattr(request, "thinking_enabled", None),
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=final_user_prompt),
    ]

    accumulated_text = ""
    reasoning_accumulated = ""
    try:
        async for chunk in model.astream(messages):
            content_blocks = getattr(chunk, "content_blocks", None)
            delta_text = ""
            if isinstance(content_blocks, list):
                reasoning_parts: list[str] = []
                text_parts: list[str] = []
                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type")
                    if block_type == "text":
                        text_parts.append(str(block.get("text") or ""))
                    elif block_type == "reasoning":
                        text = str(block.get("reasoning") or block.get("text") or "")
                        if text:
                            reasoning_parts.append(text)
                delta_text = "".join(text_parts)
                reasoning_delta = "".join(reasoning_parts)
                if reasoning_delta:
                    reasoning_accumulated += reasoning_delta
                    yield {"type": "reasoning", "data": {"text": reasoning_delta, "delta": True}}
            else:
                content = getattr(chunk, "content", None)
                if isinstance(content, str):
                    delta_text = content

            if delta_text:
                accumulated_text += delta_text
                yield {"type": "token", "data": {"text": delta_text, "delta": True}}
    except asyncio.CancelledError:
        record_usage(
            session,
            request.llm_config_id,
            calc_input_tokens(system_prompt, final_user_prompt),
            estimate_tokens(accumulated_text + reasoning_accumulated),
            calls=1,
            aborted=True,
        )
        raise

    record_usage(
        session,
        request.llm_config_id,
        calc_input_tokens(system_prompt, final_user_prompt),
        estimate_tokens(accumulated_text + reasoning_accumulated),
        calls=1,
        aborted=False,
    )


async def stream_chat_with_react(
    session: Session,
    request: AssistantChatRequest,
    system_prompt: str,
) -> AsyncGenerator[dict, None]:
    deps = AssistantDeps(session=session, project_id=request.project_id)
    async for event in stream_chat_with_react_protocol(
        session=session,
        llm_config_id=request.llm_config_id,
        system_prompt=system_prompt,
        context_info=request.context_info or "",
        user_prompt=request.user_prompt or "",
        tool_registry=ASSISTANT_TOOL_REGISTRY,
        tool_descriptions=ASSISTANT_TOOL_DESCRIPTIONS,
        set_deps=set_assistant_deps,
        deps=deps,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        timeout=request.timeout,
        thinking_enabled=getattr(request, "thinking_enabled", None),
        max_steps=MAX_REACT_STEPS,
        protocol_instructions=ASSISTANT_REACT_PROTOCOL_INSTRUCTIONS,
        log_tag="Assistant-React",
    ):
        yield event


async def stream_chat_with_tools(
    session: Session,
    request: AssistantChatRequest,
    system_prompt: str,
) -> AsyncGenerator[dict, None]:
    """Standard mode: reuses the shared Tool Agent streaming core."""
    parts: list[str] = []
    if request.context_info:
        parts.append(request.context_info)
    if request.user_prompt:
        parts.append("\nUser: " + request.user_prompt)
    final_user_prompt = "\n\n".join(parts) if parts else "(User input is empty; assistant should clarify intent first.)"

    enable_summarization = getattr(request, "context_summarization_enabled", None)
    max_tokens_before_summary = (
        int(request.context_summarization_threshold)
        if getattr(request, "context_summarization_threshold", None)
        else 8192
    )

    deps = AssistantDeps(session=session, project_id=request.project_id)

    async for event in stream_agent_with_tools(
        session=session,
        llm_config_id=request.llm_config_id,
        system_prompt=system_prompt,
        user_prompt=final_user_prompt,
        tools=ASSISTANT_TOOLS,
        set_deps=set_assistant_deps,
        deps=deps,
        temperature=request.temperature or 0.6,
        max_tokens=16384 if request.max_tokens is None else request.max_tokens,
        timeout=request.timeout or 90,
        thinking_enabled=getattr(request, "thinking_enabled", None),
        enable_summarization=bool(enable_summarization),
        max_tokens_before_summary=max_tokens_before_summary,
        log_tag="LangChain+Agent",
    ):
        yield event


async def generate_assistant_chat_streaming(
    session: Session,
    request: AssistantChatRequest,
    system_prompt: str,
    track_stats: bool = True,
) -> AsyncGenerator[str, None]:
    """Inspiration-assistant-specific streaming chat generation (structured event-stream protocol)."""
    _ = track_stats
    manual_react_mode = getattr(request, "react_mode_enabled", None)
    cfg = llm_config_service.get_llm_config(session, request.llm_config_id)
    recommended_mode = (getattr(cfg, "recommended_assistant_mode", None) or "auto").strip().lower() if cfg else "auto"
    if manual_react_mode is None:
        react_enabled = recommended_mode == "react"
        recommended_plain_chat = recommended_mode == "plain"
    else:
        react_enabled = bool(manual_react_mode)
        recommended_plain_chat = False
    fallback_plain_chat = _should_fallback_to_plain_chat(session, request.llm_config_id)
    plain_chat_enabled = fallback_plain_chat or recommended_plain_chat
    logger.info(
        "[LangChain] generate_assistant_chat_streaming: using {} mode, model_id:{}",
        "plain chat" if plain_chat_enabled else ("React" if react_enabled else "standard"),
        request.llm_config_id
    )

    if plain_chat_enabled:
        engine = stream_chat_plain
        effective_system_prompt = system_prompt
    else:
        engine = stream_chat_with_react if react_enabled else stream_chat_with_tools
        effective_system_prompt = _with_assistant_tool_guidance(system_prompt)
    has_visible_output = False
    has_tool_events = False

    try:
        async for evt in engine(
            session=session,
            request=request,
            system_prompt=effective_system_prompt,
        ):
            evt_type = evt.get("type") if isinstance(evt, dict) else None
            evt_data = evt.get("data") if isinstance(evt, dict) else None

            if evt_type in ("token", "reasoning") and isinstance(evt_data, dict):
                evt_text = str(evt_data.get("text") or "")
                if evt_text.strip():
                    has_visible_output = True
            elif evt_type in ("tool_start", "tool_end", "tool_summary"):
                has_tool_events = True

            yield json.dumps(evt, ensure_ascii=False)

        if not has_visible_output:
            fallback_text = (
                "Tool calls were executed. Please review the tool results."
                if has_tool_events
                else "No visible reply text was produced this round. Please retry or adjust your question."
            )
            yield json.dumps(
                {
                    "type": "token",
                    "data": {"text": fallback_text, "delta": False},
                },
                ensure_ascii=False,
            )
    except asyncio.CancelledError:
        logger.info("[LangChain] assistant call was cancelled (CancelledError)")
        return
    except Exception as exc:
        logger.error("[LangChain] inspiration assistant generation failed: {}", exc)
        error_event = {
            "type": "error",
            "data": {"error": str(exc)},
        }
        yield json.dumps(error_event, ensure_ascii=False)
        raise