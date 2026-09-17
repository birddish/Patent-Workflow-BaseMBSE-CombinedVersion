"""Validate versioned view Patches before they can change a case JSON.

The validator is deliberately independent from the commit command. It does
not write files and exposes the historical validate(case, patch) API used by
the compatibility wrapper. A Patch is accepted only when the current case
revision, the persisted user confirmation, the selected route and the owned
JSON namespace all agree.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

from _case_utils import (
    load_json,
    path_owned_by_view,
    pointer_get,
    pointer_parent,
    pointer_tokens,
    stable_record_id,
)
from validate_case_json import validate as validate_case


BUSINESS_VIEWS = {"mbse", "search", "drafting", "oa", "invalidity", "audit"}
ALLOWED_VIEWS = BUSINESS_VIEWS | {"control", "import"}
ROUTE_FIELDS = ("transaction", "view", "submode", "profile", "phase", "domain")
TRANSACTIONS = {
    "bootstrap_import",
    "case_json_only",
    "reimport_material",
    "export_from_json",
}

# The case validator has a deliberately conservative historical status set.
# Patch governance additionally understands workflow statuses used by views.
STATUSES = {
    "empty",
    "fresh",
    "working",
    "stale",
    "blocked",
    "invalid",
    "candidate",
    "conditional",
    "pending_review",
    "mocked_pass",
    "pass",
    "confirmed",
    "open",
    "resolved",
    "rejected",
    "deleted",
    "superseded",
    "preview",
    "conflict",
    "aborted",
    "committed",
    "awaiting_confirmation",
    "processing",
    "pending",
    "invalidated",
}
TERMINAL_STATUSES = {"deleted", "superseded", "invalidated"}
FORBIDDEN_ENTITY_ID_TOKENS = {"", "-"}
IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _pointer_error(pointer: Any) -> str | None:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return "不是 JSON Pointer（必须以 / 开头）"
    # RFC 6901 permits only ~0 and ~1 escapes.
    if any(re.search(r"~(?![01])", token) for token in pointer[1:].split("/")):
        return "包含非法 ~ 转义"
    return None


def _route_from_patch(patch: dict[str, Any]) -> dict[str, Any]:
    """Return route fields explicitly carried by a Patch, if any."""
    route: dict[str, Any] = {}
    for key in ("route", "route_selection", "selected_route"):
        value = patch.get(key)
        if isinstance(value, dict):
            route.update({field: value.get(field) for field in ROUTE_FIELDS if field in value})
            break
    for field in ROUTE_FIELDS:
        if field in patch:
            route[field] = patch[field]
    return route


def _validate_route_binding(case: dict[str, Any], patch: dict[str, Any], errors: list[str]) -> None:
    control = case.get("control")
    if not isinstance(control, dict):
        errors.append("缺少 /control，无法验证 route_confirmation")
        return
    current = control.get("current_revision")
    confirmation = control.get("route_confirmation")
    if not isinstance(confirmation, dict):
        errors.append("缺少有效 /control/route_confirmation；Patch 不能自行替代用户明文确认")
        return
    if confirmation.get("status") != "confirmed":
        errors.append("/control/route_confirmation/status 必须为 confirmed")
    confirmation_id = confirmation.get("confirmation_id")
    if not isinstance(confirmation_id, str) or not confirmation_id.strip():
        errors.append("/control/route_confirmation/confirmation_id 必须为非空字符串")
    case_id = case.get("case", {}).get("case_id") if isinstance(case.get("case"), dict) else None
    if confirmation.get("case_id") != case_id:
        errors.append("/control/route_confirmation/case_id 与案件 case.case_id 不一致")
    confirmed_revision = confirmation.get("confirmed_revision")
    if not _is_int(confirmed_revision) or confirmed_revision != current:
        errors.append(
            "/control/route_confirmation/confirmed_revision 必须等于 "
            f"control.current_revision（当前为 {current!r}）"
        )
    selected = confirmation.get("selected_route")
    if not isinstance(selected, dict):
        errors.append("/control/route_confirmation/selected_route 必须是对象")
        return
    for field in ROUTE_FIELDS:
        if not isinstance(selected.get(field), str) or not selected.get(field):
            errors.append(f"/control/route_confirmation/selected_route/{field} 缺失或不是非空字符串")
    if selected.get("transaction") not in TRANSACTIONS:
        errors.append("route_confirmation.selected_route.transaction 不是合法事务模式")
    elif selected.get("transaction") not in {"case_json_only", "reimport_material"}:
        errors.append("export_from_json 和 bootstrap_import 路由不得用于已有案件的 Patch 写回")

    patch_transaction = patch.get("transaction")
    if isinstance(patch_transaction, str) and selected.get("transaction") != patch_transaction:
        errors.append(
            "Patch transaction 与 route_confirmation.selected_route.transaction 必须精确一致"
        )

    explicit_route = _route_from_patch(patch)
    for field, value in explicit_route.items():
        if field == "view" and patch.get("view") == "import" and patch.get("transaction") == "reimport_material":
            continue  # import 是事务写入者，不是已确认的后续业务视图
        if not isinstance(value, str) or not value:
            errors.append(f"Patch 路由字段 {field} 必须是非空字符串")
        elif selected.get(field) != value:
            errors.append(
                f"Patch 路由字段 {field}={value!r} 与已确认路由 "
                f"{field}={selected.get(field)!r} 不一致"
            )

    view = patch.get("view")
    selected_view = selected.get("view")
    if view in BUSINESS_VIEWS and selected_view != view:
        errors.append(f"Patch view={view} 与 route_confirmation.selected_route.view={selected_view} 不一致")
    if view == "import" and selected.get("transaction") != "reimport_material":
        errors.append("view=import 的已有案件 Patch 只能绑定 reimport_material 路由")
    if view == "import" and "transaction" in patch and patch.get("transaction") != selected.get("transaction"):
        errors.append("import Patch 的 transaction 与已确认事务不一致")
    if view == "control" and "route_view" in patch and patch.get("route_view") != selected_view:
        errors.append("control Patch 的 route_view 与已确认路由不一致")

    supplied_confirmation_id = patch.get("confirmation_id", patch.get("route_confirmation_id"))
    if supplied_confirmation_id is not None and supplied_confirmation_id != confirmation_id:
        errors.append("Patch confirmation_id 与当前 route_confirmation 不一致")

    active = control.get("active_route")
    if isinstance(active, dict):
        for field in ROUTE_FIELDS:
            if field in active and active.get(field) != selected.get(field):
                errors.append(f"/control/active_route 与 route_confirmation.selected_route 不一致: {field}")


def _validate_reimport_scope(case: dict[str, Any], patch: dict[str, Any], errors: list[str]) -> None:
    """Bind every import Patch to the exact confirmed material and strategy scope."""
    if patch.get("transaction") != "reimport_material":
        return
    confirmation = case.get("control", {}).get("route_confirmation", {})
    scope = confirmation.get("import_scope") if isinstance(confirmation, dict) else None
    if not isinstance(scope, dict):
        errors.append("reimport_material 必须具有当前 route_confirmation.import_scope；历史兼容告警不能代替明文确认")
        return
    files = scope.get("files")
    if not isinstance(files, list) or not files or any(not isinstance(item, str) or not item for item in files):
        errors.append("route_confirmation.import_scope.files 必须为非空文件路径数组")
        return
    if patch.get("strategy") != scope.get("strategy") or patch.get("old_batch_policy") != scope.get("old_batch_policy"):
        errors.append("reimport Patch 的 strategy/old_batch_policy 与当前确认范围不一致")
    allowed_paths = {
        "/source_materials/import_batches/-", "/source_materials/documents/-",
        "/source_materials/raw_artifacts/-", "/normalized/documents/-",
        "/control/open_gates/-",
    }
    operations = patch.get("operations", [])
    if not isinstance(operations, list):
        return
    for item in operations:
        if isinstance(item, dict) and (item.get("op") != "add" or item.get("path") not in allowed_paths):
            errors.append(f"reimport Patch 包含未授权操作: {item.get('path')}")
    batches = [item.get("value") for item in operations if isinstance(item, dict) and item.get("path") == "/source_materials/import_batches/-"]
    documents = [item.get("value") for item in operations if isinstance(item, dict) and item.get("path") == "/source_materials/documents/-"]
    if len(batches) != 1 or not isinstance(batches[0], dict):
        errors.append("reimport Patch 必须且只能追加一个导入批次")
        return
    batch = batches[0]
    if batch.get("strategy") != scope.get("strategy") or batch.get("old_batch_policy") != scope.get("old_batch_policy"):
        errors.append("导入批次策略与已确认 import_scope 不一致")
    if sorted(batch.get("source_files", [])) != sorted(files):
        errors.append("导入批次 source_files 与已确认文件清单不一致")
    if len(documents) != len(files) or any(not isinstance(item, dict) for item in documents):
        errors.append("reimport Patch 的文档数量与已确认文件清单不一致")
    elif sorted(item.get("source_path") for item in documents) != sorted(files):
        errors.append("reimport Patch 的文档来源路径与已确认文件清单不一致")
    if sorted(batch.get("document_ids", [])) != sorted(item.get("document_id") for item in documents if isinstance(item, dict)):
        errors.append("导入批次 document_ids 与实际新增文档不一致")

def _record_ids(value: Any, collection_key: str | None = None) -> set[str]:
    """Collect entity IDs from records, excluding dependency/reference IDs."""
    found: set[str] = set()
    if isinstance(value, dict):
        record_id = stable_record_id(value, collection_key=collection_key)
        if record_id:
            found.add(record_id)
        for key, child in value.items():
            next_collection = key if isinstance(child, (list, dict)) else None
            found.update(_record_ids(child, next_collection))
    elif isinstance(value, list):
        for child in value:
            found.update(_record_ids(child, collection_key))
    return found


def _ids_in_path(case: dict[str, Any], path: str) -> set[str]:
    ids: set[str] = set()
    tokens = pointer_tokens(path)
    for index, token in enumerate(tokens[:-1]):
        if token == "by_id" and index + 1 < len(tokens):
            candidate = tokens[index + 1]
            if candidate not in FORBIDDEN_ENTITY_ID_TOKENS and not candidate.isdigit():
                ids.add(candidate)
    try:
        target = pointer_get(case, path)
    except (KeyError, IndexError, TypeError, ValueError):
        target = None
    ids.update(_record_ids(target))
    return ids


def _simulate_one(document: Any, operation: dict[str, Any]) -> None:
    op = operation.get("op")
    path = operation["path"]
    if op == "test":
        if pointer_get(document, path) != operation.get("value"):
            raise ValueError(f"test 失败: {path}")
        return
    parent, token = pointer_parent(document, path)
    if isinstance(parent, list):
        if token != "-" or op != "add":
            raise ValueError(f"数组只能通过 /- 追加对象，不能执行 {op}: {path}")
        parent.append(copy.deepcopy(operation["value"]))
        return
    if not isinstance(parent, dict):
        raise TypeError(f"父路径不可写: {path}")
    if op == "add":
        if token in parent:
            raise ValueError(f"add 不能覆盖现有字段，请使用 replace: {path}")
        parent[token] = copy.deepcopy(operation["value"])
    elif op == "replace":
        if token not in parent:
            raise KeyError(path)
        parent[token] = copy.deepcopy(operation["value"])
    elif op == "remove":
        if token not in parent:
            raise KeyError(path)
        del parent[token]
    else:
        raise ValueError(f"不支持 op={op}")


def _status_records(document: Any) -> dict[str, tuple[str, dict[str, Any]]]:
    result: dict[str, tuple[str, dict[str, Any]]] = {}

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("status"), str):
                identity = stable_record_id(value)
                if identity:
                    result[f"{path}#status"] = (value["status"], value)
            for key, child in value.items():
                walk(child, f"{path}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}/{index}")

    walk(document, "")
    return result


def _validate_status_changes(before: dict[str, Any], after: dict[str, Any], errors: list[str]) -> None:
    before_records = _status_records(before)
    after_records = _status_records(after)
    for key, (new_status, _record) in after_records.items():
        old_status = before_records.get(key, (None, {}))[0]
        # Validate only changed or newly added records. Unmodified source
        # snapshots and control transaction history are outside this Patch's
        # status-transition scope.
        if old_status is not None and old_status == new_status:
            continue
        if new_status not in STATUSES:
            errors.append(f"状态非法: {new_status!r} at {key}")
            continue
        if old_status in TERMINAL_STATUSES:
            errors.append(f"禁止从终态 {old_status} 恢复或改写为 {new_status}: {key}")

    for key, (new_status, record) in after_records.items():
        old_status = before_records.get(key, (None, {}))[0]
        if new_status != "deleted" or old_status == "deleted":
            continue
        required = ("deleted_by", "deleted_at", "reason", "replacement_id")
        missing = [field for field in required if field not in record]
        if missing:
            errors.append(f"逻辑删除对象缺少元数据 {missing}: {key}")
            continue
        for field in ("deleted_by", "deleted_at", "reason"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                errors.append(f"逻辑删除字段 {field} 必须是非空字符串: {key}")
        replacement = record.get("replacement_id")
        if replacement is not None and (not isinstance(replacement, str) or not replacement.strip()):
            errors.append(f"逻辑删除字段 replacement_id 必须为稳定 ID 或 null: {key}")


def _validate_entity_identity(before: dict[str, Any], patch: dict[str, Any], after: dict[str, Any], errors: list[str]) -> None:
    expected = patch.get("expected_affected_entities")
    expected_ids: set[str] = set()
    if not isinstance(expected, list) or not expected:
        errors.append("expected_affected_entities 必须是非空稳定 ID 数组")
    else:
        for item in expected:
            if not isinstance(item, str) or not item.strip() or item.isdigit() or not IDENTIFIER_RE.match(item):
                errors.append(f"expected_affected_entities 含非法稳定 ID: {item!r}")
            elif item in expected_ids:
                errors.append(f"expected_affected_entities 存在重复 ID: {item}")
            else:
                expected_ids.add(item)

    direct_ids: set[str] = set()
    for operation in patch.get("operations", []):
        if not isinstance(operation, dict) or not isinstance(operation.get("path"), str):
            continue
        direct_ids.update(_ids_in_path(before, operation["path"]))
        if operation.get("op") in {"add", "replace", "test"}:
            direct_ids.update(_record_ids(operation.get("value")))
    missing = sorted(direct_ids - expected_ids)
    if missing:
        errors.append(f"expected_affected_entities 未覆盖 Patch 直接影响实体: {missing}")

    # Removing an entity object is a physical deletion. It must be represented
    # by status=deleted plus the four required deletion fields.
    for operation in patch.get("operations", []):
        if not isinstance(operation, dict) or operation.get("op") != "remove":
            continue
        path = operation.get("path")
        if not isinstance(path, str):
            continue
        try:
            target = pointer_get(before, path)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if _record_ids(target):
            errors.append(f"禁止物理删除实体对象，请使用逻辑删除元数据: {path}")


def _candidate_errors(before: dict[str, Any], patch: dict[str, Any], errors: list[str]) -> dict[str, Any] | None:
    candidate = copy.deepcopy(before)
    try:
        for operation in patch.get("operations", []):
            _simulate_one(candidate, operation)
    except Exception as exc:
        errors.append(f"Patch 操作无法应用: {exc}")
        return None

    _validate_status_changes(before, candidate, errors)
    _validate_entity_identity(before, patch, candidate, errors)
    # Reuse the case-level validator for Schema, duplicate stable IDs and
    # reference closure. This is still a read-only candidate check.
    for item in validate_case(candidate):
        errors.append(f"候选案件 Schema/引用校验失败: {item}")
    return candidate


def validate(case: dict[str, Any], patch: dict[str, Any]) -> list[str]:
    """Return human-readable validation errors; an empty list means valid."""
    errors: list[str] = []
    if not isinstance(case, dict):
        return ["案件 JSON 顶层必须是对象"]
    if not isinstance(patch, dict):
        return ["Patch 顶层必须是对象"]

    required = [
        "patch_id",
        "case_id",
        "base_revision",
        "view",
        "transaction",
        "operation",
        "actor",
        "reason",
        "operations",
        "expected_affected_entities",
    ]
    for key in required:
        if key not in patch:
            errors.append(f"Patch 缺少字段 {key}")
    for key in ("patch_id", "case_id", "view", "operation", "actor", "reason"):
        if key in patch and (not isinstance(patch[key], str) or not patch[key].strip()):
            errors.append(f"Patch 字段 {key} 必须是非空字符串")

    transaction = patch.get("transaction")
    if not isinstance(transaction, str) or not transaction.strip():
        errors.append("Patch 字段 transaction 必须是非空字符串")
    elif transaction not in TRANSACTIONS:
        errors.append(f"不支持的 Patch transaction: {transaction}")
    elif transaction == "reimport_material" and patch.get("view") != "import":
        errors.append("reimport_material 的业务 Patch 只能使用 view=import")
    elif transaction != "reimport_material" and transaction != "case_json_only":
        errors.append("export_from_json 和 bootstrap_import 不得用于已有案件的 Patch 写回")
    elif transaction == "case_json_only" and patch.get("view") == "import":
        errors.append("case_json_only 不得使用 import 视图读取或写入外部材料")

    case_id = case.get("case", {}).get("case_id") if isinstance(case.get("case"), dict) else None
    if patch.get("case_id") != case_id:
        errors.append("Patch case_id 与案件不一致")
    control = case.get("control") if isinstance(case.get("control"), dict) else {}
    current = control.get("current_revision")
    if not _is_int(current) or current < 0:
        errors.append("案件 /control/current_revision 必须是非负整数")
    if not _is_int(patch.get("base_revision")):
        errors.append("Patch base_revision 必须是非负整数")
    elif isinstance(current, int) and patch["base_revision"] != current:
        errors.append(f"base_revision={patch['base_revision']} 不等于 current_revision={current}")

    view = patch.get("view")
    if view not in ALLOWED_VIEWS:
        errors.append(f"不支持的 Patch view: {view}")

    operations = patch.get("operations")
    if not isinstance(operations, list) or not operations:
        errors.append("operations 必须是非空数组")
        operations = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            errors.append(f"operations[{index}] 必须是对象")
            continue
        op = operation.get("op")
        path = operation.get("path")
        if op not in {"add", "replace", "remove", "test"}:
            errors.append(f"operations[{index}] 不支持 op={op}")
        pointer_issue = _pointer_error(path)
        if pointer_issue:
            errors.append(f"operations[{index}].path {pointer_issue}: {path}")
            continue
        if not path_owned_by_view(path, view):
            errors.append(f"operations[{index}] 越权路径: {path} 不属于 view={view}")
        tokens = pointer_tokens(path)
        protected_control = {"current_revision", "route_confirmation", "active_route", "transactions", "change_log", "conflicts", "dependency_index", "reverse_dependency_index", "object_index"}
        if tokens and tokens[0] == "control" and (len(tokens) == 1 or tokens[1] in protected_control):
            errors.append(f"operations[{index}] 受保护的总控治理路径不得由 Patch 直接写入: {path}")
        numeric = [token for token in tokens if token.isdigit()]
        if numeric:
            errors.append(f"operations[{index}] 使用数组下标定位对象；请使用稳定 ID 对象或数组追加 /-: {path}")
        if tokens and tokens[-1] == "-" and op != "add":
            errors.append(f"operations[{index}] 只有 add 可以使用数组追加 /-: {path}")
        if op in {"add", "replace", "test"} and "value" not in operation:
            errors.append(f"operations[{index}] 缺少 value")
        if op == "remove" and tokens and tokens[-1] in {"id", "claim_id", "chain_id", "document_id", "issue_id"}:
            errors.append(f"operations[{index}] 不得移除实体稳定 ID: {path}")

    _validate_route_binding(case, patch, errors)
    _validate_reimport_scope(case, patch, errors)
    _candidate_errors(case, patch, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验统一案件工作流的版本化视图 Patch")
    parser.add_argument("--case", required=True)
    parser.add_argument("--patch", required=True)
    args = parser.parse_args()
    try:
        errors = validate(load_json(Path(args.case)), load_json(Path(args.patch)))
    except Exception as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
