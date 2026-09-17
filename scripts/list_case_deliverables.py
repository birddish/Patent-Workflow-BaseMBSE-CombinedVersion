#!/usr/bin/env python3
"""List drafting deliverables registered in one case.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="列出 case.json 中登记的撰写交付物")
    parser.add_argument("--case-json", required=True, type=Path)
    args = parser.parse_args()

    case_path = args.case_json.resolve()
    with case_path.open("r", encoding="utf-8") as handle:
        document: dict[str, Any] = json.load(handle)
    control = document.get("control", {})
    revision = control.get("current_revision", control.get("revision", "unknown"))
    items = control.get("deliverables", [])
    if not isinstance(items, list):
        raise SystemExit("control.deliverables 不是数组，无法列出交付物")

    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("view") != "drafting":
            continue
        relative_path = item.get("path")
        absolute_path = None
        exists = False
        if isinstance(relative_path, str):
            candidate = Path(relative_path)
            absolute_path = str(candidate if candidate.is_absolute() else case_path.parent / candidate)
            exists = Path(absolute_path).is_file()
        result.append({
            "deliverable_id": item.get("deliverable_id"),
            "stage": item.get("stage"),
            "type": item.get("type"),
            "status": item.get("status"),
            "human_review": item.get("human_review"),
            "source_revision": item.get("source_revision"),
            "path": relative_path,
            "absolute_path": absolute_path,
            "exists": exists,
        })

    print(json.dumps({
        "case_json": str(case_path),
        "current_revision": revision,
        "deliverables": result,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
