"""Stable hashing helpers used by manifests and mock records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence


def sha256_text(value: str) -> str:
    """Return a namespaced SHA-256 digest for text."""

    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def canonical_json_hash(value: object) -> str:
    """Hash a JSON-compatible object with stable key ordering."""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def derive_seed(parent_seed: int, namespace: str, stable_id: str) -> int:
    """Derive a deterministic unsigned 32-bit seed."""

    raw = f"{parent_seed}|{namespace}|{stable_id}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], byteorder="big", signed=False)


def normalize_for_json(value: object) -> object:
    """Recursively normalize common containers before canonical hashing."""

    if isinstance(value, Mapping):
        return {str(key): normalize_for_json(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize_for_json(item) for item in value]
    return value
