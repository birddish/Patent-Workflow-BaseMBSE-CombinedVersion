"""Commit a validated Patch with conflict recording and recoverable atomic writes.

The public command remains compatible with the former --case --patch
[--dry-run] interface. All business changes are applied to a deep copy,
validated, serialized to a same-directory temporary file, and replaced only
after a compare-and-swap check. A timestamped/transactioned backup is made
before replacement; any failure leaves the original case JSON untouched.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from _case_utils import iter_entity_records, load_json, now_iso, pointer_get, pointer_parent, stable_record_id
from calculate_impact_set import calculate as calculate_impact
from validate_case_json import validate as validate_case
from validate_view_patch import validate as validate_patch
from validate_view_patch import _ids_in_path, _record_ids


class ConcurrentModificationError(RuntimeError):
    """The case changed after it was read and before the replacement."""


TERMINAL_STATUSES = {"deleted", "superseded", "invalidated"}


def _patch_change_inputs(case: dict[str, Any], patch: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Resolve changed paths and stable IDs from the original case and Patch."""
    changed_paths: list[str] = []
    changed_ids: set[str] = set()
    for operation in patch.get("operations", []):
        if not isinstance(operation, dict) or not isinstance(operation.get("path"), str):
            continue
        path = operation["path"]
        changed_paths.append(path)
        changed_ids.update(_ids_in_path(case, path))
        if operation.get("op") in {"add", "replace", "test"}:
            changed_ids.update(_record_ids(operation.get("value")))
    if patch.get("transaction") == "reimport_material" and patch.get("strategy") == "replace":
        batches = case.get("source_materials", {}).get("import_batches", [])
        superseded = set()
        for operation in patch.get("operations", []):
            if isinstance(operation, dict) and operation.get("path") == "/source_materials/import_batches/-":
                value = operation.get("value")
                if isinstance(value, dict):
                    superseded.update(value.get("supersedes_batch_ids", []))
        if isinstance(batches, list):
            for old in batches:
                if isinstance(old, dict) and old.get("batch_id") in superseded:
                    changed_ids.add(old["batch_id"])
                    changed_ids.update(x for x in old.get("document_ids", []) if isinstance(x, str))
    return sorted(set(changed_paths)), sorted(changed_ids)


def _find_derived_entity(case: dict[str, Any], entity_id: str) -> dict[str, Any] | None:
    """Find a derived entity by stable ID without relying on array positions."""
    for record, _path in iter_entity_records(case.get("derived", {}), "/derived"):
        if stable_record_id(record) == entity_id:
            return record
    return None


def _apply_impact_statuses(
    candidate: dict[str, Any],
    impact: dict[str, Any],
) -> list[dict[str, str]]:
    """Apply controlled stale/invalid transitions to the original dependency closure."""
    updates: list[dict[str, str]] = []
    for recommendation in impact.get("status_recommendations", []):
        if not isinstance(recommendation, dict):
            continue
        entity_id = recommendation.get("id")
        target_status = recommendation.get("recommended_status")
        if not isinstance(entity_id, str) or target_status not in {"stale", "invalid"}:
            continue
        record = _find_derived_entity(candidate, entity_id)
        if record is None:
            # Newly added entities are not in the original dependency closure;
            # their own status is owned by the Patch that created them.
            continue
        current_status = record.get("status")
        if current_status in TERMINAL_STATUSES:
            # A logical-delete Patch owns the direct terminal transition, and
            # an existing terminal record must never be revived or rewritten.
            continue
        if current_status != target_status:
            record["status"] = target_status
            updates.append(
                {
                    "id": entity_id,
                    "from": str(current_status),
                    "to": target_status,
                }
            )

    # A non-terminal impacted derived entity may not remain fresh after the
    # commit. This checks the exact original dependency closure, not the
    # Patch caller's declared affected list.
    fresh_remaining: list[str] = []
    for entity_id in impact.get("affected_derived_ids", []):
        if not isinstance(entity_id, str):
            continue
        record = _find_derived_entity(candidate, entity_id)
        if record is not None and record.get("status") == "fresh":
            fresh_remaining.append(entity_id)
    if fresh_remaining:
        raise ValueError(
            "依赖闭包失效传播未完成，受影响派生对象仍为 fresh: "
            + ", ".join(sorted(fresh_remaining))
        )
    return updates


def apply_one(doc: dict[str, Any], operation: dict[str, Any]) -> None:
    """Apply one already-validated JSON Patch operation in memory."""
    op, path = operation["op"], operation["path"]
    if op == "test":
        if pointer_get(doc, path) != operation.get("value"):
            raise ValueError(f"test 失败: {path}")
        return

    parent, token = pointer_parent(doc, path)
    if isinstance(parent, list):
        if token != "-":
            raise ValueError(f"禁止使用数组下标写回: {path}")
        if op != "add":
            raise ValueError(f"数组对象只能通过 /- 追加，不能 {op}: {path}")
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


def _serialize(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _backup_path(case_path: Path, revision: int, transaction_id: str) -> Path:
    return case_path.with_name(f"{case_path.name}.backup.r{revision}.{transaction_id}.json")


def _atomic_replace_with_backup(
    case_path: Path,
    value: dict[str, Any],
    *,
    expected_bytes: bytes,
    revision: int,
    transaction_id: str,
) -> Path:
    """Write same-directory temp, CAS-check, backup, then atomically replace."""
    parent = case_path.parent
    parent.mkdir(parents=True, exist_ok=True)

    # Check before making a backup. This avoids claiming a backup for a write
    # that was never authorized against the bytes that were read.
    current_bytes = case_path.read_bytes()
    if current_bytes != expected_bytes:
        raise ConcurrentModificationError("案件 JSON 在提交前已发生变化，拒绝覆盖")

    backup = _backup_path(case_path, revision, transaction_id)
    temp_name: str | None = None
    try:
        # copy2 preserves the recoverable pre-commit snapshot. If it fails,
        # no replacement is attempted.
        shutil.copy2(case_path, backup)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{case_path.name}.",
            suffix=".tmp",
            dir=str(parent),
        )
        with os.fdopen(fd, "wb") as handle:
            handle.write(_serialize(value))
            handle.flush()
            os.fsync(handle.fileno())

        # Re-check immediately before os.replace. This is a compare-and-swap
        # guard against a second writer; no last-write-wins behavior.
        if case_path.read_bytes() != expected_bytes:
            raise ConcurrentModificationError("案件 JSON 在临时文件写入期间已发生变化，拒绝覆盖")
        os.replace(temp_name, case_path)
        temp_name = None
        return backup
    except Exception:
        if temp_name:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
        raise


def record_conflict(case: dict[str, Any], patch: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    """Append a visible conflict result without applying any Patch operation."""
    control = case.setdefault("control", {})
    if not isinstance(control, dict):
        raise ValueError("/control 必须是对象，无法记录冲突")
    current_revision = control.get("current_revision", 0)
    conflict_id = f"CONFLICT-{uuid.uuid4().hex[:10].upper()}"
    transaction_id = f"TX-CONFLICT-{uuid.uuid4().hex[:10].upper()}"
    created_at = now_iso()
    conflict = {
        "conflict_id": conflict_id,
        "patch_id": patch.get("patch_id"),
        "case_id": patch.get("case_id"),
        "base_revision": patch.get("base_revision"),
        "current_revision": current_revision,
        "paths": [
            item.get("path")
            for item in patch.get("operations", [])
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        ],
        "errors": list(errors),
        "status": "open",
        "suggestion": "重新读取 L0/L1 和当前 revision，重新计算影响集并生成新的 Patch；不得静默覆盖。",
        "result": {
            "status": "rejected",
            "business_changes_applied": False,
            "requires_reconfirmation": True,
        },
        "created_at": created_at,
    }
    control.setdefault("conflicts", []).append(conflict)
    control.setdefault("transactions", []).append(
        {
            "transaction_id": transaction_id,
            "kind": patch.get("transaction"),
            "status": "conflict",
            "base_revision": patch.get("base_revision"),
            "result_revision": current_revision,
            "patch_id": patch.get("patch_id"),
            "actor": patch.get("actor"),
            "started_at": created_at,
            "finished_at": now_iso(),
            "conflict_id": conflict_id,
        }
    )
    return conflict


def _record_conflict_safely(
    case_path: Path,
    patch: dict[str, Any],
    errors: list[str],
) -> tuple[dict[str, Any] | None, Path | None, str | None]:
    """Record a conflict with CAS; retry against a newer case at most twice."""
    last_error: str | None = None
    for _ in range(2):
        try:
            expected = case_path.read_bytes()
            latest = json.loads(expected.decode("utf-8"))
            if not isinstance(latest, dict):
                raise ValueError("案件 JSON 顶层必须是对象")
            conflict = record_conflict(latest, patch, errors)
            transaction_id = latest["control"]["transactions"][-1]["transaction_id"]
            revision = latest["control"].get("current_revision", 0)
            backup = _atomic_replace_with_backup(
                case_path,
                latest,
                expected_bytes=expected,
                revision=revision,
                transaction_id=transaction_id,
            )
            return conflict, backup, None
        except ConcurrentModificationError as exc:
            last_error = str(exc)
            continue
        except Exception as exc:
            last_error = str(exc)
            break
    return None, None, last_error


def _json_error_result(status: str, errors: list[str], **extra: Any) -> None:
    payload: dict[str, Any] = {
        "committed": False,
        "status": status,
        "business_changes_applied": False,
        "errors": errors,
    }
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="校验并原子提交统一案件工作流 Patch")
    parser.add_argument("--case", required=True)
    parser.add_argument("--patch", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    case_path = Path(args.case)
    try:
        original_bytes = case_path.read_bytes()
        case = load_json(case_path)
        patch = load_json(Path(args.patch))
    except Exception as exc:
        _json_error_result("blocked", [f"无法读取案件或 Patch: {exc}"], original_preserved=True)
        return 2

    errors = validate_patch(case, patch)
    # Keep the commit boundary defensive even if a future validator caller
    # changes its accepted transaction vocabulary.
    if not (patch.get("transaction") == "case_json_only" and patch.get("view") != "import" or patch.get("transaction") == "reimport_material" and patch.get("view") == "import"):
        errors.append("提交器只接受 case_json_only 的业务/总控 Patch 或 reimport_material 的 import Patch；导出永远只读")
        _json_error_result("blocked", errors, original_preserved=True)
        return 1
    current = case.get("control", {}).get("current_revision") if isinstance(case.get("control"), dict) else None
    base = patch.get("base_revision")
    revision_conflict = (
        isinstance(current, int)
        and not isinstance(current, bool)
        and isinstance(base, int)
        and not isinstance(base, bool)
        and base != current
    )
    if revision_conflict:
        conflict, backup, conflict_error = _record_conflict_safely(case_path, patch, errors)
        payload: dict[str, Any] = {
            "committed": False,
            "status": "conflict",
            "business_changes_applied": False,
            "errors": errors,
            "original_preserved": True,
            "conflict_recorded": conflict is not None,
        }
        if conflict is not None:
            payload["conflict_id"] = conflict["conflict_id"]
        if backup is not None:
            payload["backup_path"] = str(backup)
        if conflict_error:
            payload["conflict_record_error"] = conflict_error
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    if errors:
        _json_error_result("blocked", errors, original_preserved=True)
        return 1

    candidate = copy.deepcopy(case)
    try:
        for operation in patch["operations"]:
            apply_one(candidate, operation)
    except Exception as exc:
        _json_error_result("blocked", [f"Patch 操作无法应用: {exc}"], original_preserved=True)
        return 1

    changed_paths, changed_ids = _patch_change_inputs(case, patch)
    change_kind = "remove" if patch.get("operation") in {"logical_delete", "remove", "delete"} else "replace"
    try:
        impact = calculate_impact(
            case,
            changed_ids=changed_ids,
            changed_paths=changed_paths,
            change_kind=change_kind,
        )
        status_updates = _apply_impact_statuses(candidate, impact)
    except Exception as exc:
        _json_error_result(
            "blocked",
            [f"依赖闭包失效传播失败，Patch 未写回: {exc}"],
            original_preserved=True,
        )
        return 1

    # The validator already checked the candidate; this second call protects
    # the commit path if a caller mutates the in-memory candidate in the future.
    structural_errors = validate_case(candidate)
    if structural_errors:
        _json_error_result(
            "blocked",
            [f"候选案件 Schema/引用校验失败: {item}" for item in structural_errors],
            original_preserved=True,
        )
        return 1

    control = candidate.setdefault("control", {})
    old_revision = control.get("current_revision")
    if not isinstance(old_revision, int) or isinstance(old_revision, bool) or old_revision < 0:
        _json_error_result("blocked", ["案件 current_revision 无效"], original_preserved=True)
        return 1
    new_revision = old_revision + 1
    transaction_id = f"TX-{uuid.uuid4().hex[:12].upper()}"
    started_at = now_iso()
    backup = _backup_path(case_path, old_revision, transaction_id)

    consumed_confirmation = control.get("route_confirmation")
    if (isinstance(consumed_confirmation, dict) and consumed_confirmation.get("status") == "confirmed"
            and consumed_confirmation.get("confirmed_revision") == old_revision):
        # A confirmation is single-use. Advancing the case revision expires it
        # so the next write must pass through a fresh explicit user confirmation.
        consumed_confirmation["status"] = "expired"
        consumed_confirmation["expired_at"] = now_iso()
        consumed_confirmation["expired_reason"] = "Patch committed and current_revision advanced"
        consumed_confirmation["superseded_by_revision"] = new_revision
    control["current_revision"] = new_revision
    control.setdefault("change_log", []).append(
        {
            "transaction_id": transaction_id,
            "patch_id": patch["patch_id"],
            "revision": new_revision,
            "view": patch["view"],
            "operation": patch["operation"],
            "actor": patch["actor"],
            "reason": patch["reason"],
            "affected_entities": impact.get("impacted_ids", []),
            "declared_affected_entities": patch.get("expected_affected_entities", []),
            "impact_set": {
                "change_kind": impact.get("change_kind"),
                "changed_ids": impact.get("changed_ids", []),
                "changed_paths": impact.get("changed_paths", []),
                "impacted_ids": impact.get("impacted_ids", []),
                "affected_derived_ids": impact.get("affected_derived_ids", []),
                "status_updates": status_updates,
            },
            "timestamp": now_iso(),
        }
    )
    control.setdefault("transactions", []).append(
        {
            "transaction_id": transaction_id,
            "kind": patch.get("transaction"),
            "status": "preview" if args.dry_run else "committed",
            "base_revision": old_revision,
            "result_revision": new_revision,
            "actor": patch["actor"],
            "patch_id": patch["patch_id"],
            "started_at": started_at,
            "finished_at": now_iso(),
            "backup_path": str(backup),
            "affected_entities": impact.get("impacted_ids", []),
            "status_updates": status_updates,
        }
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "committed": False,
                    "status": "preview",
                    "business_changes_applied": False,
                    "base_revision": old_revision,
                    "result_revision": new_revision,
                    "transaction_id": transaction_id,
                    "backup_path": None,
                    "original_preserved": True,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    try:
        actual_backup = _atomic_replace_with_backup(
            case_path,
            candidate,
            expected_bytes=original_bytes,
            revision=old_revision,
            transaction_id=transaction_id,
        )
    except ConcurrentModificationError as exc:
        conflict_errors = [str(exc), "Patch 未应用；请重新读取当前 revision 后重试。"]
        conflict, conflict_backup, conflict_error = _record_conflict_safely(case_path, patch, conflict_errors)
        payload = {
            "committed": False,
            "status": "conflict",
            "business_changes_applied": False,
            "errors": conflict_errors,
            "original_preserved": True,
            "conflict_recorded": conflict is not None,
        }
        if conflict is not None:
            payload["conflict_id"] = conflict["conflict_id"]
        if conflict_backup is not None:
            payload["backup_path"] = str(conflict_backup)
        if conflict_error:
            payload["conflict_record_error"] = conflict_error
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    except Exception as exc:
        _json_error_result(
            "blocked",
            [f"原子写回失败: {exc}"],
            original_preserved=True,
            backup_path=str(backup) if backup.exists() else None,
        )
        return 1

    print(
        json.dumps(
            {
                "committed": True,
                "status": "committed",
                "business_changes_applied": True,
                "base_revision": old_revision,
                "result_revision": new_revision,
                "transaction_id": transaction_id,
                "backup_path": str(actual_backup),
                "original_preserved": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
