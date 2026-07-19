from typing import Any

from app.schemas.chapter_review import ReviewRunRequest


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(_to_text(item) for item in value if _to_text(item))
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            rendered = _to_text(item)
            if rendered:
                lines.append(f"{key}: {rendered}")
        return "\n".join(lines)
    return str(value)


def build_review_prompt(request: ReviewRunRequest) -> str:
    parts: list[str] = [
        "[Review Target]",
        f"Title: {request.title}",
        f"Review type: {request.review_type}",
        f"Review profile: {request.review_profile}",
        f"Target field: {request.target_field}",
    ]

    if request.context_info:
        parts.extend(["", "[Reference Context]", request.context_info.strip()])
    if request.facts_info:
        parts.extend(["", "[Facts Subgraph]", request.facts_info.strip()])

    target_text = _to_text(request.target_text)
    parts.extend(["", "[Content to Review]", target_text or "(empty content)"])
    return "\n".join(parts)
