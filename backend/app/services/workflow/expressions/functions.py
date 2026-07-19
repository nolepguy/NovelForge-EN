"""Expression helper function library (simplified version)

Notes:
- Only keeps helpers that are not Python builtins and have clear value in workflows.
- Capabilities with the same name as builtins (such as len/str/int/range/sum) are
  uniformly provided by `builtins.py`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict


_HELPER_REGISTRY: Dict[str, Callable[..., Any]] = {}
_HELPER_META_REGISTRY: Dict[str, "HelperMeta"] = {}


@dataclass(frozen=True)
class HelperMeta:
    """Helper metadata (used to auto-generate AI descriptions)"""

    summary: str
    scenario: str
    priority: int = 50
    example: str = ""


def register_function(
    name: str,
    *,
    summary: str = "",
    scenario: str = "",
    priority: int = 50,
    example: str = "",
):
    """Decorator to register a helper (keeps extensibility)"""

    def decorator(func: Callable[..., Any]):
        _HELPER_REGISTRY[name] = func
        _HELPER_META_REGISTRY[name] = HelperMeta(
            summary=summary or ((func.__doc__ or "").strip()),
            scenario=scenario or "general",
            priority=priority,
            example=example,
        )
        return func

    return decorator


def get_builtin_functions() -> Dict[str, Callable[..., Any]]:
    """Get all helpers (returns a copy)"""
    return _HELPER_REGISTRY.copy()


def get_helper_metadata() -> Dict[str, HelperMeta]:
    """Get helper metadata (returns a copy)"""
    return _HELPER_META_REGISTRY.copy()


@register_function(
    "default",
    summary="Return a default value when value is None",
    scenario="Null fallback",
    priority=75,
    example="default(card.content.title, 'Untitled')",
)
def fn_default(value: Any, default_value: Any) -> Any:
    """Return a default value when value is None"""
    return value if value is not None else default_value


@register_function(
    "coalesce",
    summary="Return the first non-None value",
    scenario="Multi-candidate field fallback",
    priority=85,
    example="coalesce(a.title, a.name, 'Untitled')",
)
def fn_coalesce(*values: Any) -> Any:
    """Return the first non-None value"""
    for value in values:
        if value is not None:
            return value
    return None


@register_function(
    "merge",
    summary="Merge multiple dicts, ignoring non-dict arguments",
    scenario="Data assembly",
    priority=80,
    example="merge(base, {'project_id': project.id})",
)
def fn_merge(*dicts: Any) -> Dict[str, Any]:
    """Merge multiple dicts, ignoring non-dict arguments"""
    result: Dict[str, Any] = {}
    for item in dicts:
        if isinstance(item, dict):
            result.update(item)
    return result


@register_function(
    "json_parse",
    summary="Convert a JSON string to an object",
    scenario="Parse externally returned JSON",
    priority=60,
    example="json_parse(raw_json).get('items', [])",
)
def fn_json_parse(json_str: str) -> Any:
    """Convert a JSON string to an object"""
    return json.loads(json_str)


@register_function(
    "json_stringify",
    summary="Convert an object to a JSON string",
    scenario="Debug output and archiving",
    priority=55,
    example="json_stringify(result, indent=2)",
)
def fn_json_stringify(obj: Any, indent: int | None = None) -> str:
    """Convert an object to a JSON string"""
    return json.dumps(obj, indent=indent, ensure_ascii=False)


@register_function(
    "read_file",
    summary="Read file contents (returns an error text on failure)",
    scenario="Inject external file contents into the workflow",
    priority=95,
    example="read_file(item.meta.path)",
)
def fn_read_file(path: str, encoding: str = "utf-8") -> str:
    """Read file contents (returns an error text on failure)"""
    try:
        with open(path, "r", encoding=encoding) as file:
            return file.read()
    except Exception as exc:
        return f"[Read failed: {exc}]"


@register_function(
    "normalize_ranges",
    summary="Fix gaps/overlaps in a range list to ensure continuous coverage",
    scenario="Stage range / chapter attribution fallback",
    priority=92,
    example="normalize_ranges(stages, start=1, end=total_chapters)",
)
def fn_normalize_ranges(
    ranges: Any,
    *,
    start: int = 1,
    end: int | None = None,
    start_key: str = "chapter_start",
    end_key: str = "chapter_end",
) -> list[dict[str, Any]]:
    """Normalize a range list, fixing gaps and overlaps.

    - Input: list[dict], each item must contain at least start_key/end_key.
    - Output: a new list[dict] sorted by start_key (does not modify the original).
    - Rules:
      1) Sort by start_key
      2) If a gap appears (cur_start > prev_end + 1), merge the gap into the previous
         segment (extend prev_end)
      3) If an overlap appears (cur_start <= prev_end), adjust cur_start to prev_end + 1
      4) If end is specified, pad the last segment up to end (if insufficient), and no
         segment end exceeds end
    """

    if not isinstance(ranges, list) or not ranges:
        return []

    normalized: list[dict[str, Any]] = []

    def _to_int(value: Any) -> int | None:
        try:
            return int(value)
        except Exception:
            return None

    # Filter and copy
    cleaned: list[dict[str, Any]] = []
    for item in ranges:
        if not isinstance(item, dict):
            continue
        s = _to_int(item.get(start_key))
        e = _to_int(item.get(end_key))
        if s is None or e is None:
            continue
        copied = dict(item)
        copied[start_key] = s
        copied[end_key] = e
        cleaned.append(copied)

    if not cleaned:
        return []

    cleaned.sort(key=lambda x: (x[start_key], x[end_key]))

    for idx, item in enumerate(cleaned):
        cur = dict(item)
        cur_start = cur[start_key]
        cur_end = cur[end_key]

        if idx == 0:
            if cur_start > start:
                cur_start = start
            if cur_end < cur_start:
                cur_end = cur_start
            if end is not None and cur_end > end:
                cur_end = end
            cur[start_key] = cur_start
            cur[end_key] = cur_end
            normalized.append(cur)
            continue

        prev = normalized[-1]
        prev_end = int(prev[end_key])
        expected = prev_end + 1

        if cur_start > expected:
            # Merge the gap into the previous segment: extend the previous end to the end of the gap (expected..cur_start-1)
            prev[end_key] = cur_start - 1
            prev_end = int(prev[end_key])
            expected = prev_end + 1

        if cur_start < expected:
            cur_start = expected

        if cur_end < cur_start:
            cur_end = cur_start

        if end is not None and cur_start > end:
            break

        if end is not None and cur_end > end:
            cur_end = end

        cur[start_key] = cur_start
        cur[end_key] = cur_end
        normalized.append(cur)

    if end is not None and normalized:
        last = normalized[-1]
        if int(last[end_key]) < end:
            last[end_key] = end

    return normalized


@register_function(
    "squash_adjacent_stages",
    summary="Merge adjacent duplicate stages, suppressing single-chapter duplicate stages",
    scenario="Stage planning deduplication",
    priority=90,
    example="squash_adjacent_stages(stages)",
)
def fn_squash_adjacent_stages(
    stages: Any,
    *,
    name_key: str = "stage_name",
    start_key: str = "chapter_start",
    end_key: str = "chapter_end",
    outline_key: str = "stage_outline",
    summary_key: str = "stage_summary",
    tiny_threshold: int = 1,
) -> list[dict[str, Any]]:
    """Merge adjacent duplicate stages, avoiding "same name + similar content + single chapter" fragments.

    Rules:
    1) Only process adjacent stages.
    2) If adjacent stages share the same name, directly merge the chapter range,
       keeping the richer text side.
    3) If the current stage is only 1 chapter and its text is highly similar to the
       previous stage, also merge it into the previous stage.
    """

    if not isinstance(stages, list) or not stages:
        return []

    def _to_int(value: Any) -> int | None:
        try:
            return int(value)
        except Exception:
            return None

    def _clean_text(value: Any) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        return re.sub(r"\s+", "", text)

    def _is_similar_text(a: Any, b: Any) -> bool:
        ta = _clean_text(a)
        tb = _clean_text(b)
        if not ta or not tb:
            return False
        if ta == tb:
            return True
        short, long = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
        return len(short) >= 24 and short in long

    cleaned: list[dict[str, Any]] = []
    for item in stages:
        if not isinstance(item, dict):
            continue
        copied = dict(item)
        s = _to_int(copied.get(start_key))
        e = _to_int(copied.get(end_key))
        if s is None or e is None:
            continue
        if e < s:
            e = s
        copied[start_key] = s
        copied[end_key] = e
        cleaned.append(copied)

    if not cleaned:
        return []

    cleaned.sort(key=lambda x: (x[start_key], x[end_key]))

    squashed: list[dict[str, Any]] = []
    for cur in cleaned:
        if not squashed:
            squashed.append(cur)
            continue

        prev = squashed[-1]

        prev_name = str(prev.get(name_key) or "").strip()
        cur_name = str(cur.get(name_key) or "").strip()
        same_name = bool(prev_name and cur_name and prev_name == cur_name)

        cur_len = int(cur[end_key]) - int(cur[start_key]) + 1
        tiny_and_similar = cur_len <= tiny_threshold and (
            _is_similar_text(prev.get(outline_key), cur.get(outline_key))
            or _is_similar_text(prev.get(summary_key), cur.get(summary_key))
        )

        if same_name or tiny_and_similar:
            prev[end_key] = max(int(prev[end_key]), int(cur[end_key]))

            prev_outline = str(prev.get(outline_key) or "")
            cur_outline = str(cur.get(outline_key) or "")
            if len(cur_outline) > len(prev_outline):
                prev[outline_key] = cur_outline

            prev_summary = str(prev.get(summary_key) or "")
            cur_summary = str(cur.get(summary_key) or "")
            if len(cur_summary) > len(prev_summary):
                prev[summary_key] = cur_summary
            continue

        squashed.append(cur)

    return squashed