"""Strict, backward-compatible validator for the single-case JSON contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _case_utils import iter_entity_records, load_json, pointer_get, stable_record_id


VIEWS = ["mbse", "search", "drafting", "oa", "invalidity", "audit"]
# The five original view roots remain required so existing case.json files do
# not require an immediate migration. invalidity is an additive, optional root.
REQUIRED_VIEWS = ["mbse", "search", "drafting", "oa", "audit"]
STATUSES = {"fresh", "stale", "blocked", "invalid", "deleted", "superseded", "invalidated"}
VIEW_STATUSES = {"empty", "fresh", "working", "stale", "blocked", "invalid"}
TRANSACTIONS = {"bootstrap_import", "case_json_only", "reimport_material", "export_from_json"}
REFERENCE_KEYS = {
    "source_refs",
    "dependency_ids",
    "depends_on",
    "replaced_by",
    "claim_ids",
    "issue_ids",
    "document_ids",
}
FORBIDDEN_PROJECTION_FIELDS = {"raw_artifacts", "content_base64", "raw_artifact_base64"}
ENTITY_COLLECTION_KEYS = {
    "import_batches",
    "documents",
    "evidence",
    "search_results",
    "technical_facts",
    "claims",
    "issues",
    "entities",
    "chains",
    "relations",
    "protection_units",
    "protection_candidates",
    "search_blocks",
    "comparisons",
    "claim_versions",
    "paths",
    "support_links",
    "events",
    "features",
    "elements",
    "paragraphs",
    "tables",
    "figures",
    "invalidity_requests",
    "invalidity_grounds",
    "response_rounds",
    "claim_feature_charts",
    "evidence_assessments",
    "argument_paths",
    "defense_positions",
    "statement_sections",
    "response_statements",
    "invalidity_snapshots",
}
ENTITY_ID_KEYS = {
    "batch_id",
    "document_id",
    "evidence_id",
    "search_result_id",
    "technical_fact_id",
    "claim_id",
    "issue_id",
    "entity_id",
    "chain_id",
    "relation_id",
    "protection_unit_id",
    "protection_candidate_id",
    "search_block_id",
    "comparison_id",
    "claim_version_id",
    "path_id",
    "support_link_id",
    "feature_id",
    "element_id",
    "paragraph_id",
    "table_id",
    "figure_id",
    "invalidity_request_id",
    "invalidity_ground_id",
    "response_round_id",
    "claim_feature_chart_id",
    "evidence_assessment_id",
    "argument_path_id",
    "defense_position_id",
    "statement_id",
    "statement_section_id",
    "response_statement_id",
    "invalidity_snapshot_id",
}
BUSINESS_ROOTS = {"source_materials", "normalized", "derived"}


def walk(value: Any, path: str = ""):
    if isinstance(value, dict):
        yield value, path or "/"
        for key, child in value.items():
            yield from walk(child, f"{path}/{key}" if path else f"/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}/{index}")


def pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def iter_named_entity_ids(value: Any, path: str = "", root: str | None = None):
    """Find *_id records without treating ordinary *_id references as entities."""
    if isinstance(value, dict):
        current_root = root
        if path.count("/") == 1:
            current_root = path[1:]
        for key, child in value.items():
            child_path = f"{path}/{pointer_escape(key)}" if path else f"/{pointer_escape(key)}"
            if key == "by_id" and isinstance(child, dict) and current_root in BUSINESS_ROOTS:
                for map_id, record in child.items():
                    if not isinstance(map_id, str) or not map_id:
                        continue
                    if isinstance(record, dict) and "id" not in record:
                        candidate = stable_record_id(record) or map_id
                        yield candidate, f"{child_path}/{pointer_escape(map_id)}"
            elif (
                current_root in BUSINESS_ROOTS
                and key in ENTITY_COLLECTION_KEYS
                and isinstance(child, list)
            ):
                for index, record in enumerate(child):
                    if isinstance(record, dict) and "id" not in record:
                        candidate = stable_record_id(record)
                        if candidate:
                            yield candidate, f"{child_path}/{index}"
            yield from iter_named_entity_ids(child, child_path, current_root)


def stable_id_pairs(case: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for root_name in ("source_materials", "normalized", "derived"):
        root = case.get(root_name, {})
        for record, path in iter_entity_records(root, f"/{root_name}"):
            entity_id = stable_record_id(record)
            if entity_id:
                pairs.append((entity_id, path))
    return pairs


def dependency_refs(value: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("dependency_ids", "depends_on"):
        candidate = value.get(key)
        if isinstance(candidate, list):
            refs.extend(item for item in candidate if isinstance(item, str) and item)
    candidate = value.get("dependency_id")
    if isinstance(candidate, str) and candidate:
        refs.append(candidate)
    return refs


def validate_derived_metadata(case: dict[str, Any], errors: list[str]) -> None:
    derived = case.get("derived", {})
    required_meta = (
        "status",
        "input_revision",
        "dependency_ids",
        "dependency_revisions",
        "rule_version",
        "computed_at",
    )
    for view in VIEWS:
        for obj, path in iter_entity_records(
            derived.get(view, {}), f"/derived/{view}"
        ):
            entity_id = stable_record_id(obj)
            if not entity_id:
                continue
            for key in required_meta:
                if key not in obj:
                    errors.append(f"派生对象 {entity_id} 缺少 {key} at {path}")
            if "status" in obj and obj["status"] not in STATUSES:
                errors.append(f"派生对象 {entity_id} 状态非法: {obj['status']}")
            if "input_revision" in obj and not isinstance(obj["input_revision"], int):
                errors.append(f"派生对象 {entity_id} input_revision 不是整数")
            if "dependency_ids" in obj and not isinstance(obj["dependency_ids"], list):
                errors.append(f"派生对象 {entity_id} dependency_ids 不是数组")
            if "dependency_revisions" in obj and not isinstance(
                obj["dependency_revisions"], dict
            ):
                errors.append(f"派生对象 {entity_id} dependency_revisions 不是对象")
            if "rule_version" in obj and not isinstance(obj["rule_version"], str):
                errors.append(f"派生对象 {entity_id} rule_version 不是字符串")
            if "computed_at" in obj and not isinstance(obj["computed_at"], str):
                errors.append(f"派生对象 {entity_id} computed_at 不是字符串")


def validate_indexed_collections(case: dict[str, Any], errors: list[str]) -> None:
    for value, path in walk(case):
        if not isinstance(value, dict) or "by_id" not in value or "order" not in value:
            continue
        by_id = value["by_id"]
        order = value["order"]
        if not isinstance(by_id, dict):
            errors.append(f"by_id 必须是对象 at {path}/by_id")
            continue
        if not isinstance(order, list):
            errors.append(f"order 必须是数组 at {path}/order")
            continue
        seen_order: set[str] = set()
        for item in order:
            if not isinstance(item, str) or not item:
                errors.append(f"order 只能包含非空稳定 ID at {path}/order")
                continue
            if item in seen_order:
                errors.append(f"order 中稳定 ID 重复: {item} at {path}/order")
            seen_order.add(item)
            if item not in by_id:
                errors.append(f"order 引用不存在的 by_id: {item} at {path}/order")
        for map_id, record in by_id.items():
            if not isinstance(map_id, str) or not map_id:
                errors.append(f"by_id 的键必须是非空稳定 ID at {path}/by_id")
            if not isinstance(record, dict):
                errors.append(f"by_id 条目必须是对象: {map_id} at {path}/by_id")
                continue
            embedded_id = stable_record_id(record)
            if embedded_id and embedded_id != map_id:
                errors.append(
                    f"by_id 键与条目稳定 ID 不一致: {map_id} != {embedded_id} "
                    f"at {path}/by_id/{pointer_escape(map_id)}"
                )


def validate_object_index(case: dict[str, Any], pairs: list[tuple[str, str]], errors: list[str]) -> None:
    control = case.get("control", {})
    if "object_index" not in control:
        return
    index = control.get("object_index")
    if not isinstance(index, dict):
        errors.append("/control/object_index 必须是对象")
        return
    indexed_paths: dict[str, str] = {}
    for entity_id, pointer in index.items():
        if not isinstance(entity_id, str) or not entity_id:
            errors.append("/control/object_index 的键必须是非空稳定 ID")
            continue
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            errors.append(f"object_index 的路径不是 JSON Pointer: {entity_id} -> {pointer}")
            continue
        if pointer in indexed_paths and indexed_paths[pointer] != entity_id:
            errors.append(
                f"object_index 路径被多个 ID 使用: {pointer} "
                f"({indexed_paths[pointer]}, {entity_id})"
            )
        indexed_paths[pointer] = entity_id
        try:
            target = pointer_get(case, pointer)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            errors.append(f"object_index 路径无效: {entity_id} -> {pointer} ({exc})")
            continue
        actual_id = stable_record_id(target)
        if actual_id != entity_id:
            errors.append(
                f"object_index 目标 ID 不匹配: {entity_id} -> {pointer}; "
                f"实际为 {actual_id or '无稳定 ID'}"
            )


def validate_reverse_dependency_index(
    case: dict[str, Any],
    pairs: list[tuple[str, str]],
    errors: list[str],
) -> None:
    control = case.get("control", {})
    if "reverse_dependency_index" not in control:
        return
    reverse = control.get("reverse_dependency_index")
    if not isinstance(reverse, dict):
        errors.append("/control/reverse_dependency_index 必须是对象")
        return
    known_ids = {entity_id for entity_id, _ in pairs}
    entities: dict[str, list[dict[str, Any]]] = {}
    for obj, _ in walk(case.get("derived", {}), "/derived"):
        entity_id = stable_record_id(obj)
        if entity_id:
            entities.setdefault(entity_id, []).append(obj)
    for source_id, dependent_ids in reverse.items():
        if not isinstance(source_id, str) or not source_id:
            errors.append("/control/reverse_dependency_index 的键必须是非空稳定 ID")
            continue
        if not isinstance(dependent_ids, list):
            errors.append(f"反向依赖值必须是数组: {source_id}")
            continue
        if len(dependent_ids) != len(set(item for item in dependent_ids if isinstance(item, str))):
            errors.append(f"反向依赖列表存在重复 ID: {source_id}")
        for dependent_id in dependent_ids:
            if not isinstance(dependent_id, str) or not dependent_id:
                errors.append(f"反向依赖列表包含非法 ID: {source_id}")
                continue
            if dependent_id not in known_ids:
                errors.append(f"反向依赖引用未知实体: {source_id} <- {dependent_id}")
                continue
            if not any(source_id in dependency_refs(obj) for obj in entities.get(dependent_id, [])):
                errors.append(
                    f"反向依赖不对应直接依赖: {source_id} <- {dependent_id}"
                )
    for dependent_id, objects in entities.items():
        for obj in objects:
            for source_id in dependency_refs(obj):
                if dependent_id not in reverse.get(source_id, []):
                    errors.append(
                        f"反向依赖缺少映射: {source_id} <- {dependent_id}"
                    )


def validate_view_status(control: dict[str, Any], errors: list[str]) -> None:
    if "view_status" not in control:
        return
    status = control.get("view_status")
    if not isinstance(status, dict):
        errors.append("/control/view_status 必须是对象")
        return
    for view, summary in status.items():
        if not isinstance(summary, dict):
            errors.append(f"view_status 条目必须是对象: {view}")
            continue
        if "status" in summary and summary["status"] not in VIEW_STATUSES:
            errors.append(f"view_status 状态非法: {view} -> {summary['status']}")
        for key in ("active_ids", "reason_ids"):
            if key in summary:
                values = summary[key]
                if not isinstance(values, list) or not all(
                    isinstance(item, str) and item for item in values
                ):
                    errors.append(f"view_status.{key} 必须是稳定 ID 数组: {view}")
                elif len(values) != len(set(values)):
                    errors.append(f"view_status.{key} 存在重复 ID: {view}")
        for key in ("open_gate_count", "pending_question_count"):
            if key in summary and (
                not isinstance(summary[key], int) or summary[key] < 0
            ):
                errors.append(f"view_status.{key} 必须是非负整数: {view}")


def validate_route_selection(value: Any, path: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{path} 必须是对象")
        return False
    for key in ("transaction", "view", "submode", "profile", "phase", "domain"):
        if not isinstance(value.get(key), str) or not value[key]:
            errors.append(f"{path}/{key} 必须是非空字符串")
    if value.get("transaction") not in TRANSACTIONS:
        errors.append(f"{path}/transaction 不是合法事务模式: {value.get('transaction')}")
    if value.get("view") not in set(VIEWS):
        errors.append(f"{path}/view 不是合法业务视图: {value.get('view')}")
    return True


def validate_route_controls(case: dict[str, Any], errors: list[str]) -> None:
    control = case.get("control", {})
    active_route = control.get("active_route")
    if active_route is not None:
        validate_route_selection(active_route, "/control/active_route", errors)

    confirmation = control.get("route_confirmation")
    if confirmation is not None:
        if not isinstance(confirmation, dict):
            errors.append("/control/route_confirmation 必须是对象")
        else:
            allowed = {
                "pending",
                "confirmed",
                "challenge_required",
                "overridden",
                "rejected",
                "expired",
            }
            if confirmation.get("status") not in allowed:
                errors.append(
                    "/control/route_confirmation/status 不是合法状态: "
                    f"{confirmation.get('status')}"
                )
            if "selected_route" in confirmation:
                validate_route_selection(
                    confirmation["selected_route"],
                    "/control/route_confirmation/selected_route",
                    errors,
                )
            if confirmation.get("status") == "confirmed":
                required = (
                    "confirmation_id",
                    "case_id",
                    "base_revision",
                    "confirmed_revision",
                    "selected_route",
                    "confirmed_by",
                    "confirmed_at",
                    "challenge_ids",
                )
                for key in required:
                    if key not in confirmation:
                        errors.append(f"已 confirmed 的 route_confirmation 缺少 {key}")
                current = control.get("current_revision")
                if confirmation.get("confirmed_revision") != current:
                    errors.append(
                        "route_confirmation.confirmed_revision 必须等于 current_revision"
                    )
                if confirmation.get("case_id") != case.get("case", {}).get("case_id"):
                    errors.append("route_confirmation.case_id 与案件不一致")
                base = confirmation.get("base_revision")
                if not isinstance(base, int) or base < 0:
                    errors.append("route_confirmation.base_revision 必须是非负整数")
                if not isinstance(confirmation.get("confirmation_id"), str) or not confirmation.get("confirmation_id"):
                    errors.append("route_confirmation.confirmation_id 必须是非空字符串")
                if not isinstance(confirmation.get("confirmed_at"), str) or not confirmation.get("confirmed_at"):
                    errors.append("route_confirmation.confirmed_at 必须是非空字符串")
            if "challenge_ids" in confirmation:
                ids = confirmation["challenge_ids"]
                if not isinstance(ids, list) or not all(
                    isinstance(item, str) and item for item in ids
                ):
                    errors.append(
                        "/control/route_confirmation/challenge_ids 必须是稳定 ID 数组"
                    )
                elif len(ids) != len(set(ids)):
                    errors.append(
                        "/control/route_confirmation/challenge_ids 存在重复 ID"
                    )

    if active_route is not None and isinstance(confirmation, dict):
        selected = confirmation.get("selected_route")
        if isinstance(selected, dict) and isinstance(active_route, dict):
            for key in (
                "transaction",
                "view",
                "submode",
                "profile",
                "phase",
                "domain",
            ):
                if selected.get(key) != active_route.get(key):
                    errors.append(
                        "active_route 与 route_confirmation.selected_route "
                        f"不一致: {key}"
                    )

    resolutions = control.get("challenge_resolutions")
    if resolutions is not None:
        if not isinstance(resolutions, list):
            errors.append("/control/challenge_resolutions 必须是数组")
        else:
            seen: set[str] = set()
            for index, resolution in enumerate(resolutions):
                path = f"/control/challenge_resolutions/{index}"
                if not isinstance(resolution, dict):
                    errors.append(f"{path} 必须是对象")
                    continue
                challenge_id = resolution.get("challenge_id")
                if not isinstance(challenge_id, str) or not challenge_id:
                    errors.append(f"{path}/challenge_id 必须是非空字符串")
                elif challenge_id in seen:
                    errors.append(f"质疑 ID 重复: {challenge_id}")
                else:
                    seen.add(challenge_id)
                if resolution.get("severity") not in {"hard", "advisory"}:
                    errors.append(f"{path}/severity 必须为 hard 或 advisory")
                if resolution.get("status") not in {
                    "open",
                    "resolved",
                    "rejected",
                    "expired",
                }:
                    errors.append(f"{path}/status 不是合法状态")


def validate_access_log_summary(control: dict[str, Any], errors: list[str]) -> None:
    summary = control.get("access_log_summary")
    if summary is None:
        return
    if not isinstance(summary, dict):
        errors.append("/control/access_log_summary 必须是对象")
        return
    for key in ("event_count", "unique_path_count", "omitted_event_count"):
        if key in summary:
            value = summary[key]
            if not isinstance(value, int) or value < 0:
                errors.append(f"/control/access_log_summary/{key} 必须是非负整数")
    if (
        isinstance(summary.get("event_count"), int)
        and isinstance(summary.get("omitted_event_count"), int)
        and summary["omitted_event_count"] > summary["event_count"]
    ):
        errors.append("access_log_summary.omitted_event_count 不能大于 event_count")
    for key in ("by_level", "by_operation", "by_root"):
        mapping = summary.get(key)
        if mapping is None:
            continue
        if not isinstance(mapping, dict):
            errors.append(f"/control/access_log_summary/{key} 必须是对象")
            continue
        for label, count in mapping.items():
            if not isinstance(label, str) or not label:
                errors.append(f"/control/access_log_summary/{key} 标签必须是非空字符串")
            if not isinstance(count, int) or count < 0:
                errors.append(f"/control/access_log_summary/{key}/{label} 必须是非负整数")


def validate_projection_policy(control: dict[str, Any], errors: list[str]) -> None:
    policy = control.get("projection_policy")
    if policy is not None:
        if not isinstance(policy, dict):
            errors.append("/control/projection_policy 必须是对象")
        else:
            fields = policy.get("forbidden_fields")
            if fields is not None:
                if not isinstance(fields, list) or not all(isinstance(item, str) for item in fields):
                    errors.append("/control/projection_policy/forbidden_fields 必须是字符串数组")
                else:
                    required = {"raw_artifacts", "content_base64"}
                    missing = sorted(required - set(fields))
                    if missing:
                        errors.append(
                            "projection_policy 未声明禁止字段: " + ", ".join(missing)
                        )

    projection = control.get("model_projection")
    if projection is None:
        return
    if not isinstance(projection, dict):
        errors.append("/control/model_projection 必须是对象")
        return
    for obj, path in walk(projection, "/control/model_projection"):
        if isinstance(obj, dict):
            for key in FORBIDDEN_PROJECTION_FIELDS:
                if key in obj:
                    errors.append(
                        f"模型投影禁止包含 {key}: {path}/{pointer_escape(key)}"
                    )


def validate(case: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "schema_version",
        "case",
        "runtime_policy",
        "source_materials",
        "normalized",
        "derived",
        "control",
    ]
    errors.extend(f"缺少顶层字段 /{key}" for key in required if key not in case)
    if case.get("schema_version") != "case-json-1.0":
        errors.append("schema_version 必须为 case-json-1.0")
    if not isinstance(case.get("case", {}).get("case_id"), str) or not case.get("case", {}).get("case_id"):
        errors.append("/case/case_id 必须是非空字符串")
    control = case.get("control", {})
    if not isinstance(control, dict):
        errors.append("/control 必须是对象")
        control = {}
    if not isinstance(control.get("current_revision"), int) or control.get("current_revision", -1) < 0:
        errors.append("/control/current_revision 必须是非负整数")
    derived = case.get("derived", {})
    if not isinstance(derived, dict):
        errors.append("/derived 必须是对象")
        derived = {}
    for view in REQUIRED_VIEWS:
        if not isinstance(derived.get(view), dict):
            errors.append(f"/derived/{view} 必须是对象")

    pairs = stable_id_pairs(case)
    seen: dict[str, str] = {}
    for entity_id, path in pairs:
        if entity_id in seen:
            errors.append(f"稳定 ID 重复: {entity_id} at {seen[entity_id]} and {path}")
        else:
            seen[entity_id] = path

    validate_indexed_collections(case, errors)
    validate_derived_metadata(case, errors)
    validate_object_index(case, pairs, errors)
    validate_reverse_dependency_index(case, pairs, errors)
    validate_view_status(control, errors)
    validate_route_controls(case, errors)
    validate_access_log_summary(control, errors)
    validate_projection_policy(control, errors)

    known = set(seen)
    for obj, path in walk(case):
        if not isinstance(obj, dict):
            continue
        for key, value in obj.items():
            if key not in REFERENCE_KEYS:
                continue
            refs = value if isinstance(value, list) else [value]
            for ref in refs:
                if (
                    isinstance(ref, str)
                    and ref
                    and ref not in known
                    and not ref.startswith(("http://", "https://", "/"))
                ):
                    errors.append(f"断裂引用 {ref} at {path}/{key}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    try:
        errors = validate(load_json(Path(args.case)))
    except Exception as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
