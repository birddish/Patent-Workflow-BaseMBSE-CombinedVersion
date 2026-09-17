#!/usr/bin/env python3
"""User-facing wrapper for the drafting-stage automation.

Default output is Markdown. JSON output is available only when the caller
explicitly passes --machine-readable for an internal integration.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def absolute_link(case_json: Path, relative_path: Any) -> str:
    if not isinstance(relative_path, str):
        return "未提供路径"
    path = Path(relative_path)
    absolute = path if path.is_absolute() else case_json.parent / path
    return absolute.resolve().as_posix()


def markdown_success(result: dict[str, Any], case_json: Path) -> str:
    lines = [
        "# 撰写阶段交付结果",
        "",
        "> 本次用户交付以 Markdown 文件为准；case.json 仅作为后台案件数据源。",
        "",
        f"- 案件主 JSON：{result.get('case_json', case_json)}",
        f"- 撰写阶段：{result.get('stage', '未提供')}",
        f"- 来源版本：{result.get('source_revision', '未提供')}",
        f"- 撰写模式：{result.get('writing_mode', '未提供')}",
        f"- 当前状态：{result.get('status', '未提供')}",
        "",
        "## 已生成的 Markdown 交付文件",
        "",
    ]
    deliverables = result.get("deliverables", [])
    if isinstance(deliverables, list) and deliverables:
        for item in deliverables:
            if not isinstance(item, dict):
                continue
            path = absolute_link(case_json, item.get("path"))
            name = Path(str(item.get("path", "交付文件"))).name
            lines.append(f"- [{name}]({path}) — {item.get('status', 'generated')}，等待人工审阅")
    else:
        lines.append("- 本次没有生成可见交付文件。")
    lines.extend([
        "",
        "## 下一步",
        "",
        str(result.get("next_action", "请打开上述 Markdown 文件进行人工审阅。")),
        "",
        "请勿直接把 case.json 作为本次撰写成果交付；如需修改 Markdown 文件，必须先选择重新导入、仅作外部参考，或比较后生成 Patch。",
    ])
    return "\n".join(lines)


def markdown_failure(payload: dict[str, Any], case_json: Path) -> str:
    lines = [
        "# 撰写阶段未生成交付物",
        "",
        "> 本次没有把后台 JSON 错误对象直接作为用户交付。",
        "",
        f"- 案件主 JSON：{case_json}",
        f"- 状态：{payload.get('status', 'blocked')}",
        f"- 原因：{payload.get('reason', 'unknown')}",
        "",
        "## 处理说明",
        "",
        str(payload.get("message", "当前阶段无法生成 Markdown 交付文件。")),
    ]
    if payload.get("selected_mode") is not None:
        lines.append(f"- 用户选择模式：{payload['selected_mode']}")
    if payload.get("recommended_mode") is not None:
        lines.append(f"- AI 推荐模式：{payload['recommended_mode']}")
    lines.extend([
        "",
        "在阻断项处理完毕前，不生成或覆盖当前阶段的 Markdown 交付文件。",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="以 Markdown 作为用户界面的撰写阶段自动化入口")
    parser.add_argument("--case-json", required=True, type=Path)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--writing-mode")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--machine-readable", action="store_true", help="仅供内部调用，输出 JSON")
    args = parser.parse_args()

    orchestrator = Path(__file__).with_name("run_drafting_stage.py")
    command = [
        sys.executable,
        str(orchestrator),
        "--case-json",
        str(args.case_json),
        "--stage",
        args.stage,
    ]
    if args.writing_mode:
        command.extend(["--writing-mode", args.writing_mode])
    if args.output_root:
        command.extend(["--output-root", str(args.output_root)])

    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    raw = completed.stdout.strip() or completed.stderr.strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {
            "status": "failed",
            "reason": "automation_output_not_json",
            "message": raw or "撰写自动化入口没有返回可识别结果。",
        }

    if args.machine_readable:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif completed.returncode == 0 and payload.get("status") not in {"blocked", "failed"}:
        print(markdown_success(payload, args.case_json.resolve()))
    else:
        print(markdown_failure(payload, args.case_json.resolve()))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
