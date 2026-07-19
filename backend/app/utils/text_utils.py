"""Text processing utilities

Pure-function implementation, with no external dependencies.
"""


def truncate_text(text: str, limit: int, suffix: str = "\n...[truncated]") -> str:
    """Truncate text to a specified length
    
    Args:
        text: The text to truncate
        limit: Maximum length
        suffix: Truncation suffix
        
    Returns:
        The truncated text
    """
    if len(text) <= limit:
        return text
    # Reserve space for the suffix to avoid exceeding limit after truncation
    truncate_at = max(0, limit - len(suffix))
    return text[:truncate_at] + suffix
