"""Strict JSON parsing without repair, retries, or model calls."""

from __future__ import annotations

import json

from pydantic import ValidationError

from rolecheck.hashing import canonical_json_hash
from rolecheck.signal.models import (
    OptionScoreVector,
    StructuredRoleOutput,
    StructuredRoleOutputParseResult,
)


def parse_structured_role_output(
    raw: str, option_letters: list[str]
) -> StructuredRoleOutputParseResult:
    raw_hash = canonical_json_hash(raw)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return StructuredRoleOutputParseResult(
            status="invalid", raw_output_hash=raw_hash, invalid_reason=f"invalid_json:{exc.msg}"
        )
    if not isinstance(payload, dict):
        reason = "root_must_be_object"
    else:
        try:
            scores = payload.get("option_scores")
            if not isinstance(scores, dict) or set(scores) != set(option_letters):
                raise ValueError("option set mismatch")
            output = StructuredRoleOutput(
                option_scores=OptionScoreVector(scores=scores),
                key_evidence=payload.get("key_evidence", []),
            )
            if set(payload) != {"option_scores", "key_evidence"}:
                raise ValueError("unexpected or missing root field")
            return StructuredRoleOutputParseResult(
                status="valid",
                raw_output_hash=raw_hash,
                output=output,
                output_hash=output.canonical_hash,
            )
        except (ValidationError, ValueError, TypeError) as exc:
            reason = f"schema_invalid:{exc}"
    return StructuredRoleOutputParseResult(
        status="invalid", raw_output_hash=raw_hash, invalid_reason=reason
    )
