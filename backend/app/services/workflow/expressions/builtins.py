"""Expression execution environment (controlled builtins + helpers)"""

from __future__ import annotations

import builtins as py_builtins
from functools import lru_cache
from typing import Any, Callable, Dict

from .functions import get_builtin_functions


ALLOWED_BUILTIN_NAMES = (
    "len",
    "sum",
    "min",
    "max",
    "str",
    "int",
    "float",
    "bool",
    "list",
    "dict",
    "set",
    "tuple",
    "range",
    "enumerate",
    "zip",
    "any",
    "all",
    "abs",
    "round",
    "sorted",
)


@lru_cache(maxsize=1)
def get_safe_builtins() -> Dict[str, Any]:
    """Get the safe builtin function whitelist"""
    return {
        name: getattr(py_builtins, name)
        for name in ALLOWED_BUILTIN_NAMES
        if hasattr(py_builtins, name)
    }


@lru_cache(maxsize=1)
def get_safe_helpers() -> Dict[str, Callable]:
    """Get expression helpers (compatible with the legacy function library)"""
    return get_builtin_functions()


@lru_cache(maxsize=1)
def get_safe_globals() -> Dict[str, Any]:
    """Build the eval globals"""
    safe_builtins = get_safe_builtins()
    safe_helpers = get_safe_helpers()
    globals_dict: Dict[str, Any] = {
        "__builtins__": safe_builtins
    }

    # When a helper shares a name with a builtin, the builtin takes precedence
    for name, func in safe_helpers.items():
        if name not in safe_builtins:
            globals_dict[name] = func

    return globals_dict


@lru_cache(maxsize=1)
def get_safe_global_names() -> set[str]:
    """Get globally visible names (used for dependency extraction filtering)"""
    names = set(get_safe_builtins().keys())
    names.update(get_safe_helpers().keys())
    return names