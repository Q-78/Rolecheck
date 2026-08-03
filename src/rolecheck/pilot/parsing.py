"""Deterministic Qwen-style output separation and answer extraction."""

from __future__ import annotations

import re

from rolecheck.hashing import canonical_json_hash
from rolecheck.pilot.models import (
    AnswerParseResult,
    AnswerParseStatus,
    ParsedModelText,
)

_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"
_TERMINAL_ANSWER_RE = re.compile(r"(?:^|\n)Answer: (?P<letter>[A-J])[ \t]*\Z")


def split_model_text(raw_decoded_output: str) -> ParsedModelText:
    """Separate at most one thinking block without changing its contents."""

    close_count = raw_decoded_output.count(_THINK_CLOSE)
    open_count = raw_decoded_output.count(_THINK_OPEN)
    if close_count > 1 or open_count > 1:
        return ParsedModelText(
            final_content=raw_decoded_output.strip(),
            structure_valid=False,
            invalid_reason="multiple_thinking_markers",
        )
    if close_count == 0:
        if open_count:
            return ParsedModelText(
                final_content=raw_decoded_output.strip(),
                structure_valid=False,
                invalid_reason="unclosed_thinking_block",
            )
        return ParsedModelText(
            final_content=raw_decoded_output.strip(),
            structure_valid=True,
        )
    if open_count == 0:
        return ParsedModelText(
            final_content=raw_decoded_output.strip(),
            structure_valid=False,
            invalid_reason="thinking_close_without_open",
        )

    open_index = raw_decoded_output.index(_THINK_OPEN)
    close_index = raw_decoded_output.index(_THINK_CLOSE)
    if open_index != len(raw_decoded_output) - len(raw_decoded_output.lstrip()):
        return ParsedModelText(
            final_content=raw_decoded_output.strip(),
            structure_valid=False,
            invalid_reason="text_before_thinking_block",
        )
    if close_index < open_index:
        return ParsedModelText(
            final_content=raw_decoded_output.strip(),
            structure_valid=False,
            invalid_reason="thinking_markers_out_of_order",
        )
    reasoning_start = open_index + len(_THINK_OPEN)
    reasoning = raw_decoded_output[reasoning_start:close_index].strip()
    final_content = raw_decoded_output[close_index + len(_THINK_CLOSE) :].strip()
    return ParsedModelText(
        reasoning=reasoning,
        final_content=final_content,
        structure_valid=True,
    )


def parse_terminal_answer(
    final_content: str,
    *,
    option_count: int,
) -> AnswerParseResult:
    """Require the final visible line to be exactly ``Answer: <LETTER>``."""

    content_hash = canonical_json_hash(final_content)
    if not 2 <= option_count <= 10:
        raise ValueError("option_count must be between 2 and 10")
    match = _TERMINAL_ANSWER_RE.search(final_content)
    if match is None:
        return AnswerParseResult(
            final_content_hash=content_hash,
            option_count=option_count,
            status=AnswerParseStatus.INVALID,
            invalid_reason="missing_terminal_answer",
        )
    letter = match.group("letter")
    if ord(letter) - ord("A") >= option_count:
        return AnswerParseResult(
            final_content_hash=content_hash,
            option_count=option_count,
            status=AnswerParseStatus.INVALID,
            invalid_reason="answer_out_of_option_range",
        )
    return AnswerParseResult(
        final_content_hash=content_hash,
        option_count=option_count,
        status=AnswerParseStatus.VALID,
        answer_letter=letter,
    )
