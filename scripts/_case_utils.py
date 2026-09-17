"""Small standard-library helpers shared by the case JSON command-line tools."""
from __future__ import annotations

import copy
import datetime as _dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any


VIEWS = {"mbse", "search", "drafting", "oa", "invalidity", "audit", "control", "import"}
ROOTS = ("source_materials", "normalized", "derived", "control", "case", "runtime_policy")
# Shared business identity vocabulary. Reference-only IDs are deliberately
# kept separate so a nested dependency/source value is never an entity.
ENTITY_ID_KEYS = frozenset(
    {
        "batch_id", "document_id", "evidence_id", "search_result_id",
        "technical_fact_id", "claim_id", "issue_id", "entity_id",
        "chain_id", "relation_id", "protection_unit_id",
        "protection_candidate_id", "search_block_id", "comparison_id",
        "claim_version_id", "path_id", "support_link_id", "feature_id",
        "element_id", "paragraph_id", "table_id", "figure_id", "model_id",
        "claim_set_id", "snapshot_id", "strategy_id", "run_id", "profile_id",
        "document_version_id", "claim_mapping_id", "claim_chart_id",
        "claim_path_id", "event_id", "source_material_id",
        "invalidity_request_id", "invalidity_ground_id", "response_round_id",
        "claim_feature_chart_id", "evidence_assessment_id", "argument_path_id",
        "defense_position_id", "statement_id", "statement_section_id",
        "response_statement_id", "invalidity_snapshot_id",
    }
)

REFERENCE_ID_KEYS = frozenset(
    {
        "dependency_id", "transaction_id", "revision_id", "source_id",
        "parent_id", "owner_id", "target_id", "related_id", "reference_id",
        "input_id", "output_id", "source_document_id", "source_material_id",
        "input_document_id", "input_version_id", "tool_or_model_id",
    }
)

ENTITY_COLLECTION_KEYS = frozenset(
    {
        "import_batches", "documents", "evidence", "search_results",
        "technical_facts", "claims", "issues", "entities", "chains",
        "relations", "protection_units", "protection_candidates", "search_blocks",
        "comparisons", "claim_versions", "paths", "support_links", "events",
        "features", "elements", "paragraphs", "tables", "figures",
        "claim_mappings", "claim_charts", "claim_paths", "issue_registry",
        "strategies", "snapshots", "technical_effects", "feature_coverage",
        "landscape_maps", "fto_comparisons", "search_elements",
        "invalidity_requests", "invalidity_grounds", "response_rounds",
        "claim_feature_charts", "evidence_assessments", "argument_paths",
        "defense_positions", "statement_sections", "response_statements",
        "invalidity_snapshots",
    }
)

_COLLECTION_ID_KEYS = {
    "import_batches": "batch_id", "documents": "document_id", "evidence": "evidence_id",
    "search_results": "search_result_id", "technical_facts": "technical_fact_id",
    "claims": "claim_id", "issues": "issue_id", "entities": "entity_id",
    "chains": "chain_id", "relations": "relation_id", "protection_units": "protection_unit_id",
    "protection_candidates": "protection_candidate_id", "search_blocks": "search_block_id",
    "comparisons": "comparison_id", "claim_versions": "claim_version_id", "paths": "path_id",
    "support_links": "support_link_id", "events": "event_id", "features": "feature_id",
    "elements": "element_id", "paragraphs": "paragraph_id", "tables": "table_id",
    "figures": "figure_id", "claim_mappings": "claim_mapping_id", "claim_charts": "claim_chart_id",
    "claim_paths": "claim_path_id", "issue_registry": "issue_id", "strategies": "strategy_id",
    "snapshots": "snapshot_id",
    "invalidity_requests": "invalidity_request_id", "invalidity_grounds": "invalidity_ground_id",
    "response_rounds": "response_round_id", "claim_feature_charts": "claim_feature_chart_id",
    "evidence_assessments": "evidence_assessment_id", "argument_paths": "argument_path_id",
    "defense_positions": "defense_position_id", "statement_sections": "statement_section_id",
    "response_statements": "response_statement_id", "invalidity_snapshots": "invalidity_snapshot_id",
}


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError("案件 JSON 顶层必须是对象")
    return value


def save_json_atomic(path: str | Path, value: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(value, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, p)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def pointer_tokens(pointer: str) -> list[str]:
    if pointer in ("", "/"):
        return [] if pointer == "" else [""]
    if not pointer.startswith("/"):
        raise ValueError(f"JSON Pointer 必须以 / 开头: {pointer}")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]


def pointer_get(doc: Any, pointer: str) -> Any:
    current = doc
    for token in pointer_tokens(pointer):
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise KeyError(pointer)
    return current


def pointer_parent(doc: Any, pointer: str) -> tuple[Any, str]:
    tokens = pointer_tokens(pointer)
    if not tokens:
        raise ValueError("不能对 JSON 根对象使用 add/replace/remove")
    parent = doc
    for token in tokens[:-1]:
        if isinstance(parent, list):
            parent = parent[int(token)]
        elif isinstance(parent, dict):
            parent = parent[token]
        else:
            raise KeyError(pointer)
    return parent, tokens[-1]


def _is_candidate_id_key(key: str) -> bool:
    lowered = key.lower()
    return (
        key in ENTITY_ID_KEYS
        and key not in REFERENCE_ID_KEYS
        and not lowered.endswith("_ref")
        and not lowered.endswith("_refs")
        and not lowered.endswith("_ids")
    )


def stable_record_id(value: Any, *, collection_key: str | None = None) -> str | None:
    """Return an entity stable ID without promoting a pure reference."""
    if not isinstance(value, dict):
        return None
    direct = value.get("id")
    if isinstance(direct, str) and direct:
        return direct

    expected_key = _COLLECTION_ID_KEYS.get(collection_key or "")
    if expected_key and _is_candidate_id_key(expected_key):
        expected = value.get(expected_key)
        if isinstance(expected, str) and expected:
            return expected

    candidates: list[str] = []
    for key, candidate in value.items():
        if not isinstance(candidate, str) or not candidate or not key.endswith("_id"):
            continue
        if _is_candidate_id_key(key):
            candidates.append(candidate)
    if len(candidates) == 1:
        return candidates[0]
    return None


def iter_entity_records(value: Any, path: str = ""):
    """Yield immediate records in named collections, excluding nested references."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{key}" if path else f"/{key}"
            if key not in ENTITY_COLLECTION_KEYS:
                yield from iter_entity_records(child, child_path)
                continue
            if isinstance(child, list):
                for index, record in enumerate(child):
                    record_path = f"{child_path}/{index}"
                    if isinstance(record, dict) and stable_record_id(record, collection_key=key):
                        yield record, record_path
                    yield from iter_entity_records(record, record_path)
            elif isinstance(child, dict) and isinstance(child.get("by_id"), dict):
                for map_id, record in child["by_id"].items():
                    record_path = f"{child_path}/by_id/{map_id}"
                    if isinstance(record, dict) and stable_record_id(record, collection_key=key):
                        yield record, record_path
                    yield from iter_entity_records(record, record_path)
            else:
                yield from iter_entity_records(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_entity_records(child, f"{path}/{index}" if path else f"/{index}")

def all_ids(value: Any, path: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        if isinstance(value.get("id"), str) and value["id"]:
            found.append((value["id"], path or "/"))
        for key, child in value.items():
            child_path = f"{path}/{key}" if path else f"/{key}"
            found.extend(all_ids(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(all_ids(child, f"{path}/{index}"))
    return found


def view_root(view: str) -> str:
    if view in {"mbse", "search", "drafting", "oa", "invalidity", "audit"}:
        return f"/derived/{view}"
    if view == "import":
        return "/source_materials"
    if view == "control":
        return "/control"
    raise ValueError(f"不支持的视图: {view}")


def path_owned_by_view(path: str, view: str) -> bool:
    if view == "import":
        return path == "/source_materials" or path.startswith("/source_materials/") or path == "/normalized" or path.startswith("/normalized/") or path.startswith("/control/")
    if view == "control":
        return path == "/control" or path.startswith("/control/")
    if view in {"mbse", "search", "drafting", "oa", "invalidity", "audit"}:
        return path == f"/derived/{view}" or path.startswith(f"/derived/{view}/")
    return False


def new_case(case_id: str, title: str = "") -> dict[str, Any]:
    return {
        "schema_version": "case-json-1.0",
        "case": {"case_id": case_id, "title": title, "technical_domain": "pending"},
        "runtime_policy": {"default_transaction": "case_json_only", "external_read_requires": "bootstrap_or_explicit_reimport"},
        "source_materials": {"import_batches": [], "documents": [], "evidence": [], "search_results": [], "raw_artifacts": []},
        "normalized": {"technical_facts": [], "documents": [], "claims": [], "issues": [], "entities": []},
        "derived": {"mbse": {}, "search": {}, "drafting": {}, "oa": {}, "invalidity": {}, "audit": {}},
        "control": {
            "current_revision": 0,
            "navigation": {},
            "summary": {},
            "open_gates": [],
            "pending_questions": [],
            "conflicts": [],
            "transactions": [],
            "access_log": [],
            "change_log": [],
            "dependency_index": {},
        },
    }


def deep_copy(value: Any) -> Any:
    return copy.deepcopy(value)
