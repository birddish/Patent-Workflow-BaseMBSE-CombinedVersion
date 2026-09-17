"""Read-only whole-case audit summary.

This module intentionally returns findings, counts and stable IDs only. It
never serializes the complete case JSON and skips raw_artifacts and any
*_base64 field while traversing and reporting.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _case_utils import load_json
from inspect_case_json import (
    ENTITY_ID_KEYS,
    REFERENCE_KEYS,
    decode_cursor,
    encode_cursor,
    is_excluded_key,
    pointer_get,
    pointer_join,
    stable_id_of,
)


VIEWS = {"mbse", "search", "drafting", "oa", "invalidity", "audit"}
STATUSES = {"fresh", "stale", "blocked", "invalid", "deleted", "superseded", "invalidated"}


def walk(value: Any, path: str = "/"):
    if isinstance(value, dict):
        yield value, path
        for key, child in value.items():
            if is_excluded_key(key):
                continue
            yield from walk(child, pointer_join(path.rstrip("/"), key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, pointer_join(path.rstrip("/"), str(index)))


def build_id_index(case: dict[str, Any]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    index: dict[str, str] = {}
    findings: list[dict[str, Any]] = []
    for entity, path in walk(case):
        entity_id = stable_id_of(entity)
        if not entity_id:
            continue
        if entity_id in index:
            findings.append({
                "code": "duplicate_id",
                "severity": "high",
                "id": entity_id,
                "paths": [index[entity_id], path],
            })
        else:
            index[entity_id] = path
    case_id = case.get("case", {}).get("case_id")
    if isinstance(case_id, str) and case_id:
        index.setdefault(case_id, "/case/case_id")

    object_index = case.get("control", {}).get("object_index", {})
    if isinstance(object_index, dict):
        for entity_id, entry in object_index.items():
            if not isinstance(entity_id, str):
                continue
            pointer = entry
            if isinstance(entry, dict):
                pointer = entry.get("path") or entry.get("pointer")
            elif isinstance(entry, list) and entry:
                first = entry[0]
                if isinstance(first, str):
                    pointer = first
                elif isinstance(first, dict):
                    pointer = first.get("path") or first.get("pointer")
                else:
                    pointer = None
            if not isinstance(pointer, str):
                continue
            try:
                target = pointer_get(case, pointer)
            except (KeyError, IndexError, ValueError, TypeError):
                findings.append({"code": "stale_object_index", "severity": "high", "id": entity_id, "path": pointer})
                continue
            target_id = stable_id_of(target)
            if target_id and target_id != entity_id:
                findings.append({
                    "code": "object_index_mismatch",
                    "severity": "high",
                    "id": entity_id,
                    "path": pointer,
                    "actual_id": target_id,
                })
    return index, findings


def reference_values(value: Any) -> list[str]:
    if isinstance(value, str):
        if value and not value.startswith(("http://", "https://", "/")):
            return [value]
        return []
    if isinstance(value, list):
        return [item for child in value for item in reference_values(child)]
    return []


def collect_references(obj: dict[str, Any], path: str) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    for key, value in obj.items():
        if is_excluded_key(key):
            continue
        lowered = key.lower()
        is_reference_key = (
            key in REFERENCE_KEYS
            or key.endswith("_ids")
            or key.endswith("_ref")
            or key.endswith("_refs")
        )
        is_own_id = key == "id" or key in ENTITY_ID_KEYS
        if is_reference_key and not is_own_id:
            kind = "evidence" if "evidence" in lowered or "source" in lowered else "dependency"
            for ref in reference_values(value):
                found.append((ref, pointer_join(path.rstrip("/"), key), kind))
    return found


def in_scope(path: str, scope: str, view: str | None) -> bool:
    if view and not path.startswith(f"/derived/{view}"):
        return False
    if scope == "all":
        return True
    if scope == "control":
        return path.startswith("/control")
    if scope == "derived":
        return path.startswith("/derived")
    if scope == "refs":
        return True
    return True


def sanitize_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Keep anomaly identity while hiding source-material storage pointers."""
    result = dict(finding)
    path = result.get("path")
    if isinstance(path, str) and path.startswith("/source_materials"):
        result["path"] = "/source/<redacted>"
    paths = result.get("paths")
    if isinstance(paths, list):
        result["paths"] = [
            "/source/<redacted>" if isinstance(item, str) and item.startswith("/source_materials") else item
            for item in paths
        ]
    return result

def audit_case(
    case: dict[str, Any],
    *,
    max_items: int = 50,
    max_chars: int = 20000,
    cursor: str | None = None,
    scope: str = "all",
    view: str | None = None,
) -> dict[str, Any]:
    known_ids, findings = build_id_index(case)
    summary: dict[str, Any] = {
        "objects_checked": 0,
        "collections_checked": 0,
        "broken_references": 0,
        "duplicate_ids": sum(1 for item in findings if item.get("code") == "duplicate_id"),
        "stale_objects": 0,
        "invalid_objects": 0,
        "blocked_objects": 0,
        "ownership_violations": 0,
        "object_index_entries": len(case.get("control", {}).get("object_index", {}))
        if isinstance(case.get("control", {}).get("object_index", {}), dict)
        else 0,
    }

    for obj, path in walk(case):
        if not in_scope(path, scope, view):
            continue
        summary["objects_checked"] += 1
        status = obj.get("status")
        if status == "stale":
            summary["stale_objects"] += 1
        elif status in {"invalid", "invalidated"}:
            summary["invalid_objects"] += 1
        elif status == "blocked":
            summary["blocked_objects"] += 1
        for key, child in obj.items():
            if not is_excluded_key(key) and isinstance(child, (dict, list)):
                summary["collections_checked"] += 1

        entity_id = stable_id_of(obj)
        if entity_id and path.startswith("/derived/") and path.count("/") >= 3:
            required = [
                "status",
                "input_revision",
                "dependency_ids",
                "dependency_revisions",
                "rule_version",
                "computed_at",
            ]
            missing = [key for key in required if key not in obj]
            if missing:
                findings.append({
                    "code": "derived_metadata_missing",
                    "severity": "medium",
                    "id": entity_id,
                    "path": path,
                    "missing": missing,
                })

        for ref, ref_path, kind in collect_references(obj, path):
            if ref in known_ids:
                continue
            summary["broken_references"] += 1
            findings.append({
                "code": "broken_reference",
                "severity": "high",
                "id": ref,
                "path": ref_path,
                "kind": kind,
            })

    severity_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(
        key=lambda item: (
            severity_order.get(str(item.get("severity")), 9),
            str(item.get("path", "")),
            str(item.get("id", "")),
        )
    )

    decoded = decode_cursor(cursor)
    start = decoded.get("index", 0) if decoded and isinstance(decoded.get("index", 0), int) else 0
    start = max(0, start)
    selected = [sanitize_finding(item) for item in findings[start : start + max(0, max_items)]]
    payload: dict[str, Any] = {
        "revision": case.get("control", {}).get("current_revision", 0),
        "summary": summary,
        "findings": selected,
        "next_input_ids": list(dict.fromkeys(
            str(item["id"]) for item in selected if isinstance(item.get("id"), str)
        )),
        "truncated": start + len(selected) < len(findings),
        "over_limit": False,
        "next_cursor": None,
        "excluded_by_default": ["binary_payloads", "*_base64"],
    }
    if payload["truncated"]:
        payload["next_cursor"] = encode_cursor({"index": start + len(selected)})
    if cursor and decoded is None:
        payload["cursor_error"] = "invalid_cursor"

    budget = max(256, max_chars - 500)
    estimated = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    while estimated > budget and payload["findings"]:
        payload["findings"].pop()
        payload["truncated"] = True
        payload["over_limit"] = True
        payload["next_cursor"] = encode_cursor({"index": start + len(payload["findings"])})
        payload["next_input_ids"] = list(dict.fromkeys(
            str(item["id"]) for item in payload["findings"] if isinstance(item.get("id"), str)
        ))
        estimated = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    if estimated > budget:
        payload["findings"] = []
        payload["next_input_ids"] = []
        payload["over_limit"] = True
        payload["truncated"] = bool(findings)
        payload["next_cursor"] = encode_cursor({"index": start}) if findings else None
        payload["limit_reason"] = "audit_summary_exceeds_char_budget"
    payload["estimated_chars"] = estimated
    return payload


def emit(value: Any, pretty: bool) -> None:
    if pretty:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def main() -> int:
    parser = argparse.ArgumentParser(description="输出案件 JSON 的全案异常摘要，不输出完整 case.json")
    parser.add_argument("--case", required=True)
    parser.add_argument("--scope", choices=["all", "control", "derived", "refs"], default="all")
    parser.add_argument("--view", choices=sorted(VIEWS))
    parser.add_argument("--max-items", type=int, default=50)
    parser.add_argument("--max-chars", type=int, default=20000)
    parser.add_argument("--cursor")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.max_items < 0 or args.max_chars < 128:
        raise SystemExit("--max-items 必须非负，--max-chars 必须至少为 128")
    result = audit_case(
        load_json(Path(args.case)),
        max_items=args.max_items,
        max_chars=args.max_chars,
        cursor=args.cursor,
        scope=args.scope,
        view=args.view,
    )
    emit(result, args.pretty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
