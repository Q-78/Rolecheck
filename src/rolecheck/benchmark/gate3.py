"""Deterministic, label-blind Gate 3 Pilot subset construction."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Final, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from rolecheck.hashing import canonical_json_hash
from rolecheck.schemas.models import StrictModel, TaskSpec

GATE3_DOMAIN_COUNT: Final = 14
GATE3_SUBSET_SEED: Final = 2026080301
_FORBIDDEN_KEY_PARTS: Final = (
    "answer",
    "gold",
    "label",
    "rationale",
    "chain_of_thought",
    "cot_content",
)


class Gate3SubsetManifest(StrictModel):
    """One immutable, domain-bound, label-blind Pilot subset."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    name: Literal["pilot-14", "pilot-56"]
    seed: int = Field(ge=0)
    task_ids: tuple[str, ...]
    task_domains: tuple[str, ...]
    task_ids_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    domain_counts: dict[str, int]
    manifest_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("task_ids", "task_domains")
    @classmethod
    def validate_non_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not item.strip() for item in value):
            raise ValueError("Gate 3 task and domain identifiers must be non-blank")
        return value

    @model_validator(mode="after")
    def validate_manifest(self) -> Gate3SubsetManifest:
        expected_size = 14 if self.name == "pilot-14" else 56
        expected_per_domain = 1 if self.name == "pilot-14" else 4
        if len(self.task_ids) != expected_size or len(set(self.task_ids)) != expected_size:
            raise ValueError(f"{self.name} requires {expected_size} unique tasks")
        if len(self.task_domains) != expected_size:
            raise ValueError("task_domains must align one-to-one with task_ids")
        observed_counts = dict(sorted(Counter(self.task_domains).items()))
        if len(observed_counts) != GATE3_DOMAIN_COUNT:
            raise ValueError("Gate 3 manifest requires exactly 14 domains")
        if set(observed_counts.values()) != {expected_per_domain}:
            raise ValueError("Gate 3 manifest has an invalid per-domain allocation")
        if self.domain_counts != observed_counts:
            raise ValueError("domain_counts do not match task_domains")
        if self.task_ids_hash != canonical_json_hash(list(self.task_ids)):
            raise ValueError("task_ids_hash does not match task identifiers")
        expected = canonical_json_hash(
            {
                "name": self.name,
                "seed": self.seed,
                "task_ids": list(self.task_ids),
                "task_domains": list(self.task_domains),
                "task_ids_hash": self.task_ids_hash,
                "domain_counts": self.domain_counts,
            }
        )
        if self.manifest_hash != expected:
            raise ValueError("manifest_hash does not match canonical content")
        return self


def build_gate3_subset_manifests(
    tasks: Sequence[TaskSpec], *, seed: int = GATE3_SUBSET_SEED
) -> tuple[Gate3SubsetManifest, Gate3SubsetManifest]:
    """Select one and four tasks per domain without consulting outcomes."""

    if seed < 0:
        raise ValueError("Gate 3 subset seed must be non-negative")
    by_domain: dict[str, list[str]] = defaultdict(list)
    seen: set[str] = set()
    for task in tasks:
        audit_preexecution_payload(task.model_dump(mode="json"))
        if task.task_id in seen:
            raise ValueError("source task identifiers must be unique")
        seen.add(task.task_id)
        category = task.public_metadata.get("category")
        if not isinstance(category, str) or not category.strip():
            raise ValueError("every Gate 3 task requires a non-blank category")
        by_domain[category].append(task.task_id)
    if len(by_domain) != GATE3_DOMAIN_COUNT:
        raise ValueError(f"Gate 3 requires exactly {GATE3_DOMAIN_COUNT} domains")
    insufficient = sorted(domain for domain, ids in by_domain.items() if len(ids) < 4)
    if insufficient:
        raise ValueError(f"domains with fewer than four valid records: {insufficient}")
    ordered = {
        domain: sorted(
            ids,
            key=lambda task_id: (
                canonical_json_hash({"seed": seed, "domain": domain, "task_id": task_id}),
                task_id,
            ),
        )
        for domain, ids in by_domain.items()
    }
    small_pairs = tuple((ordered[domain][0], domain) for domain in sorted(ordered))
    large_pairs = tuple(
        (task_id, domain) for domain in sorted(ordered) for task_id in ordered[domain][:4]
    )
    small = _manifest("pilot-14", seed, small_pairs)
    large = _manifest("pilot-56", seed, large_pairs)
    if not set(small.task_ids).issubset(large.task_ids):
        raise AssertionError("the 56-task subset must contain the 14-task subset")
    return small, large


def audit_preexecution_payload(payload: object, path: str = "root") -> None:
    """Reject evaluation-only keys anywhere in a pre-execution artifact."""

    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if any(part in normalized for part in _FORBIDDEN_KEY_PARTS):
                raise ValueError(f"evaluation-only key at {path}.{key}")
            audit_preexecution_payload(value, f"{path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            audit_preexecution_payload(value, f"{path}[{index}]")


def _manifest(
    name: Literal["pilot-14", "pilot-56"], seed: int, pairs: tuple[tuple[str, str], ...]
) -> Gate3SubsetManifest:
    task_ids = tuple(task_id for task_id, _ in pairs)
    task_domains = tuple(domain for _, domain in pairs)
    counts = dict(sorted(Counter(task_domains).items()))
    ids_hash = canonical_json_hash(list(task_ids))
    payload = {
        "name": name,
        "seed": seed,
        "task_ids": list(task_ids),
        "task_domains": list(task_domains),
        "task_ids_hash": ids_hash,
        "domain_counts": counts,
    }
    return Gate3SubsetManifest(
        name=name,
        seed=seed,
        task_ids=task_ids,
        task_domains=task_domains,
        task_ids_hash=ids_hash,
        domain_counts=counts,
        manifest_hash=canonical_json_hash(payload),
    )
