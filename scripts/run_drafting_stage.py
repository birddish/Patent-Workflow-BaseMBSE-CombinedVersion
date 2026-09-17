#!/usr/bin/env python3
"""Run one drafting-stage delivery transaction from a single case.json.

The orchestrator is JSON-only. It requires an explicitly confirmed user mode,
checks a stored AI recommendation when present, generates visible Markdown
deliverables, registers them in control.deliverables, and atomically writes
the control metadata back to case.json.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from export_drafting_deliverable import STAGES, atomic_write, render


def get_path(document: dict[str, Any], path: str) -> Any:
    value: Any = document
    for part in path.split("/"):
        if not part:
            continue
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def set_path(document: dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in path.split("/") if part]
    cursor: dict[str, Any] = document
    for part in parts[:-1]:
        existing = cursor.get(part)
        if not isinstance(existing, dict):
            existing = {}
            cursor[part] = existing
        cursor = existing
    cursor[parts[-1]] = value


def atomic_json_write(path: Path, document: dict[str, Any]) -> None:
    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def next_deliverable_id(items: list[Any]) -> str:
    numbers: list[int] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get("deliverable_id")
        if isinstance(value, str) and value.startswith("DELIV-") and value[6:].isdigit():
            numbers.append(int(value[6:]))
    return f"DELIV-{(max(numbers, default=0) + 1):03d}"


def resolve_mode(document: dict[str, Any]) -> tuple[Any, Any]:
    navigation = get_path(document, "control/navigation") or {}
    transaction = get_path(document, "control/transaction") or {}
    ai_assessment = get_path(document, "control/ai_assessment") or {}
    if not isinstance(navigation, dict):
        navigation = {}
    if not isinstance(transaction, dict):
        transaction = {}
    if not isinstance(ai_assessment, dict):
        ai_assessment = {}
    selected = navigation.get("selected_writing_mode", transaction.get("writing_mode"))
    recommended = navigation.get("recommended_writing_mode", ai_assessment.get("recommended_writing_mode"))
    return selected, recommended


def require_explicit_mode(document: dict[str, Any], supplied_mode: str | None) -> tuple[str, str | None]:
    selected, recommended = resolve_mode(document)
    effective = supplied_mode or selected
    if not isinstance(effective, str) or not effective.strip():
        raise SystemExit(json.dumps({
            "status": "blocked",
            "reason": "explicit_writing_mode_required",
            "message": "必须先由用户明文确认撰写模式。",
        }, ensure_ascii=False))
    if isinstance(recommended, str) and recommended.strip() and effective != recommended:
        raise SystemExit(json.dumps({
            "status": "blocked",
            "reason": "user_mode_differs_from_ai_assessment",
            "selected_mode": effective,
            "recommended_mode": recommended,
            "message": "用户选择的撰写模式与案件 JSON 中的 AI 判断不一致，必须先向用户提出质疑并获得确认。",
        }, ensure_ascii=False))
    return effective, recommended if isinstance(recommended, str) else None


def mark_previous_stage_items_stale(items: list[Any], stage_id: str, revision: Any) -> None:
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("view") == "drafting" and item.get("stage") == stage_id:
            if item.get("source_revision") != revision and item.get("status") not in {"superseded", "stale"}:
                item["status"] = "superseded"


def main() -> int:
    parser = argparse.ArgumentParser(description="自动执行一个撰写阶段的 JSON-only 交付事务")
    parser.add_argument("--case-json", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=sorted(STAGES))
    parser.add_argument("--writing-mode", help="用户明文确认的撰写模式")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()

    case_path = args.case_json.resolve()
    if not case_path.is_file():
        raise SystemExit(f"找不到案件主 JSON：{case_path}")
    with case_path.open("r", encoding="utf-8") as handle:
        document: dict[str, Any] = json.load(handle)

    mode, recommended = require_explicit_mode(document, args.writing_mode)
    control = document.setdefault("control", {})
    if not isinstance(control, dict):
        raise SystemExit("case.json 的 control 必须是对象")
    revision = control.get("current_revision", control.get("revision", 0))
    stage = STAGES[args.stage]
    output_root = (args.output_root or case_path.parent / "deliverables").resolve()
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    stage_status = control.setdefault("stage_status", {})
    if not isinstance(stage_status, dict):
        raise SystemExit("case.json 的 control.stage_status 必须是对象")
    stage_status[args.stage] = {
        "view": "drafting",
        "writing_mode": mode,
        "status": "generating",
        "source_revision": revision,
        "updated_at": generated_at,
    }

    deliverables = control.setdefault("deliverables", [])
    if not isinstance(deliverables, list):
        raise SystemExit("case.json 的 control.deliverables 必须是数组")
    mark_previous_stage_items_stale(deliverables, args.stage, revision)

    generated: list[dict[str, Any]] = []
    for filename in stage["files"]:
        target = output_root / stage["directory"] / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        content = render(args.stage, stage, case_path, document)
        atomic_write(target, content)
        generated.append({
            "deliverable_id": next_deliverable_id(deliverables),
            "stage": args.stage,
            "view": "drafting",
            "type": filename.rsplit(".", 1)[0],
            "path": str(target.relative_to(case_path.parent)),
            "source_revision": revision,
            "source_object_paths": stage["paths"],
            "status": "generated",
            "human_review": "pending",
            "content_scope": "current_stage_only",
            "generated_at": generated_at,
        })
        deliverables.append(generated[-1])

    stage_status[args.stage] = {
        "view": "drafting",
        "writing_mode": mode,
        "ai_recommended_mode": recommended,
        "status": "review_pending",
        "source_revision": revision,
        "updated_at": generated_at,
        "deliverable_ids": [item["deliverable_id"] for item in generated],
    }
    control["last_drafting_delivery"] = {
        "stage": args.stage,
        "writing_mode": mode,
        "source_revision": revision,
        "generated_at": generated_at,
        "deliverable_ids": [item["deliverable_id"] for item in generated],
    }
    control["deliverables_revision"] = int(control.get("deliverables_revision", 0)) + 1
    atomic_json_write(case_path, document)

    print(json.dumps({
        "status": "review_pending",
        "case_json": str(case_path),
        "source_revision": revision,
        "stage": args.stage,
        "writing_mode": mode,
        "deliverables": generated,
        "next_action": "请查看阶段文件并明确确认、修改或阻断。",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
