"""Token estimation utilities

Pure-function implementation, with no external dependencies.
"""

import re
from typing import Optional

_TOKEN_REGEX = re.compile(
    r"""
    ([A-Za-z]+)               # English word (consecutive letters count as 1)
    |([0-9])                 # 1 digit counts as 1
    |([\u4E00-\u9FFF])       # A single Chinese character counts as 1
    |(\S)                     # Other non-whitespace symbol/punctuation counts as 1
    """,
    re.VERBOSE,
)


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens

    Rules:
    - 1 Chinese character = 1 token
    - 1 English word = 1 token
    - 1 digit = 1 token
    - 1 symbol = 1 token
    - Whitespace is not counted

    Args:
        text: The text to estimate

    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0
    try:
        return sum(1 for _ in _TOKEN_REGEX.finditer(text))
    except Exception:
        # Fallback: count non-whitespace characters
        return sum(1 for ch in text if not ch.isspace())


def calc_input_tokens(system_prompt: Optional[str], user_prompt: Optional[str]) -> int:
    """Calculate the total number of input tokens

    Args:
        system_prompt: System prompt
        user_prompt: User prompt

    Returns:
        Total number of tokens
    """
    sys_part = system_prompt or ""
    usr_part = user_prompt or ""
    return int(round(0.6 * estimate_tokens(sys_part + usr_part)))