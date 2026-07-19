"""Expression context wrapper (simplified version)"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Dict


PRIMITIVE_TYPES = (
    str,
    int,
    float,
    bool,
    bytes,
    bytearray,
    complex,
    date,
    datetime,
    time,
)


class AttrDict(dict):
    """Dict that supports attribute access (missing fields return None)"""

    def __getattr__(self, item: str) -> Any:
        if item.startswith("__"):
            raise AttributeError(item)
        return self.get(item, None)

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, wrap_value(value))


def wrap_value(value: Any) -> Any:
    """Recursively wrap values, keeping only the necessary compatibility (dict attribute access)"""
    if value is None:
        return None
    if isinstance(value, AttrDict):
        return value
    if isinstance(value, PRIMITIVE_TYPES):
        return value
    if isinstance(value, dict):
        wrapped = AttrDict()
        for key, item in value.items():
            wrapped[key] = item
        return wrapped
    if isinstance(value, list):
        return [wrap_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(wrap_value(item) for item in value)
    if isinstance(value, set):
        return {wrap_value(item) for item in value}
    return value


def unwrap_value(value: Any) -> Any:
    """Recursively unwrap values into standard Python data structures"""
    if isinstance(value, AttrDict):
        return {
            key: unwrap_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [unwrap_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(unwrap_value(item) for item in value)
    if isinstance(value, set):
        return {unwrap_value(item) for item in value}
    return value


def wrap_context(context: Dict[str, Any] | None) -> Dict[str, Any]:
    """Wrap the expression context"""
    if not context:
        return {}
    return {
        key: wrap_value(value)
        for key, value in context.items()
    }