"""Build and submit an explicit reimport Patch through the unified commit CLI."""
from __future__ import annotations
import argparse, copy, json, subprocess, sys, tempfile, uuid
from pathlib import Path
from typing import Any
from _case_utils import now_iso
from import_case_materials import read_material
from validate_view_patch import _record_ids

def _load_snapshot(case_path: Path) -> tuple[bytes, dict[str, Any]]:
    original_bytes = case_path.read_bytes()
    case = json.loads(original_bytes.decode("utf-8"))
    if not isinstance(case, dict): raise ValueError("案件 JSON 顶层必须是对象")
    return original_bytes, case

def _valid_confirmation(case: dict[str, Any], *, confirmation_id: str, transaction: str,
                        files: list[str], strategy: str, old_batch_policy: str
                        ) -> tuple[bool, str, list[str]]:
    control = case.get("control") if isinstance(case.get("control"), dict) else {}
    current_revision = control.get("current_revision")
    case_id = case.get("case", {}).get("case_id") if isinstance(case.get("case"), dict) else None
    confirmation = control.get("route_confirmation")
    if not isinstance(confirmation, dict): return False, "缺少当前 route_confirmation；不能使用历史事务记录替代当前明文确认", []
    if confirmation.get("status") != "confirmed": return False, "当前 route_confirmation 不是 confirmed 状态", []
    if confirmation.get("confirmation_id") != confirmation_id: return False, "confirmation_id 与当前 route_confirmation 不一致", []
    if confirmation.get("case_id") != case_id: return False, "当前 route_confirmation.case_id 与案件不一致", []
    if confirmation.get("confirmed_revision") != current_revision: return False, "当前 route_confirmation.confirmed_revision 已不是当前 revision", []
    if confirmation.get("base_revision") != current_revision: return False, "当前 route_confirmation.base_revision 必须等于当前 revision", []
    route = confirmation.get("selected_route")
    if not isinstance(route, dict) or route.get("transaction") != transaction: return False, "当前 route_confirmation.selected_route.transaction 不是 reimport_material", []
    warnings: list[str] = []
    import_scope = confirmation.get("import_scope")
    if not isinstance(import_scope, dict):
        return False, "当前 route_confirmation 缺少 import_scope；必须重新明文确认文件清单及策略", []
    else:
        confirmed_files = import_scope.get("files")
        if not isinstance(confirmed_files, list) or not confirmed_files:
            return False, "当前 route_confirmation.import_scope.files 缺失或为空", warnings
        if sorted(map(str, confirmed_files)) != sorted(map(str, files)):
            return False, "实际文件清单与当前 route_confirmation.import_scope.files 不一致", warnings
        if import_scope.get("strategy") != strategy:
            return False, "实际 strategy 与当前 route_confirmation.import_scope.strategy 不一致", warnings
        if import_scope.get("old_batch_policy") != old_batch_policy:
            return False, "实际 old_batch_policy 与当前 route_confirmation.import_scope.old_batch_policy 不一致", warnings
    return True, "confirmed", warnings

def _active_batch_ids(case: dict[str, Any]) -> list[str]:
    batches = case.get("source_materials", {}).get("import_batches", [])
    if not isinstance(batches, list): return []
    superseded = {old_id for batch in batches if isinstance(batch, dict) for old_id in batch.get("supersedes_batch_ids", []) if isinstance(old_id, str)}
    return [x["batch_id"] for x in batches if isinstance(x, dict) and x.get("status") == "committed" and isinstance(x.get("batch_id"), str) and x["batch_id"] not in superseded]

def build_reimport_patch(*, case: dict[str, Any], materials: list[dict[str, Any]],
                         confirmation_id: str, strategy: str, old_batch_policy: str,
                         actor: str, compatibility_warnings: list[str]) -> dict[str, Any]:
    source = case.get("source_materials") if isinstance(case.get("source_materials"), dict) else {}
    batches = source.get("import_batches", []) if isinstance(source, dict) else []
    batch_id = f"BATCH-{(len(batches) if isinstance(batches, list) else 0) + 1:04d}"
    document_ids = [x["document_id"] for x in materials]
    normalized_ids = [f"NORM-{x}" for x in document_ids]
    active_ids = _active_batch_ids(case)
    batch: dict[str, Any] = {
        "batch_id": batch_id, "transaction_id": f"TX-REIMPORT-{uuid.uuid4().hex[:10].upper()}",
        "kind": "reimport_material", "strategy": strategy, "old_batch_policy": old_batch_policy,
        "actor": actor, "source_files": [str(x.get("source_path", x.get("name", ""))) for x in materials],
        "document_ids": document_ids, "imported_at": now_iso(), "status": "committed",
    }
    if strategy == "replace": batch["supersedes_batch_ids"] = active_ids
    elif strategy == "parallel": batch["parallel_to_batch_ids"] = active_ids
    else: batch["appends_to_batch_ids"] = active_ids
    operations: list[dict[str, Any]] = [{"op": "add", "path": "/source_materials/import_batches/-", "value": batch}]
    for item in materials:
        material = copy.deepcopy(item)
        raw_ref, raw_base64 = material.pop("raw_artifact_ref", None), material.pop("raw_artifact_base64", None)
        operations.append({"op": "add", "path": "/source_materials/documents/-", "value": material})
        if raw_ref and raw_base64:
            operations.append({"op": "add", "path": "/source_materials/raw_artifacts/-", "value": {"artifact_id": raw_ref, "document_id": item["document_id"], "base64": raw_base64, "media_type": item["media_type"]}})
        if item.get("extraction_status") != "extracted" or any(isinstance(f, dict) and f.get("ocr_status") == "pending" for f in item.get("figures", [])):
            operations.append({"op": "add", "path": "/control/open_gates/-", "value": {"id": f"GATE-EXTRACT-{item['document_id']}", "status": "blocked", "document_id": item["document_id"], "reason": "重新导入已保存快照，但可计算的文本、图形或 OCR 结构尚不完整", "next_action": "明确补充结构化导入；JSON-only 阶段不得回读原始文件"}})
        operations.append({"op": "add", "path": "/normalized/documents/-", "value": {"id": f"NORM-{item['document_id']}", "title": item["name"], "source_refs": [item["document_id"]], "evidence_state": "pending_review", "confirmation_state": "unconfirmed", "extraction_status": item["extraction_status"]}})
    return {
        "patch_id": f"PATCH-REIMPORT-{uuid.uuid4().hex[:10].upper()}", "case_id": case["case"]["case_id"],
        "base_revision": case["control"]["current_revision"], "transaction": "reimport_material", "view": "import",
        "operation": "reimport_material", "actor": actor, "reason": f"用户明文确认重新导入，策略={strategy}，旧批次快照=retain",
        "confirmation_id": confirmation_id, "strategy": strategy, "old_batch_policy": old_batch_policy,
        "import_batch_id": batch_id, "source_document_ids": document_ids, "normalized_document_ids": normalized_ids,
        "compatibility_warnings": compatibility_warnings, "expected_affected_entities": sorted({batch_id, *document_ids, *normalized_ids}.union(*(_record_ids(op["value"]) for op in operations))),
        "operations": operations,
    }

def _write_temp_patch(patch: dict[str, Any]) -> Path:
    handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".patch.json", delete=False)
    try:
        json.dump(patch, handle, ensure_ascii=False, indent=2); handle.write("\n"); return Path(handle.name)
    finally: handle.close()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True); parser.add_argument("--transaction", choices=["reimport_material"], required=True)
    parser.add_argument("--confirmation-id", required=True); parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument("--strategy", choices=["append", "parallel", "replace"], required=True)
    parser.add_argument("--old-batch-policy", choices=["retain"], required=True)
    parser.add_argument("--materials-listed", action="store_true", required=True); parser.add_argument("--writeback-confirmed", action="store_true", required=True)
    parser.add_argument("--actor", default="user"); args = parser.parse_args()
    case_path = Path(args.case)
    try:
        _original_bytes, case = _load_snapshot(case_path)
        files = [str(Path(x).resolve()) for x in args.files]
        valid, reason, warnings = _valid_confirmation(case, confirmation_id=args.confirmation_id, transaction=args.transaction, files=files, strategy=args.strategy, old_batch_policy=args.old_batch_policy)
        if not valid:
            print(json.dumps({"committed": False, "status": "blocked", "errors": [reason]}, ensure_ascii=False, indent=2)); return 1
        patch = build_reimport_patch(case=case, materials=[read_material(Path(x)) for x in args.files], confirmation_id=args.confirmation_id, strategy=args.strategy, old_batch_policy=args.old_batch_policy, actor=args.actor, compatibility_warnings=warnings)
        patch_path = _write_temp_patch(patch)
        try:
            commit_script = Path(__file__).with_name("commit_case_patch.py")
            result = subprocess.run([sys.executable, str(commit_script), "--case", str(case_path), "--patch", str(patch_path)], cwd=str(commit_script.parent), text=True, encoding="utf-8", capture_output=True, check=False)
            try: payload = json.loads(result.stdout)
            except json.JSONDecodeError: payload = {"committed": False, "status": "blocked", "errors": [result.stdout or result.stderr]}
            payload.update({"transaction": "reimport_material", "patch_id": patch["patch_id"], "expected_affected_entities": patch["expected_affected_entities"]})
            if warnings: payload["compatibility_warnings"] = warnings
            print(json.dumps(payload, ensure_ascii=False, indent=2)); return result.returncode
        finally:
            try: patch_path.unlink()
            except OSError: pass
    except Exception as exc:
        print(json.dumps({"committed": False, "status": "blocked", "errors": [str(exc)]}, ensure_ascii=False, indent=2)); return 1

if __name__ == "__main__":
    raise SystemExit(main())
