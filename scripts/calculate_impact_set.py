"""Calculate a bounded dependency impact set without mutating case.json."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from _case_utils import iter_entity_records, load_json, pointer_get, stable_record_id


TERMINAL_STATUSES = {"deleted", "superseded", "invalidated", "invalid"}


def _derived_entities(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entities: dict[str, dict[str, Any]] = {}
    for record, path in iter_entity_records(case.get("derived", {}), "/derived"):
        entity_id = stable_record_id(record)
        if entity_id:
            entities[entity_id] = {"record": record, "path": path}
    return entities


def _reverse_dependencies(
    case: dict[str, Any],
    entities: dict[str, dict[str, Any]],
) -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = defaultdict(set)
    configured = case.get("control", {}).get("reverse_dependency_index", {})
    if isinstance(configured, dict):
        for source_id, dependent_ids in configured.items():
            if isinstance(source_id, str) and isinstance(dependent_ids, list):
                reverse[source_id].update(
                    item for item in dependent_ids if isinstance(item, str) and item
                )

    legacy = case.get("control", {}).get("dependency_index", {})
    if isinstance(legacy, dict):
        for entity_id, record in legacy.items():
            dependencies = (
                record.get("dependencies", record.get("dependency_ids", []))
                if isinstance(record, dict)
                else record
            )
            if isinstance(entity_id, str) and isinstance(dependencies, list):
                for source_id in dependencies:
                    if isinstance(source_id, str) and source_id:
                        reverse[source_id].add(entity_id)

    for entity_id, entry in entities.items():
        dependencies = entry["record"].get("dependency_ids", [])
        if isinstance(dependencies, list):
            for source_id in dependencies:
                if isinstance(source_id, str) and source_id:
                    reverse[source_id].add(entity_id)
    return reverse


def _ids_from_paths(case: dict[str, Any], changed_paths: list[str]) -> set[str]:
    resolved: set[str] = set()
    object_index = case.get("control", {}).get("object_index", {})
    if isinstance(object_index, dict):
        for entity_id, indexed_path in object_index.items():
            if not isinstance(entity_id, str) or not isinstance(indexed_path, str):
                continue
            for changed_path in changed_paths:
                normalized = changed_path.rstrip("/") or "/"
                if (
                    indexed_path == normalized
                    or indexed_path.startswith(normalized + "/")
                    or normalized.startswith(indexed_path.rstrip("/") + "/")
                ):
                    resolved.add(entity_id)

    for changed_path in changed_paths:
        try:
            target = pointer_get(case, changed_path)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        entity_id = stable_record_id(target)
        if entity_id:
            resolved.add(entity_id)
    return resolved


def calculate(
    case: dict[str, Any],
    changed_ids: list[str],
    changed_paths: list[str],
    change_kind: str,
) -> dict[str, Any]:
    entities = _derived_entities(case)
    sources = set(item for item in changed_ids if item)
    sources.update(_ids_from_paths(case, changed_paths))
    reverse = _reverse_dependencies(case, entities)

    impacted = set(sources)
    queue = deque(sorted(sources))
    while queue:
        source_id = queue.popleft()
        for dependent_id in sorted(reverse.get(source_id, ())):
            if dependent_id not in impacted:
                impacted.add(dependent_id)
                queue.append(dependent_id)

    affected_derived = sorted(entity_id for entity_id in impacted if entity_id in entities)
    recommendations: list[dict[str, Any]] = []
    target_status = "invalid" if change_kind == "remove" else "stale"
    for entity_id in affected_derived:
        entry = entities[entity_id]
        current_status = entry["record"].get("status")
        recommended_status = (
            current_status if current_status in TERMINAL_STATUSES else target_status
        )
        recommendations.append(
            {
                "id": entity_id,
                "path": entry["path"],
                "current_status": current_status,
                "recommended_status": recommended_status,
            }
        )

    unaffected_fresh = sorted(
        entity_id
        for entity_id, entry in entities.items()
        if entity_id not in impacted and entry["record"].get("status") == "fresh"
    )
    object_index = case.get("control", {}).get("object_index", {})
    impacted_paths = sorted(
        {
            object_index[entity_id]
            for entity_id in impacted
            if isinstance(object_index, dict)
            and isinstance(object_index.get(entity_id), str)
        }
    )
    return {
        "status": "ok",
        "current_revision": case.get("control", {}).get("current_revision", 0),
        "change_kind": change_kind,
        "changed_ids": sorted(set(changed_ids)),
        "changed_paths": sorted(set(changed_paths)),
        "resolved_source_ids": sorted(sources),
        "impacted_ids": sorted(impacted),
        "affected_derived_ids": affected_derived,
        "impacted_paths": impacted_paths,
        "status_recommendations": recommendations,
        "unaffected_fresh_ids": unaffected_fresh,
        "write_performed": False,
        "next_action": "由总控生成受限 Patch，经用户确认后写回建议状态。",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--changed-id", action="append", default=[])
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument(
        "--change-kind",
        choices=["add", "replace", "remove"],
        default="replace",
    )
    args = parser.parse_args()
    if not args.changed_id and not args.changed_path:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "errors": ["必须至少提供一个 --changed-id 或 --changed-path"],
                    "write_performed": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    case = load_json(Path(args.case))
    print(
        json.dumps(
            calculate(
                case,
                args.changed_id,
                args.changed_path,
                args.change_kind,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())