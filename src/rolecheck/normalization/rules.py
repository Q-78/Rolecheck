"""Versioned, language-neutral rule tables for the v0.1 normalizer."""

from __future__ import annotations

import re
import unicodedata
from typing import Final

NORMALIZER_VERSION: Final = "v0.1"


def canonical_heading(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


_ALIASES: dict[str, tuple[str, ...]] = {
    "goal": (
        "goal",
        "objective",
        "role goal",
        "\u76ee\u6807",
        "\u89d2\u8272\u76ee\u6807",
    ),
    "responsibilities": (
        "responsibilities",
        "responsibility",
        "duties",
        "tasks",
        "\u804c\u8d23",
        "\u4efb\u52a1",
    ),
    "success_criteria": (
        "success criteria",
        "definition of done",
        "acceptance criteria",
        "\u6210\u529f\u6807\u51c6",
        "\u5b8c\u6210\u6807\u51c6",
        "\u9a8c\u6536\u6807\u51c6",
    ),
    "non_goals": (
        "non-goals",
        "non goals",
        "out of scope",
        "\u975e\u76ee\u6807",
        "\u8303\u56f4\u5916",
    ),
    "prohibited_behaviors": (
        "prohibited behaviors",
        "prohibited",
        "must not",
        "do not",
        "\u7981\u6b62\u884c\u4e3a",
        "\u7981\u6b62",
        "\u4e0d\u5f97",
    ),
    "priority_rules": (
        "priority rules",
        "priorities",
        "\u4f18\u5148\u7ea7",
        "\u4f18\u5148\u89c4\u5219",
    ),
    "required_inputs": (
        "required inputs",
        "required input",
        "\u5fc5\u9700\u8f93\u5165",
        "\u5fc5\u8981\u8f93\u5165",
    ),
    "optional_inputs": (
        "optional inputs",
        "optional input",
        "\u53ef\u9009\u8f93\u5165",
    ),
    "outputs": ("outputs", "output", "deliverables", "\u8f93\u51fa", "\u4ea4\u4ed8\u7269"),
    "context_assumptions": (
        "context assumptions",
        "assumptions",
        "\u4e0a\u4e0b\u6587\u5047\u8bbe",
        "\u5047\u8bbe",
    ),
    "can_override": ("can override", "override", "\u53ef\u8986\u76d6"),
    "requires_approval_from": (
        "requires approval from",
        "approval",
        "\u9700\u8981\u6279\u51c6",
        "\u6279\u51c6\u65b9",
    ),
    "decision_scope": ("decision scope", "\u51b3\u7b56\u8303\u56f4"),
    "conflict_resolution_rule": (
        "conflict resolution",
        "conflict resolution rule",
        "\u51b2\u7a81\u89e3\u51b3",
        "\u51b2\u7a81\u89c4\u5219",
    ),
    "downstream_consumers": ("consumers", "downstream consumers", "\u4e0b\u6e38\u6d88\u8d39\u8005"),
    "termination_signal": ("termination signal", "stop signal", "\u7ec8\u6b62\u4fe1\u53f7"),
    "handoff_conditions": ("handoff", "handoff conditions", "\u4ea4\u63a5\u6761\u4ef6"),
    "required_capabilities": (
        "required capabilities",
        "capabilities",
        "\u6240\u9700\u80fd\u529b",
        "\u80fd\u529b\u8981\u6c42",
    ),
}

HEADING_TO_FIELD: Final = {
    canonical_heading(alias): field for field, aliases in _ALIASES.items() for alias in aliases
}

LIST_FIELDS: Final = frozenset(
    {
        "responsibilities",
        "success_criteria",
        "non_goals",
        "prohibited_behaviors",
        "priority_rules",
        "context_assumptions",
        "can_override",
        "requires_approval_from",
        "decision_scope",
        "downstream_consumers",
        "handoff_conditions",
        "required_capabilities",
    }
)

SCALAR_FIELDS: Final = frozenset({"goal", "conflict_resolution_rule", "termination_signal"})

LIST_MARKER_RE: Final = re.compile(
    r"^\s*(?:[-*+]\s+|\d+[.)\u3001]\s*|[\u4e00-\u9fff][\u3001.]\s*|[\uff08(]\d+[\uff09)]\s*)"
)
MARKDOWN_HEADING_RE: Final = re.compile(r"^\s*#{1,6}\s*(?P<label>.+?)\s*$")
LABEL_RE: Final = re.compile(r"^\s*(?P<label>[^:\uff1a]{1,48})[:\uff1a]\s*(?P<value>.*)$")
ROLE_PATTERNS: Final = (
    re.compile(r"^\s*you are (?:an?|the) (?P<value>[^.\n]{1,80})\.?\s*$", re.IGNORECASE),
    re.compile(
        r"^\s*\u4f60\u662f(?:\u4e00\u540d|\u4e00\u4e2a)?(?P<value>[^\u3002\n]{1,40})\u3002?\s*$"
    ),
)
RESPONSIBILITY_PATTERNS: Final = (
    re.compile(r"^\s*(?:you )?must\s+.+", re.IGNORECASE),
    re.compile(r"^\s*(?:\u4f60)?(?:\u8d1f\u8d23|\u5fc5\u987b)\s*.+"),
)
PROHIBITION_PATTERNS: Final = (
    re.compile(r"^\s*(?:you )?(?:must not|do not|never)\s+.+", re.IGNORECASE),
    re.compile(r"^\s*(?:\u4e0d\u5f97|\u7981\u6b62|\u4e25\u7981)\s*.+"),
)
