"""ChatModel factory.

Centrally manages LLM config reading and LangChain ChatModel construction to avoid
repeated parameter assembly in the business layer.
"""

from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_qwq import ChatQwen
from sqlmodel import Session

from app.db.models import LLMConfig
from app.services import llm_config_service


def _sanitize_common_generation_kwargs(
    *,
    temperature: Optional[float],
    max_tokens: Optional[int],
    timeout: Optional[float],
) -> dict:
    normalized_max_tokens = None if max_tokens == -1 else max_tokens
    kwargs: dict = {}
    if temperature is not None:
        kwargs["temperature"] = float(temperature)
    if normalized_max_tokens is not None:
        kwargs["max_tokens"] = int(normalized_max_tokens)
    if timeout is not None:
        kwargs["timeout"] = float(timeout)
    return kwargs


def _build_openai_family_transport_kwargs(transport: dict) -> dict:
    kwargs: dict = {}
    if transport["request_base"]:
        # LangChain accepts `base_url` here uniformly.
        # Previously passing it as `openai_api_base` would cause `ChatQwen` to ignore the custom gateway,
        # and legacy openai_compatible configs would incorrectly fall back to the provider default endpoint.
        kwargs["base_url"] = transport["request_base"]
    if transport["default_headers"]:
        kwargs["default_headers"] = transport["default_headers"]
    if transport["api_protocol"] != "auto":
        kwargs["use_responses_api"] = transport["api_protocol"] == "responses"
    elif transport["use_responses_api"]:
        kwargs["use_responses_api"] = True
    return kwargs


def build_chat_model_from_payload(
    *,
    provider: str,
    model_name: str,
    api_key: str,
    api_base: str | None = None,
    base_url: str | None = None,
    api_protocol: str | None = None,
    custom_request_path: str | None = None,
    user_agent: str | None = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
    thinking_enabled: Optional[bool] = None,
):
    if not api_key:
        raise ValueError("No API Key provided")

    transport = llm_config_service.resolve_transport_settings(
        provider=provider,
        api_base=api_base,
        base_url=base_url,
        api_protocol=api_protocol,
        custom_request_path=custom_request_path,
        user_agent=user_agent,
    )
    provider_name = transport["provider"]
    common_kwargs = _sanitize_common_generation_kwargs(
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )

    if provider_name in {"openai_compatible", "openai"}:
        model_kwargs = {
            "model": model_name,
            "api_key": api_key,
            **_build_openai_family_transport_kwargs(transport),
            **common_kwargs,
        }
        if thinking_enabled is not None:
            model_kwargs["extra_body"] = {"enable_thinking": thinking_enabled}

        # In `responses` mode, uniformly use `ChatOpenAI`.
        # Previously openai_compatible still used `ChatQwen`, which would build a payload
        # during streaming continuation that does not satisfy openai-python Responses API
        # requirements, triggering
        # "Missing required arguments; Expected either ('messages' and 'model') ...".
        if transport["use_responses_api"]:
            return ChatOpenAI(**model_kwargs)

        if provider_name == "openai_compatible":
            return ChatQwen(**model_kwargs)
        return ChatOpenAI(**model_kwargs)

    if provider_name == "anthropic":
        model_kwargs = {
            "model": model_name,
            "api_key": api_key,
            **common_kwargs,
        }
        if thinking_enabled is True:
            model_kwargs["thinking"] = {"type": "enabled", "budget_tokens": 2048}
        return ChatAnthropic(**model_kwargs)

    if provider_name == "google":
        model_kwargs = {
            "model": model_name,
            "api_key": api_key,
        }
        if thinking_enabled is not None:
            model_kwargs["include_thoughts"] = thinking_enabled
        if common_kwargs.get("max_tokens") is not None:
            model_kwargs["max_output_tokens"] = common_kwargs["max_tokens"]
        if common_kwargs.get("temperature") is not None:
            model_kwargs["temperature"] = common_kwargs["temperature"]
        if common_kwargs.get("timeout") is not None:
            model_kwargs["timeout"] = common_kwargs["timeout"]
        return ChatGoogleGenerativeAI(**model_kwargs)

    raise ValueError(f"Unsupported LLM provider: {provider}")


def _get_llm_config(session: Session, llm_config_id: int) -> LLMConfig:
    cfg = llm_config_service.get_llm_config(session, llm_config_id)
    if not cfg:
        raise ValueError(f"LLM config does not exist, ID: {llm_config_id}")
    if not cfg.api_key:
        raise ValueError(f"No API key found for LLM config {cfg.display_name or cfg.model_name}")
    return cfg


def build_chat_model(
    session: Session,
    llm_config_id: int,
    *,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
    thinking_enabled: Optional[bool] = None,
):
    cfg = _get_llm_config(session, llm_config_id)
    return build_chat_model_from_payload(
        provider=cfg.provider,
        model_name=cfg.model_name,
        api_key=cfg.api_key,
        api_base=cfg.api_base,
        base_url=cfg.base_url,
        api_protocol=getattr(cfg, "api_protocol", None),
        custom_request_path=getattr(cfg, "custom_request_path", None),
        user_agent=getattr(cfg, "user_agent", None),
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        thinking_enabled=thinking_enabled,
    )