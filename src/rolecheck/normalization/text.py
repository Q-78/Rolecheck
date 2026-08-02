"""Text helpers that preserve source offsets while normalizing only for matching."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from rolecheck.normalization.models import DetectedLanguage, SourceSpan
from rolecheck.normalization.rules import LIST_MARKER_RE


@dataclass(frozen=True, slots=True)
class SourceLine:
    text: str
    start: int
    end: int
    normalized: str

    def stripped_span(self, *, remove_list_marker: bool = False) -> SourceSpan | None:
        leading = len(self.text) - len(self.text.lstrip())
        trailing = len(self.text.rstrip())
        if leading == trailing:
            return None

        value = self.text[leading:trailing]
        if remove_list_marker:
            marker = LIST_MARKER_RE.match(value)
            if marker is not None:
                leading += marker.end()
                value = self.text[leading:trailing]
        if not value:
            return None
        return SourceSpan(start=self.start + leading, end=self.start + trailing, text=value)


def source_lines(raw_text: str) -> list[SourceLine]:
    lines: list[SourceLine] = []
    offset = 0
    for with_ending in raw_text.splitlines(keepends=True):
        text = with_ending.rstrip("\r\n")
        lines.append(
            SourceLine(
                text=text,
                start=offset,
                end=offset + len(text),
                normalized=unicodedata.normalize("NFKC", text),
            )
        )
        offset += len(with_ending)
    if raw_text and not lines:
        lines.append(
            SourceLine(
                text=raw_text,
                start=0,
                end=len(raw_text),
                normalized=unicodedata.normalize("NFKC", raw_text),
            )
        )
    return lines


def detect_language(raw_text: str) -> DetectedLanguage:
    han_count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", raw_text))
    latin_count = len(re.findall(r"[A-Za-z]", raw_text))
    if han_count and latin_count:
        return DetectedLanguage.MIXED
    if han_count:
        return DetectedLanguage.CHINESE
    if latin_count:
        return DetectedLanguage.ENGLISH
    return DetectedLanguage.UNKNOWN
