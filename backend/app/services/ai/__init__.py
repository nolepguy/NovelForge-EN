"""AI service module

Unified LLM invocation, structured generation, continuation, and assistant services.
"""

from .core.chat_model_factory import build_chat_model
from .core.llm_service import (
    generate_structured,
    generate_continuation_streaming,
)
from .assistant.assistant_service import (
    generate_assistant_chat_streaming,
)

__all__ = [
    'build_chat_model',
    'generate_structured',
    'generate_continuation_streaming',
    'generate_assistant_chat_streaming',
]