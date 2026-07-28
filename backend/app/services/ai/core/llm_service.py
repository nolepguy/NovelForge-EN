"""General LLM service

Provides ChatModel construction, structured generation, and continuation features.
"""

from typing import Any, Dict, Type, Optional, AsyncGenerator
from pydantic import BaseModel
from sqlmodel import Session
from loguru import logger
import asyncio
import json

from langchain_core.messages import HumanMessage, SystemMessage
from app.services.ai.generation.continuation_budget_runtime import (
    build_budget_hint_text,
    build_round_plan,
    count_text_units,
    estimate_required_call_count,
    normalize_word_control_mode,
    trim_generated_text,
)
from app.services.ai.generation.structured_runtime import (
    generate_structured_via_instruction_flow_model,
)
from app.schemas.ai import ContinuationRequest
from .chat_model_factory import build_chat_model
from .token_utils import calc_input_tokens, estimate_tokens
from .quota_manager import precheck_quota, record_usage


async def generate_structured(
    session: Session,
    llm_config_id: int,
    user_prompt: str,
    output_type: Type[BaseModel],
    system_prompt: Optional[str] = None,
    deps: str = "",
    max_tokens: Optional[int] = None,
    max_retries: int = 3,
    temperature: Optional[float] = None,
    timeout: Optional[float] = None,
    track_stats: bool = True,
    use_instruction_flow: bool = False,
    return_logs: bool = False,
) -> BaseModel | Dict[str, Any]:
    """Structured output generation

    Uses the LangChain ChatModel's structured output capability.

    Args:
        session: Database session
        llm_config_id: LLM config ID
        user_prompt: User prompt
        output_type: Output Pydantic model type
        system_prompt: System prompt
        deps: Dependencies (reserved)
        max_tokens: Maximum number of tokens
        max_retries: Maximum number of retries
        temperature: Temperature parameter
        timeout: Timeout
        track_stats: Whether to record statistics

    Returns:
        Structured output object
    """
    if use_instruction_flow:
        return await generate_structured_via_instruction_flow_model(
            session=session,
            llm_config_id=llm_config_id,
            user_prompt=user_prompt,
            output_type=output_type,
            system_prompt=system_prompt,
            deps=deps,
            max_tokens=max_tokens,
            max_retries=max_retries,
            temperature=temperature,
            timeout=timeout,
            track_stats=track_stats,
            return_logs=return_logs,
        )

    native_result = await _generate_structured_native(
        session=session,
        llm_config_id=llm_config_id,
        user_prompt=user_prompt,
        output_type=output_type,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        max_retries=max_retries,
        temperature=temperature,
        timeout=timeout,
        track_stats=track_stats,
    )

    if return_logs:
        return {
            "result": native_result,
            "logs": [],
        }

    return native_result


async def generate_review(
    session: Session,
    llm_config_id: int,
    user_prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    timeout: Optional[float] = None,
    track_stats: bool = True,
) -> str:
    """Review text generation."""
    if track_stats:
        ok, reason = precheck_quota(
            session, llm_config_id,
            calc_input_tokens(system_prompt, user_prompt),
            need_calls=1
        )
        if not ok:
            raise ValueError(f"Insufficient LLM quota: {reason}")

    try:
        model = build_chat_model(
            session=session,
            llm_config_id=llm_config_id,
            temperature=temperature or 0.7,
            max_tokens=16384 if max_tokens is None else max_tokens,
            timeout=timeout or 150,
        )

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=user_prompt))

        logger.info(f"Starting review, prompt: {system_prompt} \n\n {user_prompt}")
        response = await model.ainvoke(messages)
        content = getattr(response, "content", response)
        if isinstance(content, list):
            text = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        else:
            text = "" if content is None else str(content)

        if not text.strip():
            raise ValueError("LLM returned an empty response")

        if track_stats:
            in_tokens = calc_input_tokens(system_prompt, user_prompt)
            out_tokens = estimate_tokens(text)
            record_usage(
                session, llm_config_id,
                in_tokens, out_tokens,
                calls=1, aborted=False
            )

        return text.strip()
    except asyncio.CancelledError:
        logger.info("[LangChain-Text] LLM call was cancelled (CancelledError), aborting immediately.")
        if track_stats:
            in_tokens = calc_input_tokens(system_prompt, user_prompt)
            record_usage(
                session, llm_config_id,
                in_tokens, 0,
                calls=1, aborted=True
            )
        raise


async def _generate_structured_native(
    *,
    session: Session,
    llm_config_id: int,
    user_prompt: str,
    output_type: Type[BaseModel],
    system_prompt: Optional[str],
    max_tokens: Optional[int],
    max_retries: int,
    temperature: Optional[float],
    timeout: Optional[float],
    track_stats: bool,
) -> BaseModel:
    """Native structured output implementation (LangChain with_structured_output)."""

    # Quota pre-check
    if track_stats:
        ok, reason = precheck_quota(
            session, llm_config_id,
            calc_input_tokens(system_prompt, user_prompt),
            need_calls=1
        )
        if not ok:
            raise ValueError(f"Insufficient LLM quota: {reason}")

    last_exception = None
    for attempt in range(max_retries):
        try:
            model = build_chat_model(
                session=session,
                llm_config_id=llm_config_id,
                temperature=temperature or 0.7,
                max_tokens=16384 if max_tokens is None else max_tokens,
                timeout=timeout or 150,
            )

            structured_llm = model.with_structured_output(output_type)

            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=user_prompt))

            response = await structured_llm.ainvoke(messages)

            if response is None:
                raise ValueError("LLM returned an empty response")

            logger.info(f"[LangChain-Structured] response: {response}")

            if track_stats:
                in_tokens = calc_input_tokens(system_prompt, user_prompt)
                try:
                    out_text = (
                        response
                        if isinstance(response, str)
                        else json.dumps(response, ensure_ascii=False)
                    )
                except Exception:
                    out_text = str(response)
                out_tokens = estimate_tokens(out_text)
                record_usage(
                    session, llm_config_id,
                    in_tokens, out_tokens,
                    calls=1, aborted=False
                )

            return response

        except asyncio.CancelledError:
            logger.info("[LangChain-Structured] LLM call was cancelled (CancelledError), aborting immediately, no more retries.")
            if track_stats:
                in_tokens = calc_input_tokens(system_prompt, user_prompt)
                record_usage(
                    session, llm_config_id,
                    in_tokens, 0,
                    calls=1, aborted=True
                )
            raise
        except Exception as e:
            last_exception = e
            logger.warning(
                f"[LangChain-Structured] call failed, retry {attempt + 1}/{max_retries}, llm_config_id={llm_config_id}: {e}"
            )

            if attempt < max_retries - 1:
                retry_delay = min(2 ** attempt, 4)
                logger.info(f"[LangChain-Structured] waiting {retry_delay} seconds before retry...")
                await asyncio.sleep(retry_delay)

    logger.error(
        f"[LangChain-Structured] call still failed after {max_retries} retries, llm_config_id={llm_config_id}. Last error: {last_exception}"
    )
    raise ValueError(
        f"LLM service call failed after {max_retries} retries: {str(last_exception)}"
    )


async def generate_continuation_streaming(
    session: Session,
    request: ContinuationRequest,
    system_prompt: str,
    track_stats: bool = True
) -> AsyncGenerator[str, None]:
    """Continuation streaming generation

    Args:
        session: Database session
        request: Continuation request object
        system_prompt: System prompt (passed in from outside)
        track_stats: Whether to record statistics

    Yields:
        Generated text fragments
    """
    current_word_count = getattr(request, "existing_word_count", None)
    if current_word_count is None:
        current_word_count = count_text_units(getattr(request, "previous_content", ""))

    control_mode = normalize_word_control_mode(request)
    expected_rounds = estimate_required_call_count(request)
    if control_mode == "prompt_only" or expected_rounds <= 1:
        round_plan = build_round_plan(request, current_word_count, 1)
        async for chunk in _stream_continuation_single_round(
            session=session,
            request=request,
            system_prompt=system_prompt,
            round_plan=round_plan,
            track_stats=track_stats,
        ):
            yield chunk
        return

    current_content = request.previous_content or ""

    for round_index in range(1, expected_rounds + 1):
        round_plan = build_round_plan(request, current_word_count, round_index)
        round_request = request.model_copy(update={
            "previous_content": current_content,
            "existing_word_count": current_word_count,
            "word_control_mode": control_mode,
            "budget_round_hint": round_plan.round_index,
            "remaining_word_count_hint": round_plan.remaining_word_count,
            "is_final_round_hint": round_plan.is_final_round,
        })

        round_chunks: list[str] = []
        async for chunk in _stream_continuation_single_round(
            session=session,
            request=round_request,
            system_prompt=system_prompt,
            round_plan=round_plan,
            track_stats=track_stats,
        ):
            round_chunks.append(chunk)
            if getattr(request, "stream", False):
                yield chunk

        round_text = "".join(round_chunks)
        if not round_text.strip():
            logger.warning("Continuation budget runtime got empty output in round {}, stopping early.", round_index)
            break

        trim_result = trim_generated_text(round_text, round_plan)
        final_text = round_text if getattr(request, "stream", False) else trim_result.text
        if not final_text.strip():
            logger.warning("Continuation budget runtime got empty output after trimming in round {}, stopping early.", round_index)
            break

        current_content = f"{current_content}{final_text}"
        current_word_count = count_text_units(current_content)

        if not getattr(request, "stream", False):
            for chunk in _chunk_text(final_text):
                yield chunk

        target_word_count = getattr(request, "target_word_count", None)
        if trim_result.trimmed and not getattr(request, "stream", False):
            logger.info("Continuation budget runtime triggered sentence-boundary wrap-up in round {}.", round_index)
            break
        if target_word_count is not None and current_word_count >= target_word_count:
            break
        if round_plan.is_final_round:
            break


def _build_continuation_user_prompt(
    request: ContinuationRequest,
    round_plan,
) -> str:
    # Assemble the user message
    user_prompt_parts = []

    # 1. Add context info (reference context + facts subgraph)
    context_info = (getattr(request, 'context_info', None) or '').strip()
    if context_info:
        # Detect whether context_info already contains structured markers
        has_structured_marks = any(
            mark in context_info
            for mark in ['[Reference Context]', '[Previous Content]', '[Needs Polish', '[Needs Expand']
        )

        if has_structured_marks:
            # Already structured context, use directly
            user_prompt_parts.append(context_info)
        else:
            # Unstructured context (legacy format), add a marker
            user_prompt_parts.append(f"[Reference Context]\n{context_info}")

    # 2. Add existing chapter content (only when previous_content is non-empty)
    previous_content = (request.previous_content or '').strip()
    if previous_content:
        user_prompt_parts.append(f"[Existing Chapter Content]\n{previous_content}")

        # Continuation instruction
        if getattr(request, 'append_continuous_novel_directive', True):
            user_prompt_parts.append("[Instruction]Please continue writing from the above content, keeping the style and plot coherent. Output the novel body directly.")
    else:
        # New-writing mode or polish/expand mode (previous_content is empty)
        if getattr(request, 'append_continuous_novel_directive', True):
            if context_info and '[Existing Chapter Content]' in context_info:
                user_prompt_parts.append("[Instruction]Please continue writing from the above content, keeping the style and plot coherent. Output the novel body directly.")
            else:
                user_prompt_parts.append("[Instruction]Please start creating a new chapter. Output the novel body directly.")

    budget_hint = build_budget_hint_text(
        round_plan,
        getattr(request, "continuation_guidance", None),
        include_outline_boundary=getattr(request, "append_continuous_novel_directive", True),
    )
    if budget_hint:
        user_prompt_parts.append(budget_hint)

    return "\n\n".join(user_prompt_parts)


async def _stream_continuation_single_round(
    session: Session,
    request: ContinuationRequest,
    system_prompt: str,
    round_plan,
    track_stats: bool = True,
) -> AsyncGenerator[str, None]:
    user_prompt = _build_continuation_user_prompt(request, round_plan)

    # Quota pre-check
    if track_stats:
        ok, reason = precheck_quota(
            session, request.llm_config_id,
            calc_input_tokens(system_prompt, user_prompt),
            need_calls=1
        )
        if not ok:
            raise ValueError(f"Insufficient LLM quota: {reason}")

    # Use the LangChain ChatModel for streaming continuation
    model = build_chat_model(
        session=session,
        llm_config_id=request.llm_config_id,
        temperature=request.temperature or 0.7,
        max_tokens=round_plan.max_tokens,
        timeout=request.timeout or 64,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    logger.info(f"Starting continuation, prompt: {system_prompt} \n\n {user_prompt}")

    accumulated: str = ""
    pending_buffer: str = ""
    stream_with_hard_limit = bool(
        getattr(request, "stream", False)
        and round_plan.mode != "prompt_only"
        and not round_plan.is_final_round
        and round_plan.hard_word_limit
    )
    should_stop_current_round = False

    try:
        logger.debug("Streaming continuation content with the LangChain ChatModel")
        async for chunk in model.astream(messages):
            content = getattr(chunk, "content", None)
            if not content:
                continue

            if isinstance(content, str):
                delta = content
            elif isinstance(content, list):
                texts = [
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                ]
                delta = "".join(texts)
            else:
                delta = str(content)

            if not delta:
                continue

            if stream_with_hard_limit:
                pending_buffer += delta
                emitted_text, pending_buffer, reached_limit = _flush_streaming_buffer_with_limit(
                    already_emitted=accumulated,
                    pending_text=pending_buffer,
                    hard_limit=round_plan.hard_word_limit or 0,
                )
                if emitted_text:
                    accumulated += emitted_text
                    yield emitted_text
                if reached_limit:
                    should_stop_current_round = True
                    break
                continue

            accumulated += delta
            yield delta

        if stream_with_hard_limit and not should_stop_current_round and pending_buffer:
            emitted_tail, pending_buffer, reached_limit = _flush_streaming_buffer_with_limit(
                already_emitted=accumulated,
                pending_text=pending_buffer,
                hard_limit=round_plan.hard_word_limit or 0,
                force_flush_tail=True,
            )
            if emitted_tail:
                accumulated += emitted_tail
                yield emitted_tail

    except asyncio.CancelledError:
        logger.info("Streaming LLM call was cancelled (CancelledError), stopping push.")
        if track_stats:
            in_tokens = calc_input_tokens(system_prompt, user_prompt)
            out_tokens = estimate_tokens(accumulated)
            record_usage(
                session, request.llm_config_id,
                in_tokens, out_tokens,
                calls=1, aborted=True
            )
        return
    except Exception as e:
        logger.error(f"Streaming LLM call failed: {e}")
        raise

    # Record statistics after normal completion
    try:
        if track_stats:
            in_tokens = calc_input_tokens(system_prompt, user_prompt)
            out_tokens = estimate_tokens(accumulated)
            record_usage(
                session, request.llm_config_id,
                in_tokens, out_tokens,
                calls=1, aborted=False
            )
    except Exception as stat_e:
        logger.warning(f"Failed to record LLM streaming statistics: {stat_e}")


async def _collect_continuation_single_round(
    session: Session,
    request: ContinuationRequest,
    system_prompt: str,
    round_plan,
    track_stats: bool = True,
) -> str:
    chunks: list[str] = []
    async for chunk in _stream_continuation_single_round(
        session=session,
        request=request,
        system_prompt=system_prompt,
        round_plan=round_plan,
        track_stats=track_stats,
    ):
        chunks.append(chunk)
    return "".join(chunks)


def _chunk_text(text: str, chunk_size: int = 240) -> list[str]:
    if not text:
        return []
    return [text[index:index + chunk_size] for index in range(0, len(text), chunk_size)]


def _flush_streaming_buffer_with_limit(
    *,
    already_emitted: str,
    pending_text: str,
    hard_limit: int,
    force_flush_tail: bool = False,
) -> tuple[str, str, bool]:
    if not pending_text:
        return "", "", False

    emitted_parts: list[str] = []
    rest = pending_text

    while True:
        sentence_end = _find_first_sentence_boundary(rest)
        if sentence_end is None:
            break
        sentence = rest[:sentence_end]
        next_text = already_emitted + "".join(emitted_parts) + sentence
        if count_text_units(next_text) > hard_limit:
            return "".join(emitted_parts), rest, True
        emitted_parts.append(sentence)
        rest = rest[sentence_end:]

    if force_flush_tail and rest:
        next_text = already_emitted + "".join(emitted_parts) + rest
        if count_text_units(next_text) <= hard_limit:
            emitted_parts.append(rest)
            rest = ""
        elif not emitted_parts:
            truncated = _take_text_by_units(rest, hard_limit - count_text_units(already_emitted))
            return truncated, "", True
        else:
            return "".join(emitted_parts), rest, True

    return "".join(emitted_parts), rest, False


def _find_first_sentence_boundary(text: str) -> int | None:
    for idx, char in enumerate(text):
        if char in "。！？!?…\n":
            return idx + 1
    return None


def _take_text_by_units(text: str, limit_units: int) -> str:
    # Word-based take: emit up to limit_units whitespace-delimited words,
    # preserving original spacing. A new word begins at the first non-space
    # char following a space; once we start the (limit_units + 1)-th word we
    # stop appending. This stays consistent with count_text_units (word count).
    if limit_units <= 0 or not text:
        return ""
    words = 0
    in_word = False
    out_chars: list[str] = []
    for char in text:
        if char.isspace():
            in_word = False
        elif not in_word:
            words += 1
            in_word = True
            if words > limit_units:
                break
        out_chars.append(char)
    return "".join(out_chars).rstrip()
