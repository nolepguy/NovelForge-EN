"""LLM quota management

Responsible for quota pre-checks and usage statistics recording.
"""

from typing import Tuple
from sqlmodel import Session
from loguru import logger

from app.services import llm_config_service


def precheck_quota(
    session: Session,
    llm_config_id: int,
    input_tokens: int,
    need_calls: int = 1
) -> Tuple[bool, str]:
    """Pre-check whether quota is sufficient

    Args:
        session: Database session
        llm_config_id: LLM config ID
        input_tokens: Estimated number of input tokens
        need_calls: Estimated number of calls

    Returns:
        (whether passed, reason description)
    """
    return llm_config_service.can_consume(
        session, llm_config_id, input_tokens, 0, need_calls
    )


def record_usage(
    session: Session,
    llm_config_id: int,
    input_tokens: int,
    output_tokens: int,
    calls: int = 1,
    aborted: bool = False
) -> None:
    """Record LLM usage

    Args:
        session: Database session
        llm_config_id: LLM config ID
        input_tokens: Actual number of input tokens
        output_tokens: Actual number of output tokens
        calls: Number of calls
        aborted: Whether it was aborted
    """
    try:
        llm_config_service.accumulate_usage(
            session, llm_config_id,
            max(0, input_tokens),
            max(0, output_tokens),
            max(0, calls),
            aborted=aborted
        )
    except Exception as e:
        logger.warning(f"Failed to record LLM statistics: {e}")