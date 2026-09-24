"""
Yieldix Canonical JSON Serialization & Cryptographic Hasher.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    """Produces sorted, compact UTF-8 JSON bytes for deterministic hashing"""
    def _default(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_default,
    ).encode("utf-8")


def sha256_digest_hex(payload: dict[str, Any]) -> str:
    """Computes SHA-256 hex digest of a dictionary"""
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
