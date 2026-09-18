"""Integrity helpers for standalone packaged catalogs.

These catalogs predate the runtime-catalog bundle envelope.  Keep their
schemas stable while giving each catalog an embedded, deterministic payload
fingerprint.  Source-file mtimes are provenance only and deliberately do not
participate in the fingerprint, so rebuilding unchanged templates is stable.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def payload_for_fingerprint(catalog: dict[str, Any]) -> dict[str, Any]:
    """Return the catalog payload excluding its checksum and volatile mtimes."""

    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: normalize(item)
                for key, item in value.items()
                if key not in {"payloadFingerprint", "mtime_ns"}
            }
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    return normalize(catalog)


def value_fingerprint(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def payload_fingerprint(catalog: dict[str, Any]) -> str:
    return value_fingerprint(payload_for_fingerprint(catalog))


def attach_payload_fingerprint(catalog: dict[str, Any]) -> dict[str, Any]:
    catalog["payloadFingerprint"] = payload_fingerprint(catalog)
    return catalog
