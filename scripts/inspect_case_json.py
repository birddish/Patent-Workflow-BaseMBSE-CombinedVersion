"""Bounded L0/L1/L2/L3 projections for the master case JSON.

The command keeps the original CLI shape but makes the default reads small:
L0 is an index, L1 is an operation projection (or a compact legacy view
index), L2 resolves stable IDs through the control object index first, and
L3 delegates to audit_case_json without ever returning the whole case.
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
from pathlib import Path
from typing import Any, Iterable

from _case_utils import load_json, now_iso, pointer_get


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SLICE_PROFILE_PATH = PACKAGE_ROOT / "references" / "routing" / "slice-profiles.json"

# These are only command-line compatibility aliases.  The canonical profile
# definition, pointers, and budgets always come from slice-profiles.json.
LEGACY_VIEW_PROFILES = {
    "mbse": "mbse.disclosure.standard",
    "search": "search.novelty.quick",
    "drafting": "drafting.stage3",
    "oa": "oa.opinion.phase_01",
    "invalidity": "invalidity.defense.phase_01",
    "audit": "audit.l0",
}
PROFILE_ALIASES = {
    "mbse.disclosure": "mbse.disclosure.standard",
    "mbse.document": "mbse.document.standard",
    "mbse.search": "mbse.search.standard",
    "drafting.stage3.claim_core": "drafting.stage3",
    "drafting.claim_core": "drafting.stage1_stage3_claim_core",
    "drafting.stage1-stage3-claim-core": "drafting.stage1_stage3_claim_core",
    "drafting.stage1+stage3": "drafting.stage1_stage3_claim_core",
    "oa.phase1": "oa.opinion.phase_01",
    "oa.phase2": "oa.opinion.phase_02",
    "oa.phase3": "oa.opinion.phase_03",
    "oa.phase4": "oa.opinion.phase_04",
    "oa.phase5": "oa.opinion.phase_05",
    "oa.v2.1-oa.phase4": "oa.opinion.phase_04",
    "oa.inventive_step": "oa.opinion.phase_04",
}
# These guards are deliberately broader than the current schema names. A
# projection must remain safe if an importer uses a future spelling such as
# raw_binary_content or payload_base64.
EXCLUDED_KEYS = {
    "raw_artifacts",
    "content_base64",
    "base64",
    "binary_payloads",
    "binary_payload",
    "binary_data",
    "binary_content",
    "raw_binary",
    "source_path",
    "source_paths",
    "file_path",
    "file_paths",
}
BINARY_KEY_MARKERS = (
    "base64",
    "binary_payload",
    "binary_data",
    "binary_content",
    "raw_binary",
    "raw_artifact",
)
REFERENCE_KEYS = {
    "source_ref", "source_refs", "evidence_ref", "evidence_refs", "evidence_id", "evidence_ids",    "dependency_id", "dependency_ids", "depends_on", "replaced_by", "claim_id", "claim_ids",
    "issue_id", "issue_ids", "document_id", "document_ids", "feature_ref", "feature_refs",
    "chain_id", "chain_ids", "protection_unit_id", "protection_unit_ids",
    "support_link_id", "support_link_ids", "comparison_id", "comparison_ids",
    "path_id", "path_ids", "related_id", "related_ids", "parent_id", "parent_ids",
    "target_id", "target_ids", "source_id", "source_ids",
}
ENTITY_ID_KEYS = {
    "document_id", "claim_id", "issue_id", "chain_id", "evidence_id", "source_material_id",
    "protection_unit_id", "search_result_id", "comparison_id", "path_id", "feature_id",
    "entity_id", "transaction_id", "batch_id", "question_id", "gate_id", "conflict_id",
    "claim_set_id", "support_link_id", "relation_id", "model_id", "patch_id",
}


def load_slice_profiles() -> dict[str, Any]:
    """Load the only authoritative profile registry for this reader."""
    config = load_json(SLICE_PROFILE_PATH)
    profiles = config.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise SystemExit(f"切片配置没有可用 profiles: {SLICE_PROFILE_PATH}")
    return config


def _profile_view(profile_name: str) -> str | None:
    return profile_name.split(".", 1)[0] if "." in profile_name else None


def _unique_strings(values: Iterable[Any]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if isinstance(value, str) and value))


def resolve_profile(name: str, profiles_config: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    """Resolve a canonical or thin legacy alias through slice-profiles.json."""
    profiles_config = profiles_config or load_slice_profiles()
    requested = name.strip().lower()
    normalized = PROFILE_ALIASES.get(requested, requested)
    profiles = profiles_config.get("profiles", {})
    if normalized not in profiles or not isinstance(profiles[normalized], dict):
        choices = ", ".join(sorted(str(key) for key in profiles))
        raise SystemExit(f"未知 L1 操作 profile: {name}；可用 profile: {choices}")
    raw = profiles[normalized]
    defaults = profiles_config.get("defaults", {})
    if not isinstance(defaults, dict):
        defaults = {}
    budget = dict(defaults)
    profile_budget = raw.get("context_budget", {})
    if isinstance(profile_budget, dict):
        budget.update(profile_budget)
    excludes = _unique_strings(defaults.get("exclude_fields", []))
    excludes.extend(_unique_strings(raw.get("exclude_fields", [])))
    excludes.extend(_unique_strings(profile_budget.get("exclude_fields", []) if isinstance(profile_budget, dict) else []))
    spec = {
        "view": _profile_view(normalized),
        "pointers": _unique_strings(raw.get("pointers", [])),
        "context_budget": budget,
        "exclude_fields": list(dict.fromkeys(excludes)),
        "canonical_name": normalized,
    }
    required = {"max_output_chars", "max_items", "evidence_hops", "max_excerpt_chars_per_source"}
    missing = sorted(required - set(budget))
    if not spec["pointers"] or missing:
        detail = f"缺少字段 {missing}" if missing else "pointers 为空"
        raise SystemExit(f"切片 profile 配置无效 {normalized}: {detail}")
    return normalized, spec


def _legacy_view_profile(view: str, profiles_config: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    try:
        return resolve_profile(LEGACY_VIEW_PROFILES[view], profiles_config)
    except KeyError as exc:
        raise SystemExit(f"不支持的兼容视图: {view}") from exc


def is_excluded_key(key: str) -> bool:
    lowered = key.lower()
    return (
        lowered in {item.lower() for item in EXCLUDED_KEYS}
        or any(marker in lowered for marker in BINARY_KEY_MARKERS)
    )


def is_excluded_path(path: str, exclude_fields: Iterable[str] = ()) -> bool:
    """Apply configured JSON-pointer exclusions plus unconditional binary guards."""
    if not path:
        return False
    tokens = path.lstrip("/").split("/")
    if any(is_excluded_key(token.replace("~1", "/").replace("~0", "~")) for token in tokens):
        return True
    for raw_pattern in exclude_fields:
        if not isinstance(raw_pattern, str) or not raw_pattern.startswith("/"):
            continue
        pattern = raw_pattern.lstrip("/").split("/")
        if len(pattern) != len(tokens):
            continue
        if all(expected == "*" or expected == actual for expected, actual in zip(pattern, tokens)):
            return True
    return False


def ensure_readable_pointer(pointer: str, exclude_fields: Iterable[str] = ()) -> None:
    """Reject a direct read of a protected source or binary pointer."""
    if is_excluded_path(pointer, exclude_fields):
        raise SystemExit(f"禁止读取受保护的案件 JSON 路径: {pointer}")


def is_binary_mapping(value: Any) -> bool:
    """Recognize common encoded or raw-binary object envelopes."""
    if not isinstance(value, dict):
        return False
    encoding = value.get("encoding")
    if isinstance(encoding, str) and encoding.lower() in {"base64", "binary", "raw"}:
        return any(
            isinstance(key, str)
            and ("payload" in key.lower() or "content" in key.lower() or "data" in key.lower())
            for key in value
        )
    return False


def pointer_join(path: str, token: str) -> str:
    escaped = str(token).replace("~", "~0").replace("/", "~1")
    return f"{path}/{escaped}" if path else f"/{escaped}"


def stable_id_of(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    direct = value.get("id")
    if isinstance(direct, str) and direct:
        return direct
    for key, item in value.items():
        if key in ENTITY_ID_KEYS and isinstance(item, str) and item:
            return item
    return None


def iter_dicts(value: Any, path: str = "") -> Iterable[tuple[dict[str, Any], str]]:
    if isinstance(value, dict):
        yield value, path or "/"
        for key, child in value.items():
            if is_excluded_key(key):
                continue
            yield from iter_dicts(child, pointer_join(path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_dicts(child, pointer_join(path, str(index)))


def get_optional(
    case: dict[str, Any],
    pointer: str,
    exclude_fields: Iterable[str] = (),
) -> Any:
    ensure_readable_pointer(pointer, exclude_fields)
    try:
        return pointer_get(case, pointer)
    except (KeyError, IndexError, ValueError, TypeError):
        return None


def object_index_pointer(case: dict[str, Any], entity_id: str) -> str | None:
    index = case.get("control", {}).get("object_index", {})
    if not isinstance(index, dict):
        return None
    entry = index.get(entity_id)
    if isinstance(entry, str):
        return None if is_excluded_path(entry) else entry
    if isinstance(entry, dict):
        pointer = entry.get("path") or entry.get("pointer")
        return pointer if isinstance(pointer, str) and not is_excluded_path(pointer) else None
    if isinstance(entry, list) and entry:
        first = entry[0]
        if isinstance(first, str):
            return None if is_excluded_path(first) else first
        if isinstance(first, dict):
            pointer = first.get("path") or first.get("pointer")
            return pointer if isinstance(pointer, str) and not is_excluded_path(pointer) else None
    return None


def find_id(case: dict[str, Any], entity_id: str) -> tuple[Any, str, str] | None:
    """Resolve an entity, preferring the explicit control index."""
    indexed = object_index_pointer(case, entity_id)
    if indexed:
        try:
            return pointer_get(case, indexed), indexed, "control.object_index"
        except (KeyError, IndexError, ValueError, TypeError):
            pass
    for value, path in iter_dicts(case):
        if isinstance(value.get("id"), str) and value["id"] == entity_id:
            return value, path, "scan.id"
    for value, path in iter_dicts(case):
        if stable_id_of(value) == entity_id:
            return value, path, "scan.typed_id"
    return None


def extract_ids(value: Any) -> list[str]:
    if isinstance(value, dict):
        entity_id = stable_id_of(value)
        return [entity_id] if entity_id else []
    if isinstance(value, list):
        return [entity_id for item in value for entity_id in extract_ids(item)]
    return []


def compact_index(value: Any, max_ids: int = 20) -> Any:
    if isinstance(value, list):
        ids: list[str] = []
        statuses: dict[str, int] = {}
        for item in value:
            ids.extend(extract_ids(item))
            if isinstance(item, dict) and isinstance(item.get("status"), str):
                statuses[item["status"]] = statuses.get(item["status"], 0) + 1
        unique_ids = list(dict.fromkeys(ids))
        result: dict[str, Any] = {"count": len(value), "ids": unique_ids[:max_ids]}
        if len(unique_ids) > max_ids:
            result["ids_truncated"] = True
        if statuses:            result["status_counts"] = statuses
        return result
    if isinstance(value, dict):
        entity_id = stable_id_of(value)
        if entity_id:
            result = {"id": entity_id}
            if isinstance(value.get("status"), str):
                result["status"] = value["status"]
            if isinstance(value.get("title"), str):
                result["title"] = _light_scalar(value["title"], 96)
            return result
        safe_keys = [key for key in value if not is_excluded_key(key)]
        return {"count": len(safe_keys), "keys": safe_keys[:max_ids], "keys_truncated": len(safe_keys) > max_ids}
    return value


NAV_IGNORED_KEYS = {
    "detail", "details", "explanation", "reason", "rationale", "message", "notes", "analysis", "raw", "full_text"
}
NAV_ROUTE_KEYS = {"transaction", "view", "submode", "profile", "phase", "domain", "status", "confidence"}


def _light_scalar(value: Any, max_chars: int = 64) -> Any:
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, str):
        return value if len(value) <= max_chars else "<truncated>"
    return None


def _compact_route(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, Any] = {}
    for key in NAV_ROUTE_KEYS:
        if key in value and key not in NAV_IGNORED_KEYS:
            scalar = _light_scalar(value[key])
            if scalar is not None:
                result[key] = scalar
    return result or None


def _compact_ai_assessment(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        route = _compact_route(value)
        if route:
            result.update(route)
        for key in ("candidate", "candidate_route", "route"):
            if key in value:
                compacted = _compact_route(value[key])
                if compacted:
                    result[key] = compacted
        return result or None
    # A free-form assessment is often a long rationale. Navigation only
    # carries route-shaped fields; do not surface scalar prose here.
    return None


def compact_navigation(value: Any, max_ids: int = 20) -> Any:
    if not isinstance(value, dict):
        return compact_index(value, max_ids)
    allowed = {
        "user_selected_transaction", "user_selected_view", "user_selected_submode",
        "consistency_check", "challenge_required", "confirmation_status", "confirmed_revision",
        "active_transaction", "confirmed_route", "ai_routing_assessment",
    }
    result: dict[str, Any] = {}
    for key in allowed:
        if key not in value or is_excluded_key(key) or key.lower() in NAV_IGNORED_KEYS:
            continue
        if key == "ai_routing_assessment":
            compacted = _compact_ai_assessment(value[key])
        elif key == "confirmed_route":
            compacted = _compact_route(value[key])
        elif key == "consistency_check" and isinstance(value[key], dict):
            compacted = {candidate: _light_scalar(value[key][candidate], 48) for candidate in ("status", "result", "state") if candidate in value[key]}
        else:
            compacted = _light_scalar(value[key])
        if compacted is not None:
            result[key] = compacted
    if result:
        return result
    safe_keys = [
        key for key in value
        if not is_excluded_key(key) and key.lower() not in NAV_IGNORED_KEYS
    ]
    return {"count": len(safe_keys), "keys": safe_keys[:max_ids], "keys_truncated": len(safe_keys) > max_ids}


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "CURSOR." + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if not cursor or not cursor.startswith("CURSOR."):
        return None
    encoded = cursor[7:] + "=" * (-len(cursor[7:]) % 4)
    try:
        value = json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


class ProjectionState:
    def __init__(self, max_items: int, cursor_path: str | None = None) -> None:
        self.max_items = max(0, max_items)
        self.cursor_path = cursor_path
        self.resume = cursor_path is None
        self.cursor_seen = cursor_path is None
        self.items_seen = 0
        self.items_returned = 0
        self.truncated = False
        self.over_limit = False
        self.next_path: str | None = None

    def reserve(self, path: str) -> bool:
        if not self.resume:
            if path != self.cursor_path:
                return False
            self.resume = True
            self.cursor_seen = True
        self.items_seen += 1
        if self.items_returned >= self.max_items:
            self.truncated = True
            self.next_path = self.next_path or path
            return False
        self.items_returned += 1
        return True

    def omit(self, path: str) -> None:
        self.truncated = True
        self.next_path = self.next_path or path


SOURCE_PATH_TOKENS = {"source_materials", "search_results", "evidence", "documents", "references"}
EXCERPT_FIELD_NAMES = {"excerpt", "source_excerpt", "evidence_excerpt", "abstract", "full_text", "text", "content"}


def is_source_context(path: str) -> bool:
    return any(token.lower() in SOURCE_PATH_TOKENS for token in path.lstrip("/").split("/"))


def project_scalar(value: Any, key: str, path: str, max_excerpt_chars_per_source: int | None) -> Any:
    if (
        isinstance(value, str)
        and max_excerpt_chars_per_source is not None
        and max_excerpt_chars_per_source >= 0
        and len(value) > max_excerpt_chars_per_source
        and (key.lower() in EXCERPT_FIELD_NAMES or "evidence" in key.lower() or "source" in key.lower())
        and is_source_context(path)
    ):
        return value[:max_excerpt_chars_per_source] + "..."
    return value


def project_value(
    value: Any,
    fields: list[str],
    state: ProjectionState,
    path: str,
    exclude_fields: Iterable[str] = (),
    max_excerpt_chars_per_source: int | None = None,
) -> Any:
    if is_excluded_path(path, exclude_fields):
        return _ExcludedMarker()
    if isinstance(value, dict) and is_binary_mapping(value):
        return _ExcludedMarker()
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        field_hits = [field for field in fields if field in value and not is_excluded_key(field)]
        keys = field_hits if field_hits else [key for key in value if not is_excluded_key(key)]
        for key in keys:
            child_path = pointer_join(path, key)
            if is_excluded_path(child_path, exclude_fields):
                continue
            result[key] = project_value(
                value[key],
                fields,
                state,
                child_path,
                exclude_fields,
                max_excerpt_chars_per_source,
            )
            if isinstance(result[key], _ExcludedMarker):
                del result[key]
        return result
    if isinstance(value, list):
        result_list: list[Any] = []
        for index, child in enumerate(value):
            child_path = pointer_join(path, str(index))
            if is_excluded_path(child_path, exclude_fields):
                continue
            if not state.resume and child_path != state.cursor_path:
                continue
            if not state.reserve(child_path):
                state.omit(child_path)
                break
            projected_child = project_value(
                child,
                fields,
                state,
                child_path,
                exclude_fields,
                max_excerpt_chars_per_source,
            )
            if isinstance(projected_child, _ExcludedMarker):
                continue
            result_list.append(projected_child)
        return result_list
    key = path.rsplit("/", 1)[-1] if "/" in path else path
    return project_scalar(value, key, path, max_excerpt_chars_per_source)


class _ExcludedMarker:
    """Internal marker retained for a direct excluded pointer, never emitted."""

def collection_candidates(value: Any, path: str = "") -> list[tuple[int, Any, str]]:
    candidates: list[tuple[int, Any, str]] = []
    if isinstance(value, list):
        if path and value:
            candidates.append((len(value), value, path))
        for index, child in enumerate(value):
            candidates.extend(collection_candidates(child, pointer_join(path, str(index))))
    elif isinstance(value, dict):
        if path and len(value) > 1 and stable_id_of(value) is None:
            candidates.append((len(value), value, path))
        for key, child in value.items():
            if not is_excluded_key(key):                candidates.extend(collection_candidates(child, pointer_join(path, key)))
    return candidates


def trim_to_budget(value: Any, max_chars: int, state: ProjectionState) -> tuple[Any, int]:
    working = copy.deepcopy(value)
    estimated = len(json.dumps(working, ensure_ascii=False, separators=(",", ":")))
    while estimated > max_chars:
        candidates = collection_candidates(working)
        if not candidates:
            state.over_limit = True
            state.truncated = True
            return {"_projection_error": "single_value_exceeds_char_budget", "estimated_chars": estimated}, estimated
        _, container, path = max(candidates, key=lambda item: item[0])
        if isinstance(container, list):
            removed_index = len(container) - 1
            container.pop()
            state.truncated = True
            state.next_path = state.next_path or pointer_join(path, str(removed_index))
        else:
            removed_key = next(reversed(container))
            del container[removed_key]
            state.truncated = True
            state.next_path = state.next_path or pointer_join(path, removed_key)
        estimated = len(json.dumps(working, ensure_ascii=False, separators=(",", ":")))
    return working, estimated


def projection_meta(
    level: str,
    max_items: int,
    max_chars: int,
    state: ProjectionState,
    requested_pointers: list[str],
    profile: str | None = None,
    compatibility: str | None = None,
    estimated_chars: int | None = None,
    profile_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "level": level,
        "profile": profile,
        "requested_pointers": requested_pointers,
        "max_items": max_items,
        "max_chars": max_chars,
        "items_returned": state.items_returned,
        "items_seen": state.items_seen,
        "truncated": state.truncated,
        "over_limit": state.over_limit,
        "next_cursor": encode_cursor({"path": state.next_path}) if state.next_path else None,
        "excluded_by_default": ["binary_payloads", "*_base64", "source_path", "source_paths", "file_path", "file_paths"],
    }
    if profile_spec:
        budget = profile_spec.get("context_budget", {})
        meta.update(
            {
                "profile_source": str(SLICE_PROFILE_PATH).replace("\\", "/"),
                "configured_max_items": budget.get("max_items"),
                "configured_max_output_chars": budget.get("max_output_chars"),
                "evidence_hops": budget.get("evidence_hops"),
                "max_excerpt_chars_per_source": budget.get("max_excerpt_chars_per_source"),
                "exclude_fields": profile_spec.get("exclude_fields", []),
            }
        )
    if compatibility:
        meta["compatibility"] = compatibility
    if estimated_chars is not None:
        meta["estimated_chars"] = estimated_chars
    if state.cursor_path and not state.cursor_seen:
        meta["cursor_error"] = "cursor_path_not_found"
    return meta

def attach_meta(value: Any, meta: dict[str, Any]) -> Any:
    if isinstance(value, _ExcludedMarker):
        value = {}
    if isinstance(value, dict):
        result = dict(value)
        result["_projection"] = meta
        return result
    return {"data": value, "_projection": meta}


def parse_many(values: list[Any] | None, split_commas: bool = False) -> list[str]:
    result: list[str] = []
    for value in values or []:
        parts = value if isinstance(value, list) else [value]
        for part in parts:
            if not isinstance(part, str):
                continue
            if split_commas:
                result.extend(item.strip() for item in part.split(",") if item.strip())
            elif part:
                result.append(part)
    return result


def build_l0(case: dict[str, Any], max_items: int) -> dict[str, Any]:
    control = case.get("control", {})
    case_info = case.get("case", {})
    compact_case: dict[str, Any] = {}
    if isinstance(case_info, dict):
        for key in ("case_id", "title", "technical_domain", "status"):
            if key not in case_info or is_excluded_key(key):
                continue
            value = case_info[key]
            compact_case[key] = _light_scalar(value, 96) if isinstance(value, str) else value
    return {
        "case": compact_case,
        "navigation": compact_navigation(control.get("navigation", {}), max_items),
        "current_revision": control.get("current_revision", 0),
        "open_gates": compact_index(control.get("open_gates", []), max_items),
        "pending_questions": compact_index(control.get("pending_questions", []), max_items),
        "conflicts": compact_index(control.get("conflicts", []), max_items),
        "summary": {"present": bool(control.get("summary")), "field_count": len(control.get("summary", {})) if isinstance(control.get("summary"), dict) else 0},
        "view_status": compact_index(control.get("view_status", {}), max_items),
    }


def fit_l0_to_budget(data: dict[str, Any], meta: dict[str, Any], max_chars: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """Keep compact L0 within the requested compact-JSON character budget."""
    working = copy.deepcopy(data)
    state = ProjectionState(0)

    def size(value: Any) -> int:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))

    while size(attach_meta(working, meta)) > max_chars and working:
        candidates = collection_candidates(working)
        if candidates:
            _, container, path = max(candidates, key=lambda item: item[0])
            if isinstance(container, list) and container:
                removed_index = len(container) - 1
                container.pop()
                state.next_path = state.next_path or pointer_join(path, str(removed_index))
            elif isinstance(container, dict) and container:
                removed_key = next(reversed(container))
                del container[removed_key]
                state.next_path = state.next_path or pointer_join(path, removed_key)
            state.truncated = True
            continue
        # No nested collection remains.  Preserve the case identity and
        # revision first, then remove the least important top-level summary.
        removable = [key for key in working if key not in {"case", "current_revision"}]
        if not removable:
            removable = list(working)
        if not removable:
            break
        del working[removable[-1]]
        state.truncated = True

    meta = dict(meta)
    meta["truncated"] = bool(meta.get("truncated") or state.truncated)
    meta["over_limit"] = bool(meta.get("over_limit") or state.truncated)
    meta["next_cursor"] = encode_cursor({"path": state.next_path}) if state.next_path else None
    candidate = attach_meta(working, meta)
    meta["estimated_chars"] = size(candidate)
    if size(candidate) > max_chars:
        # The metadata itself must remain bounded even at the smallest valid
        # budget; returning no case data is safer than exceeding the budget.
        compact_meta = {
            "level": "L0",
            "max_items": meta.get("max_items"),
            "max_chars": max_chars,
            "truncated": True,
            "over_limit": True,
            "next_cursor": None,
        }
        return {}, compact_meta
    return working, meta


def fit_projection_to_budget(
    data: Any,
    meta: dict[str, Any],
    max_chars: int,
    state: ProjectionState,
) -> tuple[Any, dict[str, Any]]:
    """Fit data plus projection metadata inside the effective character cap."""
    working = copy.deepcopy(data)

    def size(value: Any) -> int:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))

    def remove_one() -> bool:
        candidates = collection_candidates(working)
        if not candidates:
            return False
        _, container, path = max(candidates, key=lambda item: item[0])
        if isinstance(container, list) and container:
            removed_index = len(container) - 1
            container.pop()
            state.next_path = state.next_path or pointer_join(path, str(removed_index))
        elif isinstance(container, dict) and container:
            removed_key = next(reversed(container))
            del container[removed_key]
            state.next_path = state.next_path or pointer_join(path, removed_key)
        else:
            return False
        state.truncated = True
        state.over_limit = True
        return True

    while size(attach_meta(working, meta)) > max_chars and remove_one():
        pass

    candidate = attach_meta(working, meta)
    if size(candidate) <= max_chars:
        meta = dict(meta)
        meta["truncated"] = bool(meta.get("truncated") or state.truncated)
        meta["over_limit"] = bool(meta.get("over_limit") or state.over_limit)
        meta["next_cursor"] = encode_cursor({"path": state.next_path}) if state.next_path else None
        meta["estimated_chars"] = size(attach_meta(working, meta))
        return working, meta

    # A single scalar/entity can itself exceed the cap. Return only a compact
    # diagnostic envelope instead of violating the caller's configured bound.
    minimal_meta = {
        "level": meta.get("level"),
        "profile": meta.get("profile"),
        "max_items": meta.get("max_items"),
        "max_chars": max_chars,
        "truncated": True,
        "over_limit": True,
        "next_cursor": encode_cursor({"path": state.next_path}) if state.next_path else None,
    }
    minimal = attach_meta({}, minimal_meta)
    if size(minimal) <= max_chars:
        minimal_meta["estimated_chars"] = size(minimal)
        return {}, minimal_meta
    minimal_meta = {
        "level": meta.get("level"),
        "max_chars": max_chars,
        "truncated": True,
        "over_limit": True,
        "next_cursor": encode_cursor({"path": state.next_path}) if state.next_path else None,
    }
    return {}, minimal_meta


def build_l1(
    case: dict[str, Any],
    args: argparse.Namespace,
    max_items: int,
    max_chars: int,
    profiles_config: dict[str, Any] | None = None,
) -> tuple[Any, dict[str, Any], str]:
    explicit_pointers = parse_many(args.pointer) + parse_many(args.pointers)
    fields = parse_many(args.field, split_commas=True) + parse_many(args.fields, split_commas=True)
    profile_name: str | None = None
    profile_spec: dict[str, Any] | None = None
    if args.profile and explicit_pointers:
        raise SystemExit("L1 不能同时使用 --profile 和显式 --pointer/--pointers")
    if args.profile:
        profile_name, profile_spec = resolve_profile(args.profile, profiles_config)
        if args.view and args.view != profile_spec["view"]:
            raise SystemExit(f"profile {profile_name} 属于视图 {profile_spec['view']}，不能与 --view {args.view} 混用")
        pointers = list(profile_spec["pointers"])
        if profile_spec.get("compact"):
            result = {pointer: compact_index(get_optional(case, pointer, profile_spec.get("exclude_fields", [])), max_items) for pointer in pointers}
            state = ProjectionState(max_items)
            meta = projection_meta(
                "L1",
                max_items,
                max_chars,
                state,
                pointers,
                profile_name,
                "profile_compact",
                profile_spec=profile_spec,
            )
            result, meta = fit_projection_to_budget(result, meta, max_chars, state)
            return result, meta, ",".join(pointers)
    elif explicit_pointers:
        pointers = explicit_pointers
    elif args.view:
        if fields:
            raise SystemExit("兼容性 L1 视图索引不接受 --fields；请改用 --profile 或 --pointers")
        profile_name, profile_spec = _legacy_view_profile(args.view, profiles_config)
        pointers = list(profile_spec["pointers"])
        result = {pointer: compact_index(get_optional(case, pointer, profile_spec.get("exclude_fields", [])), max_items) for pointer in pointers}
        state = ProjectionState(max_items)
        meta = projection_meta(
            "L1",
            max_items,
            max_chars,
            state,
            pointers,
            profile_name,
            "legacy_view_index",
            profile_spec=profile_spec,
        )
        result, meta = fit_projection_to_budget(result, meta, max_chars, state)
        return result, meta, ",".join(pointers)
    else:
        raise SystemExit("L1 必须指定 --profile、--pointer/--pointers 或 --view")

    budget = profile_spec.get("context_budget", {}) if profile_spec else {}
    exclude_fields = profile_spec.get("exclude_fields", []) if profile_spec else []
    excerpt_limit = budget.get("max_excerpt_chars_per_source")
    if not isinstance(excerpt_limit, int):
        excerpt_limit = None
    cursor_path = (decode_cursor(args.cursor) or {}).get("path")
    state = ProjectionState(max_items)
    state.items_seen = 0
    state.items_returned = 0
    state.cursor_seen = cursor_path is None
    result: dict[str, Any] = {}
    for pointer in pointers:
        local_cursor = cursor_path if cursor_path and (cursor_path == pointer or cursor_path.startswith(pointer.rstrip("/") + "/")) else None
        local_state = ProjectionState(max_items, local_cursor)
        result[pointer] = project_value(
            get_optional(case, pointer, exclude_fields),
            fields,
            local_state,
            pointer,
            exclude_fields,
            excerpt_limit,
        )
        state.items_seen += local_state.items_seen
        state.items_returned += local_state.items_returned
        state.truncated = state.truncated or local_state.truncated
        state.over_limit = state.over_limit or local_state.over_limit
        state.next_path = state.next_path or local_state.next_path
        if local_cursor and local_state.cursor_seen:
            state.cursor_seen = True
    meta = projection_meta(
        "L1",
        max_items,
        max_chars,
        state,
        pointers,
        profile_name,

        profile_spec=profile_spec,
    )
    result, meta = fit_projection_to_budget(result, meta, max_chars, state)
    return result, meta, ",".join(pointers)


def references_from(value: Any, kind: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        own_id = stable_id_of(value)
        for key, child in value.items():
            if is_excluded_key(key):
                continue
            lowered = key.lower()
            is_evidence = "evidence" in lowered or lowered in {"source_ref", "source_refs"}
            is_dependency = key in REFERENCE_KEYS and not is_evidence
            if kind == "evidence" and is_evidence:
                found.extend(reference_values(child))
            elif kind == "dependency" and is_dependency:
                found.extend(reference_values(child, exclude=own_id))
            if isinstance(child, (dict, list)):
                found.extend(references_from(child, kind))
    elif isinstance(value, list):
        for child in value:
            found.extend(references_from(child, kind))
    return list(dict.fromkeys(found))


def reference_values(value: Any, exclude: str | None = None) -> list[str]:
    if isinstance(value, str):
        if value and value != exclude and not value.startswith(("http://", "https://", "/")):
            return [value]
        return []
    if isinstance(value, list):
        return [item for child in value for item in reference_values(child, exclude)]
    return []


def collect_closure(
    case: dict[str, Any],
    target: Any,
    target_path: str,
    dependency_depth: int,
    evidence_depth: int,
    max_items: int = 50,
) -> dict[str, Any]:
    closure: dict[str, Any] = {
        "dependencies": [],
        "evidence": [],
        "unresolved": {"dependencies": [], "evidence": []},
    }
    queues = {"dependencies": [(target, target_path, 0)], "evidence": [(target, target_path, 0)]}
    seen_by_kind: dict[str, set[str]] = {"dependencies": set(), "evidence": set()}
    for kind, depth_limit in (("dependencies", dependency_depth), ("evidence", evidence_depth)):
        while queues[kind]:
            current, current_path, depth = queues[kind].pop(0)
            if depth >= depth_limit:
                continue
            ref_kind = "dependency" if kind == "dependencies" else "evidence"
            for ref_id in references_from(current, ref_kind):
                if ref_id in seen_by_kind[kind]:
                    continue
                seen_by_kind[kind].add(ref_id)
                if len(closure[kind]) >= max_items:
                    closure.setdefault("truncated", []).append(kind)
                    break
                found = find_id(case, ref_id)
                if not found:
                    closure["unresolved"][kind].append(ref_id)
                    continue
                obj, path, _ = found
                closure[kind].append({"id": ref_id, "path": path, "object": obj})
                queues[kind].append((obj, path, depth + 1))
    if "truncated" in closure:
        closure["truncated"] = list(dict.fromkeys(closure["truncated"]))
    return closure


def build_l2(
    case: dict[str, Any],
    args: argparse.Namespace,
    max_items: int,
    max_chars: int,
    profiles_config: dict[str, Any] | None = None,
) -> tuple[Any, dict[str, Any], str]:
    profile_name: str | None = None
    profile_spec: dict[str, Any] | None = None
    if args.profile:
        profile_name, profile_spec = resolve_profile(args.profile, profiles_config)
        if args.view and args.view != profile_spec["view"]:
            raise SystemExit(f"profile {profile_name} 属于视图 {profile_spec['view']}，不能与 --view {args.view} 混用")
    profile_exclude_fields = profile_spec.get("exclude_fields", []) if profile_spec else []
    pointers = parse_many(args.pointer)
    if len(pointers) > 1:
        raise SystemExit("L2 的旧 --pointer 参数一次只能指定一个对象")
    if pointers:
        ensure_readable_pointer(pointers[0], profile_exclude_fields)
        result: Any = pointer_get(case, pointers[0])
        read_path = pointers[0]
        target = result
        entity_id = None
    elif args.entity_id:
        found = find_id(case, args.entity_id)
        if not found:
            raise SystemExit(f"未找到对象 ID: {args.entity_id}")
        target, read_path, source = found
        entity_id = args.entity_id
        result = {"id": entity_id, "path": read_path, "object": target, "resolved_by": source}
    else:
        raise SystemExit("L2 必须指定 --pointer 或 --id")

    closure = args.closure
    dependency_depth = max(0, args.dependency_depth or 0)
    configured_hops = None
    exclude_fields: Iterable[str] = profile_exclude_fields
    excerpt_limit: int | None = None
    if profile_spec:
        budget = profile_spec.get("context_budget", {})
        configured_hops = budget.get("evidence_hops")
        exclude_fields = profile_spec.get("exclude_fields", [])
        candidate_excerpt_limit = budget.get("max_excerpt_chars_per_source")
        if isinstance(candidate_excerpt_limit, int):
            excerpt_limit = candidate_excerpt_limit
    explicit_evidence_depth = args.evidence_depth
    if explicit_evidence_depth is None:
        evidence_depth = configured_hops if isinstance(configured_hops, int) else 1
    else:
        evidence_depth = max(0, explicit_evidence_depth)
        if isinstance(configured_hops, int):
            evidence_depth = min(evidence_depth, configured_hops)
    if closure not in {"evidence", "direct", "all", "both"}:
        evidence_depth = 0
    if closure in {"dependencies", "direct", "all", "both"} and dependency_depth == 0:
        dependency_depth = 1
    if closure in {"evidence", "direct", "all", "both"} and evidence_depth == 0:        evidence_depth = 1 if configured_hops is None and explicit_evidence_depth is None else evidence_depth
    if closure == "dependencies":
        evidence_depth = 0
    if closure == "evidence":
        dependency_depth = 0
    if entity_id and (dependency_depth or evidence_depth):
        result.update(collect_closure(case, target, read_path, dependency_depth, evidence_depth, max_items))

    state = ProjectionState(max_items, (decode_cursor(args.cursor) or {}).get("path"))
    fields = parse_many(args.field, True) + parse_many(args.fields, True)
    projected = project_value(result, fields, state, read_path or "/", exclude_fields, excerpt_limit)
    meta = projection_meta(
        "L2",
        max_items,
        max_chars,
        state,
        [read_path],
        profile_name,

        profile_spec=profile_spec,
    )
    projected, meta = fit_projection_to_budget(projected, meta, max_chars, state)
    return projected, meta, read_path


L3_PATH_KEYS = {
    "path",
    "paths",
    "source_path",
    "source_paths",
    "file_path",
    "file_paths",
    "location",
    "locations",
    "source_location",
    "source_locations",
    "uri",
    "source_uri",
    "url",
    "source_url",
}


def _looks_external_path(value: str) -> bool:
    stripped = value.strip()
    return (
        stripped.startswith(("file://", "\\", "//"))
        or (len(stripped) >= 3 and stripped[1] == ":" and stripped[2] in "\\/")
    )


def _sanitize_l3_location(value: Any, key: str) -> Any:
    if isinstance(value, list):
        return [_sanitize_l3_location(item, key) for item in value]
    if isinstance(value, dict):
        return sanitize_l3_output(value)
    if not isinstance(value, str):
        return value
    lowered = key.lower()
    if value.startswith("/source_materials"):
        return "/source/<redacted>"
    if lowered in {"path", "paths"} and value.startswith(("/", "/derived", "/normalized", "/control", "/case")):
        return value
    if lowered in {"path", "paths"} and value.startswith("/source/<redacted>"):
        return value
    if _looks_external_path(value) or lowered not in {"path", "paths"}:
        return "<redacted-external-path>"
    return value


def sanitize_l3_output(value: Any) -> Any:
    """Remove protected fields and redact external storage locations in L3."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if is_excluded_key(key):
                continue
            if key.lower() in L3_PATH_KEYS or key.lower().endswith(("_path", "_location", "_uri")):
                result[key] = _sanitize_l3_location(child, key)
            else:
                result[key] = sanitize_l3_output(child)
        return result
    if isinstance(value, list):
        return [sanitize_l3_output(item) for item in value]
    return value


def build_access_proposal(
    case: dict[str, Any],
    args: argparse.Namespace,
    read_path: str,
) -> dict[str, Any]:
    """Return an unapplied access event and Patch suggestion."""
    control = case.get("control", {})
    current_revision = control.get("current_revision", 0) if isinstance(control, dict) else 0
    case_info = case.get("case", {})
    case_id = case_info.get("case_id") if isinstance(case_info, dict) else None
    event = {
        "transaction_id": args.transaction_id or None,
        "actor": args.actor,
        "read_level": args.level.upper(),
        "path": read_path,
        "revision": current_revision,
        "external_read": False,
        "timestamp": now_iso(),
    }
    patch = {
        "patch_id": None,
        "case_id": case_id,
        "base_revision": current_revision,
        "view": "control",
        "operation": "append_access_event",
        "actor": args.actor,
        "reason": "记录受控 JSON 投影访问；仅建议，不自动写回",
        "operations": [
            {
                "op": "add",
                "path": "/control/access_log/-",
                "value": event,
            }
        ],
    }
    return {"applied": False, "event": event, "patch": patch}


def emit(value: Any, pretty: bool) -> None:
    if pretty:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def main() -> int:
    parser = argparse.ArgumentParser(description="按事务约束读取案件 JSON 的有界 L0/L1/L2/L3 投影")
    parser.add_argument("--case", required=True)
    parser.add_argument("--level", choices=["l0", "l1", "l2", "l3"], default="l0")
    parser.add_argument("--view", choices=sorted(LEGACY_VIEW_PROFILES))
    parser.add_argument("--pointer", action="append", help="兼容旧 CLI；L1 可重复，L2 指定单个 JSON Pointer")
    parser.add_argument("--pointers", action="append", nargs="+", help="L1 的一个或多个 JSON Pointer")
    parser.add_argument("--id", dest="entity_id")
    parser.add_argument("--profile", "--operation-profile", "--read-profile", dest="profile")
    parser.add_argument("--field", action="append", help="字段投影，可重复")
    parser.add_argument("--fields", action="append", nargs="+", help="字段投影，可成组指定")
    parser.add_argument("--closure", choices=["none", "dependencies", "evidence", "both", "direct", "all"], default="none")
    parser.add_argument("--dependency-depth", type=int, default=0)
    parser.add_argument("--evidence-depth", type=int)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--max-chars", type=int)
    parser.add_argument("--cursor")
    parser.add_argument("--record-access", action="store_true")
    parser.add_argument("--actor", default="agent")
    parser.add_argument("--transaction-id", default="")
    parser.add_argument("--pretty", action="store_true", help="调试时以缩进格式输出；默认紧凑 JSON")
    args = parser.parse_args()
    path = Path(args.case)
    case = load_json(path)

    profiles_config: dict[str, Any] | None = None
    profile_name: str | None = None
    profile_spec: dict[str, Any] | None = None
    if args.level in {"l0", "l1", "l2", "l3"} and (args.profile or args.view or args.level == "l0"):
        profiles_config = load_slice_profiles()
        if args.profile:
            profile_name, profile_spec = resolve_profile(args.profile, profiles_config)
        elif args.level == "l1" and args.view:
            profile_name, profile_spec = _legacy_view_profile(args.view, profiles_config)
        elif args.level == "l0":
            profile_name, profile_spec = resolve_profile(
                "audit.l0" if not args.view else LEGACY_VIEW_PROFILES[args.view],
                profiles_config,
            )
        elif args.level == "l3" and args.view == "audit":
            profile_name, profile_spec = resolve_profile("audit.l3", profiles_config)

    configured_budget = profile_spec.get("context_budget", {}) if profile_spec else {}
    configured_max_items = configured_budget.get("max_items")
    configured_max_chars = configured_budget.get("max_output_chars")
    default_max_items = 20 if args.level == "l0" else 50
    default_max_chars = 8000 if args.level == "l0" else 20000
    max_items = args.max_items if args.max_items is not None else default_max_items
    max_chars = args.max_chars if args.max_chars is not None else default_max_chars
    # A CLI limit can only tighten the configured cap; it can never enlarge it.
    if isinstance(configured_max_items, int):
        max_items = min(max_items, configured_max_items)
    if isinstance(configured_max_chars, int):
        max_chars = min(max_chars, configured_max_chars)
    if max_items < 0 or max_chars < 128:
        raise SystemExit("--max-items 必须非负，--max-chars 必须至少为 128")

    read_path = "/case + /control index"
    if args.level == "l0":
        result = build_l0(case, max_items)
        state = ProjectionState(max_items)
        meta = projection_meta(
            "L0",
            max_items,
            max_chars,
            state,
            ["/case", "/control/navigation", "/control/current_revision", "/control/summary"],
            profile_name,
            profile_spec=profile_spec,
        )
        result, meta = fit_l0_to_budget(result, meta, max_chars)
    elif args.level == "l1":
        result, meta, read_path = build_l1(case, args, max_items, max_chars, profiles_config)
    elif args.level == "l2":
        result, meta, read_path = build_l2(case, args, max_items, max_chars, profiles_config)
    else:
        from audit_case_json import audit_case

        scope = args.view or "all"
        result = audit_case(case, max_items=max_items, max_chars=max_chars, scope=scope)
        result = sanitize_l3_output(result)
        read_path = "/" if scope == "all" else f"/{scope}"
        meta = None

    if args.record_access:
        proposal = build_access_proposal(case, args, read_path)
        if isinstance(result, dict):
            result["_access_proposal"] = proposal
        else:
            result = {"data": result, "_access_proposal": proposal}

    if meta is not None:
        result = attach_meta(result, meta)
    emit(result, args.pretty)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
