"""Conservative, deterministic Role Contract Normalizer v0.1."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, TypeAdapter

from rolecheck.hashing import canonical_json_hash, sha256_text
from rolecheck.normalization.models import (
    CORE_CONTRACT_FIELDS,
    NORMALIZABLE_FIELDS,
    DetectedLanguage,
    FieldNormalization,
    InputSpecDraft,
    NormalizationResult,
    NormalizationSource,
    OutputSpecDraft,
    RoleContractDraft,
    SourceKind,
    SourceSpan,
    normalization_content,
    promote_draft,
)
from rolecheck.normalization.rules import (
    HEADING_TO_FIELD,
    LABEL_RE,
    LIST_FIELDS,
    MARKDOWN_HEADING_RE,
    NORMALIZER_VERSION,
    PROHIBITION_PATTERNS,
    RESPONSIBILITY_PATTERNS,
    ROLE_PATTERNS,
    SCALAR_FIELDS,
    canonical_heading,
)
from rolecheck.normalization.text import SourceLine, detect_language, source_lines
from rolecheck.schemas import SourceType

_EXPLICIT_FIELD_NAMES = frozenset(NORMALIZABLE_FIELDS) - {"role_name"}
_FORMAT_PATTERNS = (
    ("json", re.compile(r"\bjson\b", re.IGNORECASE)),
    ("yaml", re.compile(r"\bya?ml\b", re.IGNORECASE)),
    ("xml", re.compile(r"\bxml\b", re.IGNORECASE)),
    ("markdown", re.compile(r"\bmarkdown\b", re.IGNORECASE)),
    ("plain_text", re.compile(r"\bplain[ -]?text\b|\u7eaf\u6587\u672c", re.IGNORECASE)),
)
_CODE_FENCE_RE = re.compile(r"^\s*(?P<marker>`{3,}|~{3,})")


@dataclass(frozen=True, slots=True)
class _Candidate:
    value: object
    status: SourceType
    spans: tuple[SourceSpan, ...]
    confidence: float
    parse_risk: float
    rule_id: str


def _value_span(line: SourceLine, value_start: int, value_end: int) -> SourceSpan | None:
    raw = line.text[value_start:value_end]
    leading = len(raw) - len(raw.lstrip())
    trailing = len(raw.rstrip())
    if leading == trailing:
        return None
    start = line.start + value_start + leading
    end = line.start + value_start + trailing
    return SourceSpan(
        start=start,
        end=end,
        text=line.text[value_start + leading : value_start + trailing],
    )


def _detect_declared_format(text: str) -> str | None:
    """Recognize an explicit format token; do not parse or infer a schema."""

    for name, pattern in _FORMAT_PATTERNS:
        if pattern.search(text):
            return name
    return None


def _spec_candidate(field: str, spans: list[SourceSpan]) -> _Candidate:
    if field in {"required_inputs", "optional_inputs"}:
        required = field == "required_inputs"
        value: object = [
            InputSpecDraft(
                required=required,
                format=_detect_declared_format(span.text),
                description=span.text,
            )
            for span in spans
        ]
    else:
        value = [
            OutputSpecDraft(
                format=_detect_declared_format(span.text),
                description=span.text,
            )
            for span in spans
        ]
    return _Candidate(
        value=value,
        status=SourceType.PARSED,
        spans=tuple(spans),
        confidence=0.95,
        parse_risk=0.05,
        rule_id="section.exact.v0.1",
    )


def _extract_prompt(
    raw_prompt: str,
) -> tuple[dict[str, _Candidate], set[int], list[str]]:
    lines = source_lines(raw_prompt)
    collected: dict[str, list[SourceSpan]] = {}
    section_counts: dict[str, int] = {}
    inline_fields: set[str] = set()
    recognized_lines: set[int] = set()
    warnings: list[str] = []
    current_field: str | None = None
    fence_character: str | None = None
    fence_length = 0

    for index, line in enumerate(lines):
        stripped = line.normalized.strip()
        fence = _CODE_FENCE_RE.match(stripped)
        if fence is not None:
            marker = fence.group("marker")
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0
            current_field = None
            continue
        if fence_character is not None:
            continue
        if not stripped:
            current_field = None
            continue

        markdown = MARKDOWN_HEADING_RE.match(line.text)
        if markdown is not None:
            field = HEADING_TO_FIELD.get(canonical_heading(markdown.group("label")))
            current_field = field
            if field is not None:
                section_counts[field] = section_counts.get(field, 0) + 1
                recognized_lines.add(index)
            continue

        label = LABEL_RE.match(line.text)
        if label is not None:
            field = HEADING_TO_FIELD.get(canonical_heading(label.group("label")))
            if field is not None:
                current_field = field
                section_counts[field] = section_counts.get(field, 0) + 1
                recognized_lines.add(index)
                span = _value_span(line, label.start("value"), label.end("value"))
                if span is not None:
                    collected.setdefault(field, []).append(span)
                continue
            current_field = None

        if current_field is not None:
            span = line.stripped_span(remove_list_marker=True)
            if span is not None:
                collected.setdefault(current_field, []).append(span)
                recognized_lines.add(index)
            continue

        role_match = next(
            (match for pattern in ROLE_PATTERNS if (match := pattern.match(line.text))),
            None,
        )
        if role_match is not None:
            span = _value_span(line, role_match.start("value"), role_match.end("value"))
            if span is not None:
                collected.setdefault("role_name", []).append(span)
                inline_fields.add("role_name")
                recognized_lines.add(index)
                continue

        if any(pattern.match(line.text) for pattern in PROHIBITION_PATTERNS):
            span = line.stripped_span()
            if span is not None:
                collected.setdefault("prohibited_behaviors", []).append(span)
                inline_fields.add("prohibited_behaviors")
                recognized_lines.add(index)
                continue
        if any(pattern.match(line.text) for pattern in RESPONSIBILITY_PATTERNS):
            span = line.stripped_span()
            if span is not None:
                collected.setdefault("responsibilities", []).append(span)
                inline_fields.add("responsibilities")
                recognized_lines.add(index)

    if fence_character is not None:
        warnings.append("unclosed code fence: enclosed text was not parsed")

    candidates: dict[str, _Candidate] = {}
    for field, spans in collected.items():
        spans.sort(key=lambda item: item.start)
        inline_only = field in inline_fields and section_counts.get(field, 0) == 0
        confidence = 0.8 if inline_only else 0.95
        parse_risk = 0.2 if inline_only else 0.05
        rule_id = "inline.directive.v0.1" if inline_only else "section.exact.v0.1"

        if field in {"required_inputs", "optional_inputs", "outputs"}:
            candidates[field] = _spec_candidate(field, spans)
        elif field in LIST_FIELDS:
            candidates[field] = _Candidate(
                value=[span.text for span in spans],
                status=SourceType.PARSED,
                spans=tuple(spans),
                confidence=confidence,
                parse_risk=parse_risk,
                rule_id=rule_id,
            )
        elif field in SCALAR_FIELDS or field == "role_name":
            distinct = {
                unicodedata.normalize("NFKC", span.text).strip().casefold() for span in spans
            }
            repeated_sections = section_counts.get(field, 0) > 1
            if repeated_sections and len(distinct) > 1:
                candidates[field] = _Candidate(
                    value=None,
                    status=SourceType.UNKNOWN,
                    spans=tuple(spans),
                    confidence=0.0,
                    parse_risk=1.0,
                    rule_id="scalar.conflict.v0.1",
                )
            elif len(spans) == 1 or repeated_sections:
                candidates[field] = _Candidate(
                    value=spans[0].text,
                    status=SourceType.PARSED,
                    spans=tuple(spans),
                    confidence=confidence,
                    parse_risk=parse_risk,
                    rule_id=rule_id,
                )
            else:
                start = spans[0].start
                end = spans[-1].end
                candidates[field] = _Candidate(
                    value=raw_prompt[start:end],
                    status=SourceType.PARSED,
                    spans=tuple(spans),
                    confidence=confidence,
                    parse_risk=parse_risk,
                    rule_id=rule_id,
                )

    return candidates, recognized_lines, warnings


def _comparable_field_value(field: str, value: object) -> object:
    annotation = RoleContractDraft.model_fields[field].annotation
    adapter: TypeAdapter[Any] = TypeAdapter(annotation)
    validated = adapter.validate_python(value)
    dumped = adapter.dump_python(validated, mode="json", exclude_none=True)
    if isinstance(dumped, BaseModel):
        return dumped.model_dump(mode="json", exclude_none=True)
    return dumped


class RoleContractNormalizer:
    """Extract source-supported facts without authoring or repairing a role."""

    version = NORMALIZER_VERSION

    def normalize(
        self,
        *,
        role_id: str,
        source_initializer: str,
        raw_prompt: str,
        role_name: str | None = None,
        role_version: str | None = None,
        source_node_id: str | None = None,
        source_kind: SourceKind = SourceKind.PROMPT,
        explicit_fields: dict[str, Any] | None = None,
    ) -> NormalizationResult:
        explicit = dict(explicit_fields or {})
        invalid_fields = set(explicit) - _EXPLICIT_FIELD_NAMES
        if invalid_fields:
            raise ValueError(f"unsupported explicit role fields: {sorted(invalid_fields)}")

        parsed, recognized_lines, parser_warnings = _extract_prompt(raw_prompt)
        draft_data: dict[str, object] = {
            "role_id": role_id,
            "role_name": role_name,
            "role_version": role_version if role_version is not None else "v1",
            "source_initializer": source_initializer,
            "source_node_id": source_node_id,
            "raw_prompt": raw_prompt,
            "prompt_hash": sha256_text(raw_prompt),
        }
        draft_data.update(explicit)

        conflicts: list[str] = []
        for field, parsed_candidate in parsed.items():
            has_explicit_value = (
                field == "role_name" and role_name is not None
            ) or field in explicit
            if has_explicit_value:
                explicit_value = role_name if field == "role_name" else explicit[field]
                if parsed_candidate.value is not None and (
                    _comparable_field_value(field, explicit_value)
                    != _comparable_field_value(field, parsed_candidate.value)
                ):
                    conflicts.append(field)
                continue
            draft_data[field] = parsed_candidate.value

        draft = RoleContractDraft.model_validate(draft_data)
        contract, contract_validation_errors = promote_draft(draft)
        source = NormalizationSource(
            source_initializer=source_initializer,
            source_node_id=source_node_id,
            source_kind=source_kind,
            raw_text=raw_prompt,
            source_hash=sha256_text(raw_prompt),
        )

        metadata: list[FieldNormalization] = []
        for field in NORMALIZABLE_FIELDS:
            candidate: _Candidate | None = parsed.get(field)
            if field == "role_name" and role_name is not None:
                status = SourceType.EXPLICIT
                candidate = None
            elif field in explicit:
                status = (
                    SourceType.EXPLICIT
                    if explicit[field] is not None
                    else SourceType.UNKNOWN
                )
                candidate = None
            elif candidate is not None:
                status = candidate.status
            else:
                status = SourceType.MISSING

            if status is SourceType.MISSING:
                confidence, risk, spans, rule_id = 0.0, 1.0, [], None
            elif status is SourceType.UNKNOWN:
                confidence, risk = 0.0, 1.0
                spans = list(candidate.spans) if candidate is not None else []
                rule_id = candidate.rule_id if candidate is not None else "explicit.unknown.v0.1"
            elif candidate is not None:
                confidence, risk = candidate.confidence, candidate.parse_risk
                spans, rule_id = list(candidate.spans), candidate.rule_id
            else:
                confidence, risk, spans = 1.0, 0.0, []
                rule_id = (
                    "argument.explicit.v0.1"
                    if field == "role_name"
                    else "structured.explicit.v0.1"
                )

            notes = [
                "structured value overrides differing prompt parse"
            ] if field in conflicts else []
            metadata.append(
                FieldNormalization(
                    field_path=field,
                    status=status,
                    source_spans=spans,
                    confidence=confidence,
                    parse_risk=risk,
                    rule_id=rule_id,
                    notes=notes,
                )
            )

        metadata_by_path = {item.field_path: item for item in metadata}
        missing_fields = [
            field
            for field in NORMALIZABLE_FIELDS
            if metadata_by_path[field].status is SourceType.MISSING
        ]
        unknown_fields = [
            field
            for field in NORMALIZABLE_FIELDS
            if metadata_by_path[field].status is SourceType.UNKNOWN
        ]
        warnings = list(parser_warnings)
        warnings.extend(
            f"missing core contract field: {field}"
            for field in CORE_CONTRACT_FIELDS
            if field in missing_fields
        )
        warnings.extend(
            f"conflicting structured and prompt values: {field}" for field in conflicts
        )
        warnings.extend(f"ambiguous field: {field}" for field in unknown_fields)
        if contract is None:
            warnings.append("draft is not a complete strict RoleContract")

        unparsed_segments = []
        for index, line in enumerate(source_lines(raw_prompt)):
            if index not in recognized_lines:
                span = line.stripped_span()
                if span is not None:
                    unparsed_segments.append(span)

        contract_parse_risk = max(
            metadata_by_path[field].parse_risk for field in CORE_CONTRACT_FIELDS
        )
        detected_language: DetectedLanguage = detect_language(raw_prompt)
        content = normalization_content(
            normalizer_version=self.version,
            source=source,
            detected_language=detected_language,
            draft=draft,
            contract=contract,
            field_metadata=metadata,
            missing_fields=missing_fields,
            unknown_fields=unknown_fields,
            conflicting_fields=sorted(set(conflicts)),
            unparsed_segments=unparsed_segments,
            warnings=warnings,
            contract_validation_errors=contract_validation_errors,
            contract_parse_risk=contract_parse_risk,
        )
        return NormalizationResult(
            normalization_id=canonical_json_hash(content),
            normalizer_version=self.version,
            source=source,
            detected_language=detected_language,
            draft=draft,
            contract=contract,
            field_metadata=metadata,
            missing_fields=missing_fields,
            unknown_fields=unknown_fields,
            conflicting_fields=sorted(set(conflicts)),
            unparsed_segments=unparsed_segments,
            warnings=warnings,
            contract_validation_errors=contract_validation_errors,
            contract_parse_risk=contract_parse_risk,
        )
