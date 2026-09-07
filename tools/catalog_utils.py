from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ti_parser_core import file_fingerprint


def compact_number(value: Any, digits: int = 6) -> Any:
    if not isinstance(value, float):
        return value
    rounded = round(value, digits)
    if rounded == 0:
        return 0
    if rounded.is_integer():
        return int(rounded)
    return rounded


def read_localization_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    with path.open("r", encoding="utf-8-sig") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def source_fingerprint(path: Path) -> dict[str, Any]:
    fingerprint = file_fingerprint(path)
    if not fingerprint:
        return {"file": path.name}
    return {
        "file": path.name,
        "size": fingerprint["size"],
        "mtime_ns": fingerprint["mtime_ns"],
    }


def parse_languages(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def write_json_output(path: Path, value: Any) -> Path:
    return write_utf8_lf(path, json.dumps(value, ensure_ascii=False, indent=2))


def write_text_output(path: Path, content: str) -> Path:
    return write_utf8_lf(path, content)


def write_utf8_lf(path: Path, content: str) -> Path:
    """Write deterministic UTF-8 bytes with LF endings and one trailing LF."""

    path.parent.mkdir(parents=True, exist_ok=True)
    canonical = content.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"
    path.write_bytes(canonical.encode("utf-8"))
    return path
