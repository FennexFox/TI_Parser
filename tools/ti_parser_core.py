"""Shared save loading, indexing, and serialization helpers."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CACHE_DIR = ".ti_cache"
SAVE_GLOB = "*.gz"


@dataclass(frozen=True)
class IndexedState:
    data: dict[str, Any]
    gamestates: dict[str, list[dict[str, Any]]]
    id_index: dict[int, tuple[str, str, dict[str, Any]]]


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def print_json(value: Any, *, compact: bool = False) -> None:
    if compact:
        print(json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=json_default))
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2, default=json_default))


def ref_id(value: Any) -> int | None:
    if isinstance(value, dict):
        raw = value.get("value")
        if isinstance(raw, int):
            return raw
    return None


def short_type(full_type: str) -> str:
    return full_type.rsplit(".", 1)[-1]


def campaign_code(template_name: str | None) -> str | None:
    if not template_name:
        return None
    if "_" in template_name and template_name[:4].isdigit():
        return template_name.split("_", 1)[1]
    return template_name


def clean_number(value: Any, digits: int = 3) -> Any:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, digits)
    return value


def clean_numbers(value: Any, digits: int = 3) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_numbers(v, digits) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_numbers(v, digits) for v in value]
    return clean_number(value, digits)


def save_fingerprint(save_path: Path) -> dict[str, Any]:
    stat = save_path.stat()
    return {
        "path": str(save_path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def cache_key(fingerprint: dict[str, Any]) -> str:
    raw = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def candidate_save_dirs() -> Iterable[Path]:
    home = Path.home()
    yield home / "Documents" / "My Games" / "TerraInvicta" / "Saves"
    yield home / "OneDrive" / "Documents" / "My Games" / "TerraInvicta" / "Saves"
    yield home / "OneDrive" / "문서" / "My Games" / "TerraInvicta" / "Saves"


def candidate_templates_dirs() -> Iterable[Path]:
    steam_roots = (
        Path("C:/Program Files (x86)/Steam/steamapps/common"),
        Path("C:/Program Files/Steam/steamapps/common"),
        Path("D:/SteamLibrary/steamapps/common"),
        Path("E:/SteamLibrary/steamapps/common"),
    )
    for root in steam_roots:
        yield root / "Terra Invicta" / "TerraInvicta_Data" / "StreamingAssets" / "Templates"


def find_latest_save() -> Path:
    candidates: list[Path] = []
    for directory in candidate_save_dirs():
        if directory.is_dir():
            candidates.extend(path for path in directory.glob(SAVE_GLOB) if path.is_file())
    if not candidates:
        raise FileNotFoundError("No Terra Invicta .gz saves found. Pass --save <path>.")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def resolve_save_path(save_arg: str | None) -> Path:
    if save_arg:
        path = Path(save_arg).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Save file not found: {path}")
        return path
    return find_latest_save()


def resolve_templates_dir(templates_arg: str | None) -> Path | None:
    if templates_arg:
        path = Path(templates_arg).expanduser()
        if not path.is_dir():
            raise FileNotFoundError(f"Templates directory not found: {path}")
        return path
    for path in candidate_templates_dirs():
        if (path / "TITraitTemplate.json").is_file():
            return path
    return None


def load_save(save_path: Path) -> dict[str, Any]:
    with gzip.open(save_path, "rt", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or "gamestates" not in data:
        raise ValueError(f"Not a recognized Terra Invicta save: {save_path}")
    return data


def file_fingerprint(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def snapshot_fingerprint(save_path: Path, templates_dir: Path | None) -> dict[str, Any]:
    return {
        "save": save_fingerprint(save_path),
        "traitTemplate": file_fingerprint(templates_dir / "TITraitTemplate.json" if templates_dir else None),
    }


def load_trait_templates(templates_dir: Path | None) -> dict[str, dict[str, Any]]:
    return load_named_templates(templates_dir, "TITraitTemplate.json")


def load_named_templates(templates_dir: Path | None, filename: str) -> dict[str, dict[str, Any]]:
    if templates_dir is None:
        return {}
    path = templates_dir / filename
    if not path.is_file():
        return {}
    stat = path.stat()
    return _load_named_templates_cached(str(path.resolve()), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=None)
def _load_named_templates_cached(path_value: str, size: int, mtime_ns: int) -> dict[str, dict[str, Any]]:
    path = Path(path_value)
    with path.open("r", encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        return {}
    return {item["dataName"]: item for item in raw if isinstance(item, dict) and item.get("dataName")}


def as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def raw_state_id(entry: dict[str, Any]) -> int | None:
    value = entry.get("Value") or {}
    return ref_id(entry.get("Key")) or ref_id(value.get("ID"))


def raw_name_values(state: dict[str, Any]) -> list[str]:
    values = []
    for value in (state.get("templateName"), campaign_code(state.get("templateName")), state.get("displayName")):
        if value:
            values.append(str(value))
    return values


def match_raw_state(indexed: IndexedState, wanted_type: str, name: str) -> tuple[int | None, dict[str, Any]] | None:
    needle = name.casefold()
    partial: list[tuple[int | None, dict[str, Any]]] = []
    for entry in type_entries(indexed, wanted_type):
        state = entry.get("Value") or {}
        if not isinstance(state, dict):
            continue
        names = raw_name_values(state)
        state_id = raw_state_id(entry)
        if any(value.casefold() == needle for value in names):
            return state_id, state
        if any(needle in value.casefold() for value in names):
            partial.append((state_id, state))
    return partial[0] if partial else None


def state_value_by_id(indexed: IndexedState, state_id: int | None) -> dict[str, Any] | None:
    if state_id is None:
        return None
    found = indexed.id_index.get(state_id)
    return found[2] if found else None


def find_faction_state(indexed: IndexedState, name: str | None = None) -> tuple[int, dict[str, Any]]:
    if name:
        found = match_raw_state(indexed, "TIFactionState", name)
        if found and found[0] is not None:
            return found[0], found[1]
        raise SystemExit(f"Faction not found: {name}")

    metadata = first_value(indexed, "TIMetadataState") or {}
    player_faction_name = metadata.get("playerFactionName")
    if player_faction_name:
        found = match_raw_state(indexed, "TIFactionState", str(player_faction_name))
        if found and found[0] is not None:
            return found[0], found[1]

    resist_candidate: tuple[int, dict[str, Any]] | None = None
    for entry in type_entries(indexed, "TIFactionState"):
        faction = entry.get("Value") or {}
        state_id = raw_state_id(entry)
        if state_id is None:
            continue
        player = resolve_ref(indexed, faction.get("player"))
        if player and player[2].get("templateName") == "ResistPlayer":
            return state_id, faction
        if faction.get("templateName") == "ResistCouncil":
            resist_candidate = (state_id, faction)
    if resist_candidate:
        return resist_candidate

    for entry in type_entries(indexed, "TIFactionState"):
        faction = entry.get("Value") or {}
        state_id = raw_state_id(entry)
        if state_id is not None:
            return state_id, faction
    raise SystemExit("No faction states found.")


def faction_effect_contexts(indexed: IndexedState, faction_id: int) -> dict[str, list[str]]:
    for entry in type_entries(indexed, "TIEffectsState"):
        effects_state = entry.get("Value") or {}
        pairs = effects_state.get("factionEffectsNames") if isinstance(effects_state.get("factionEffectsNames"), list) else []
        for pair in pairs:
            if not isinstance(pair, dict) or ref_id(pair.get("Key")) != faction_id:
                continue
            value = pair.get("Value")
            if isinstance(value, dict):
                return {
                    str(context): [str(item) for item in names if item]
                    for context, names in value.items()
                    if isinstance(names, list)
                }
    return {}


def apply_effect_modifiers(
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    context: str,
    base_value: float,
) -> float:
    result = float(base_value)
    for effect_name in effect_contexts.get(context, []):
        effect = effect_templates.get(effect_name)
        if not effect:
            continue
        operation = effect.get("operation")
        value = as_float(effect.get("value"), 0.0)
        if operation == "Additive":
            result += value
        elif operation == "Multiplicative":
            result *= value
        elif operation == "SetToFixedValue":
            result = value
        elif operation == "IncreaseToValue":
            result = max(result, value)
        elif operation == "DecreaseToValue":
            result = min(result, value)
    return result


def effect_modifier_delta(
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    context: str,
    base_value: float,
) -> float:
    return apply_effect_modifiers(effect_contexts, effect_templates, context, base_value) - base_value


def build_index(data: dict[str, Any]) -> IndexedState:
    gamestates = data.get("gamestates", {})
    if not isinstance(gamestates, dict):
        raise ValueError("Save gamestates field is not an object")

    id_index: dict[int, tuple[str, str, dict[str, Any]]] = {}
    for full_type, entries in gamestates.items():
        if not isinstance(entries, list):
            continue
        type_name = short_type(full_type)
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            value = entry.get("Value")
            if not isinstance(value, dict):
                continue
            state_id = ref_id(entry.get("Key")) or ref_id(value.get("ID"))
            if state_id is not None:
                id_index[state_id] = (full_type, type_name, value)
    return IndexedState(data=data, gamestates=gamestates, id_index=id_index)


def resolve_ref(indexed: IndexedState, value: Any) -> tuple[str, str, dict[str, Any]] | None:
    state_id = ref_id(value)
    if state_id is None:
        return None
    return indexed.id_index.get(state_id)


def ref_summary(indexed: IndexedState, value: Any) -> dict[str, Any] | None:
    state_id = ref_id(value)
    if state_id is None:
        return None
    found = indexed.id_index.get(state_id)
    if not found:
        return {"id": state_id}
    _, type_name, state = found
    return {
        "id": state_id,
        "type": type_name,
        "template": state.get("templateName"),
        "code": campaign_code(state.get("templateName")),
        "display": state.get("displayName"),
    }


def region_nation_summary(indexed: IndexedState, value: Any) -> dict[str, Any] | None:
    found = resolve_ref(indexed, value)
    if not found:
        return None
    region = found[2]
    return ref_summary(indexed, region.get("nation"))


def type_entries(indexed: IndexedState, wanted_type: str) -> list[dict[str, Any]]:
    for full_type, entries in indexed.gamestates.items():
        if full_type == wanted_type or short_type(full_type) == wanted_type:
            return entries
    return []


def first_value(indexed: IndexedState, wanted_type: str) -> dict[str, Any] | None:
    entries = type_entries(indexed, wanted_type)
    if entries:
        value = entries[0].get("Value")
        if isinstance(value, dict):
            return value
    return None
