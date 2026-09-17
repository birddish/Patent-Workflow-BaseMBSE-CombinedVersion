#!/usr/bin/env python3
"""Generate human-readable drafting deliverables from one case.json.

This script is JSON-only: it reads the case JSON and never reads source DOCX,
PDF, image, or other external case materials.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STAGES: dict[str, dict[str, Any]] = {
    "00-intake": {
        "directory": "00-intake",
        "title": "导入和撰写模式确认",
        "paths": ["source_materials", "normalized", "control/transaction", "control/navigation"],
        "files": ["intake-summary.md", "selected-writing-mode.md", "pending-questions.md"],
    },
    "01-technical-facts": {
        "directory": "01-technical-facts",
        "title": "技术事实整理",
        "paths": ["normalized/technical_facts", "normalized/terminology", "normalized/constraints"],
        "files": ["technical-facts.md", "confirmed-facts.md", "pending-facts.md", "terminology-table.md"],
    },
    "02-mbse-model": {
        "directory": "02-mbse-model",
        "title": "MBSE 模型和保护链",
        "paths": ["derived/mbse"],
        "files": ["mbse-model-summary.md", "protection-chain.md", "evidence-chain.md", "protection-candidates.md"],
    },
    "03-claim-core": {
        "directory": "03-claim-core",
        "title": "权利要求核心",
        "paths": [
            "derived/drafting/claims",
            "derived/drafting/claim_versions",
            "derived/drafting/protection_units",
            "derived/drafting/support_links",
            "derived/drafting/claim_paths",
        ],
        "files": [
            "claim-core-draft.md",
            "independent-claim-candidates.md",
            "necessary-features.md",
            "claim-source-traceability.md",
            "claim-core-review.md",
        ],
    },
    "04-claim-branches": {
        "directory": "04-claim-branches",
        "title": "从属项和回退路径",
        "paths": [
            "derived/drafting/dependent_claim_branches",
            "derived/drafting/fallback_routes",
            "derived/drafting/claim_paths",
        ],
        "files": [
            "claim-tree.md",
            "dependent-claim-candidates.md",
            "fallback-routes.md",
            "branch-support-matrix.md",
        ],
    },
    "05-specification-outline": {
        "directory": "05-specification-outline",
        "title": "说明书提纲",
        "paths": ["derived/drafting/specification_outline", "derived/drafting/claim_support_map"],
        "files": [
            "specification-outline.md",
            "claim-support-matrix.md",
            "embodiment-plan.md",
            "section-missing-items.md",
        ],
    },
    "06-specification-draft": {
        "directory": "06-specification-draft",
        "title": "说明书正文",
        "paths": [
            "derived/drafting/specification_sections",
            "derived/drafting/embodiments",
            "derived/drafting/terminology",
        ],
        "files": [
            "specification-draft.md",
            "embodiments.md",
            "terminology-list.md",
            "claim-to-specification-trace.md",
        ],
    },
    "07-figures-and-consistency": {
        "directory": "07-figures-and-consistency",
        "title": "附图、标号和一致性",
        "paths": [
            "derived/drafting/figures",
            "derived/drafting/reference_numbers",
            "derived/drafting/terminology_consistency",
        ],
        "files": [
            "figures-description.md",
            "reference-number-table.md",
            "figure-text-map.md",
            "terminology-consistency.md",
        ],
    },
    "08-drafting-audit": {
        "directory": "08-drafting-audit",
        "title": "撰写审计",
        "paths": ["derived/drafting/claim_text_audits", "derived/audit"],
        "files": [
            "claim-text-audit.md",
            "support-audit.md",
            "terminology-audit.md",
            "dependency-audit.md",
            "missing-feature-audit.md",
            "blocking-items.md",
        ],
    },
    "09-final-export": {
        "directory": "09-final-export",
        "title": "当前撰写交付包",
        "paths": ["derived/drafting", "derived/audit"],
        "files": [
            "claims-draft.md",
            "specification-draft.md",
            "abstract-draft.md",
            "drawings-description.md",
            "drafting-delivery-summary.md",
            "unresolved-items.md",
        ],
    },
}


def read_path(document: dict[str, Any], path: str) -> tuple[bool, Any]:
    value: Any = document
    for part in path.split("/"):
        if not part:
            continue
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return False, None
    return True, value


def json_text(value: Any) -> str:
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False, indent=2)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def render(stage_id: str, stage: dict[str, Any], case_path: Path, document: dict[str, Any]) -> str:
    control = document.get("control", {}) if isinstance(document, dict) else {}
    revision = control.get("current_revision", control.get("revision", "unknown"))
    case = document.get("case", {}) if isinstance(document, dict) else {}
    case_id = case.get("case_id", case.get("id", "unknown")) if isinstance(case, dict) else "unknown"
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    missing: list[str] = []
    sections: list[str] = []
    for source_path in stage["paths"]:
        found, value = read_path(document, source_path)
        if not found:
            missing.append(source_path)
            value = "[JSON 中未找到该路径]"
        sections.append(f"## {source_path}\n\n```json\n{json_text(value)}\n```\n")
    status = "blocked" if missing else "generated"
    lines = [
        f"# {stage['title']}",
        "",
        "> 本文件由案件主 JSON 导出，仅作为当前版本的人工可读交付物。",
        "",
        f"- 案件：{case_id}",
        f"- 来源 JSON：{case_path}",
        f"- 来源版本：{revision}",
        f"- 视图：drafting",
        f"- 阶段：{stage_id}",
        f"- 生成状态：{status}",
        f"- 生成时间：{generated_at}",
        "",
    ]
    if missing:
        lines.extend([
            "## 阻断项",
            "",
            "以下 JSON 路径不存在，不能把本文件视为完整阶段交付：",
            "",
            *[f"- {item}" for item in missing],
            "",
        ])
    lines.extend(sections)
    lines.extend([
        "## 使用边界",
        "",
        "本文件不是案件事实的权威来源。人工修改后，必须由用户明确选择重新导入、仅作外部参考，或与当前 JSON 版本比较后生成 Patch。",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="从 case.json 生成撰写阶段 Markdown 交付物")
    parser.add_argument("--case-json", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=sorted(STAGES))
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()

    case_path = args.case_json.resolve()
    with case_path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    stage = STAGES[args.stage]
    output_root = (args.output_root or case_path.parent / "deliverables").resolve()
    generated: list[str] = []
    rendered = render(args.stage, stage, case_path, document)
    for filename in stage["files"]:
        target = output_root / stage["directory"] / filename
        atomic_write(target, rendered)
        generated.append(str(target))
    print(json.dumps({"stage": args.stage, "files": generated}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
