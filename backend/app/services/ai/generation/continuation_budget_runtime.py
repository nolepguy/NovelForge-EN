from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Optional

from app.schemas.ai import ContinuationRequest


_SENTENCE_ENDINGS = "。！？!?…\n"
_OUTLINE_BOUNDARY_HINT = (
    "- Outline boundary takes priority over the word-count target: if this chapter's outline content is finished before the word count is reached, "
    "appropriately enrich details, actions, dialogue, and inner monologue within the scope of this chapter's outline; never spill into the next chapter's content to pad the word count."
)


@dataclass(frozen=True)
class ContinuationRoundPlan:
    mode: str
    round_index: int
    max_rounds: int
    rounds_left: int
    current_word_count: int
    target_word_count: Optional[int]
    remaining_word_count: Optional[int]
    suggested_word_count: Optional[int]
    is_final_round: bool
    max_tokens: Optional[int]
    hard_word_limit: Optional[int]
    should_warn_wrap_up: bool


@dataclass(frozen=True)
class ContinuationTrimResult:
    text: str
    trimmed: bool


def count_text_units(text: str | None) -> int:
    # Word counting: count whitespace-delimited tokens.
    # str.split() with no args splits on any whitespace run and discards
    # leading/trailing empty strings, so len(...) yields the word count.
    # (Previously this returned the non-whitespace character count via
    # len("".join((text or "").split())).)
    if not text:
        return 0
    return len(text.split())


def normalize_word_control_mode(request: ContinuationRequest) -> str:
    raw_mode = str(getattr(request, "word_control_mode", "") or "").strip().lower()
    target_word_count = getattr(request, "target_word_count", None)

    if raw_mode not in {"prompt_only", "balanced"}:
        raw_mode = "balanced" if target_word_count else "prompt_only"

    if not target_word_count and raw_mode != "prompt_only":
        return "prompt_only"
    return raw_mode


def estimate_required_call_count(request: ContinuationRequest) -> int:
    mode = normalize_word_control_mode(request)
    if mode == "prompt_only":
        return 1

    current_word_count = _resolve_current_word_count(request)
    remaining_word_count = _resolve_remaining_word_count(request, current_word_count)
    return _estimate_round_count_from_remaining(mode, remaining_word_count)


def build_round_plan(
    request: ContinuationRequest,
    current_word_count: int,
    round_index: int,
) -> ContinuationRoundPlan:
    mode = normalize_word_control_mode(request)
    target_word_count = getattr(request, "target_word_count", None)
    remaining_word_count = _resolve_remaining_word_count(request, current_word_count)
    max_rounds = _estimate_round_cap(mode, target_word_count, current_word_count)

    if mode == "prompt_only":
        return ContinuationRoundPlan(
            mode=mode,
            round_index=1,
            max_rounds=1,
            rounds_left=1,
            current_word_count=current_word_count,
            target_word_count=target_word_count,
            remaining_word_count=remaining_word_count,
            suggested_word_count=remaining_word_count if remaining_word_count > 0 else None,
            is_final_round=True,
            max_tokens=request.max_tokens,
            hard_word_limit=None,
            should_warn_wrap_up=False,
        )

    rounds_left = max(1, max_rounds - round_index + 1)
    effective_remaining = remaining_word_count if remaining_word_count > 0 else 280
    close_mode = effective_remaining <= 1000 or rounds_left <= 3

    if close_mode:
        suggested_word_count = _plan_close_suggestion(
            remaining_word_count=effective_remaining,
            rounds_left=rounds_left,
        )
        is_final_round = rounds_left == 1
    else:
        advance_rounds_left = max(min(rounds_left - 3, 2), 1)
        suggested_word_count = _plan_advance_suggestion(
            remaining_word_count=effective_remaining,
            advance_rounds_left=advance_rounds_left,
        )
        is_final_round = False

    max_tokens = _resolve_round_max_tokens(request.max_tokens, suggested_word_count, mode)
    hard_word_limit = None if is_final_round else _resolve_round_hard_limit(
        suggested_word_count=suggested_word_count,
        remaining_word_count=effective_remaining,
        mode=mode,
    )
    return ContinuationRoundPlan(
        mode=mode,
        round_index=round_index,
        max_rounds=max_rounds,
        rounds_left=rounds_left,
        current_word_count=current_word_count,
        target_word_count=target_word_count,
        remaining_word_count=remaining_word_count,
        suggested_word_count=suggested_word_count,
        is_final_round=is_final_round,
        max_tokens=max_tokens,
        hard_word_limit=hard_word_limit,
        should_warn_wrap_up=(not is_final_round and rounds_left <= 3),
    )


def build_budget_hint_text(
    plan: ContinuationRoundPlan,
    continuation_guidance: str | None = None,
    *,
    include_outline_boundary: bool = True,
) -> str:
    lines: list[str] = ["【Continuation budget】", f"- Current total word count: {plan.current_word_count} words"]

    if plan.target_word_count is not None:
        lines.append(f"- Target total word count: {plan.target_word_count} words")
    if plan.remaining_word_count is not None:
        lines.append(f"- Remaining word count: about {max(plan.remaining_word_count, 0)} words")
    if plan.mode != "prompt_only":
        if plan.is_final_round:
            lines.append(f"- Current round: round {plan.round_index} (wrapping up this round)")
        else:
            lines.append(f"- Current round: round {plan.round_index} (estimated up to {plan.max_rounds} rounds)")
    if plan.suggested_word_count is not None and plan.mode != "prompt_only":
        lines.append(f"- Suggested scale for this round: about {plan.suggested_word_count} words")
    if plan.hard_word_limit is not None:
        lines.append(f"- Hard cap for this round: about {plan.hard_word_limit} words (exceeding it stops the round early)")

    guidance = (continuation_guidance or "").strip()
    if guidance:
        lines.append(f"- Continuation guidance: {guidance}")

    if plan.mode == "prompt_only":
        lines.append("- Currently in prompt-only constraint mode: the target word count is for reference only; prioritize style and coherence.")
    else:
        lines.append("- Currently in smart word-count control mode: the first two rounds prioritize advancing the plot; subsequent rounds gradually tighten the word count and complete the ending.")

    if include_outline_boundary:
        lines.append(_OUTLINE_BOUNDARY_HINT)

    if plan.should_warn_wrap_up:
        if plan.rounds_left >= 3:
            lines.append("- Entering the final-thousand-words wrap-up stage: start compressing subplots, reusing information, and reserve room for the subsequent 600 / 300 / 100 wrap-up cadence.")
        elif plan.rounds_left == 2:
            lines.append("- Only the last two rounds remain: clearly accelerate the wrap-up cadence, do not open new subplots, and try to compress the last round to about 100 words.")

    if plan.mode != "prompt_only" and plan.is_final_round:
        lines.append("- This is the final round: do only ending wrap-up, strictly control word count, do not open new subplots, do not noticeably exceed the budget; the ending should feel natural and leave some aftertaste or a slight hook.")

    return "\n".join(lines).strip()


def trim_generated_text(text: str, plan: ContinuationRoundPlan) -> ContinuationTrimResult:
    if plan.mode == "prompt_only" or not text.strip():
        return ContinuationTrimResult(text=text, trimmed=False)

    remaining_word_count = plan.remaining_word_count
    if remaining_word_count is None:
        return ContinuationTrimResult(text=text, trimmed=False)

    preferred_limit = max(remaining_word_count, 160)
    soft_limit = max(preferred_limit, remaining_word_count + 120)
    actual_units = count_text_units(text)
    if actual_units <= soft_limit:
        return ContinuationTrimResult(text=text, trimmed=False)

    cut_index = _find_sentence_cut(text, preferred_limit)
    if cut_index is None:
        cut_index = _find_sentence_cut(text, soft_limit)
    if cut_index is None:
        cut_index = _find_hard_cut(text, soft_limit)

    if cut_index is None or cut_index <= 0:
        return ContinuationTrimResult(text=text, trimmed=False)

    trimmed_text = text[:cut_index].rstrip()
    return ContinuationTrimResult(
        text=trimmed_text or text[:cut_index],
        trimmed=trimmed_text != text,
    )


def _resolve_current_word_count(request: ContinuationRequest) -> int:
    existing_word_count = getattr(request, "existing_word_count", None)
    if existing_word_count is not None and existing_word_count >= 0:
        return existing_word_count
    return count_text_units(getattr(request, "previous_content", ""))


def _resolve_remaining_word_count(request: ContinuationRequest, current_word_count: int) -> int:
    target_word_count = getattr(request, "target_word_count", None)
    if target_word_count is None:
        return 0
    return max(target_word_count - current_word_count, 0)


def _resolve_round_max_tokens(
    request_max_tokens: Optional[int],
    suggested_word_count: Optional[int],
    mode: str,
) -> Optional[int]:
    if suggested_word_count is None:
        return request_max_tokens

    token_factor = 2.4
    computed_limit = max(256, int(suggested_word_count * token_factor))
    if request_max_tokens is None or request_max_tokens <= 0:
        return computed_limit
    return min(request_max_tokens, computed_limit)


def _resolve_round_hard_limit(
    *,
    suggested_word_count: Optional[int],
    remaining_word_count: int,
    mode: str,
) -> Optional[int]:
    if suggested_word_count is None:
        return None
    tolerance = 1.10
    return min(remaining_word_count, max(120, int(suggested_word_count * tolerance)))


def _find_sentence_cut(text: str, limit_units: int) -> Optional[int]:
    # Count whitespace-delimited words incrementally (a new word begins at the
    # first non-space char following a space). This keeps cut-finding consistent
    # with count_text_units, which now counts words rather than characters.
    words = 0
    in_word = False
    sentence_cut: Optional[int] = None
    for idx, char in enumerate(text):
        if char.isspace():
            in_word = False
        elif not in_word:
            words += 1
            in_word = True
        if char in _SENTENCE_ENDINGS and words <= limit_units:
            sentence_cut = idx + 1
        if words > limit_units:
            break
    return sentence_cut


def _find_hard_cut(text: str, limit_units: int) -> Optional[int]:
    # Word-based hard cut: return the index at the start of the
    # (limit_units + 1)-th word so that text[:idx] contains the first
    # limit_units complete words (plus any trailing whitespace, which the
    # caller strips). If the text has limit_units or fewer words, return the
    # whole text length.
    if not text:
        return None
    words = 0
    in_word = False
    for idx, char in enumerate(text):
        if char.isspace():
            in_word = False
        elif not in_word:
            words += 1
            in_word = True
            if words > limit_units:
                return idx
    return len(text)


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _estimate_round_count_from_remaining(mode: str, remaining_word_count: int) -> int:
    if remaining_word_count <= 0:
        return 1

    return 3 if remaining_word_count <= 1000 else 5


def _estimate_round_cap(
    mode: str,
    target_word_count: Optional[int],
    current_word_count: int,
) -> int:
    if mode == "prompt_only":
        return 1

    target = target_word_count or current_word_count or 3000

    return 3 if target <= 1000 else 5


def _plan_advance_suggestion(
    *,
    remaining_word_count: int,
    advance_rounds_left: int,
) -> int:
    advance_budget = max(remaining_word_count - 1000, 0)
    suggestion = ceil(advance_budget / max(1, advance_rounds_left))
    upper = 2200
    lower = 220
    return _clamp(suggestion, lower, upper)


def _plan_close_suggestion(
    *,
    remaining_word_count: int,
    rounds_left: int,
) -> int:
    if rounds_left >= 3:
        return _clamp(min(600, max(remaining_word_count - 400, 0)), 180, 600)
    if rounds_left == 2:
        return _clamp(min(300, max(remaining_word_count - 100, 0)), 120, 300)
    return _clamp(min(remaining_word_count, 100), 60, 100)