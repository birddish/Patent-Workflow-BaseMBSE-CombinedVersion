"""Export one explicitly selected JSON-only pointer slice.

This command deliberately refuses whole-case, control-plane and raw-binary
exports. A caller must present the authoritative route confirmation recorded
for the current case revision; a CLI flag alone is not a confirmation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _case_utils import load_json, pointer_get


FORBIDDEN_POINTERS = {
    "/",
    "/control",
    "/source_materials/raw_artifacts",
}


def _is_forbidden_pointer(pointer: str) -> bool:
    normalized = pointer.rstrip("/") or "/"
    return any(
        normalized == prefix or normalized.startswith(prefix + "/")
        for prefix in FORBIDDEN_POINTERS
    )


def _valid_confirmation(case: dict[str, Any], confirmation_id: str) -> tuple[bool, str]:
    control = case.get("control") if isinstance(case.get("control"), dict) else {}
    confirmation = (
        control.get("route_confirmation")
        if isinstance(control.get("route_confirmation"), dict)
        else {}
    )
    current_revision = control.get("current_revision")
    selected_route = (
        confirmation.get("selected_route")
        if isinstance(confirmation.get("selected_route"), dict)
        else {}
    )
    if confirmation.get("case_id") != case.get("case", {}).get("case_id"):
        return False, "确认记录的 case_id 与当前案件不一致"
    if confirmation.get("status") != "confirmed":
        return False, "control.route_confirmation 不是 confirmed"
    if confirmation.get("confirmation_id") != confirmation_id:
        return False, "confirmation_id 与案件权威确认记录不一致"
    if confirmation.get("confirmed_revision") != current_revision:
        return False, "确认记录已因案件 revision 变化而失效"
    if selected_route.get("transaction") != "export_from_json":
        return False, "权威确认记录不是 export_from_json 事务"
    if selected_route.get("view") not in {"mbse", "search", "drafting", "oa", "invalidity", "audit"}:
        return False, "权威确认记录未绑定合法业务视图"
    return True, "confirmed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--transaction", choices=["export_from_json"], required=True)
    parser.add_argument("--confirmation-id", required=True)
    parser.add_argument("--pointer", required=True)
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output")
    args = parser.parse_args()

    if _is_forbidden_pointer(args.pointer):
        print(
            json.dumps(
                {
                    "exported": False,
                    "status": "blocked",
                    "errors": [
                        "禁止导出整个案件、控制区或 raw_artifacts；请指定受控业务切片。"
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    case = load_json(Path(args.case))
    valid, reason = _valid_confirmation(case, args.confirmation_id)
    if not valid:
        print(
            json.dumps(
                {"exported": False, "status": "blocked", "errors": [reason]},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    confirmed_view = case["control"]["route_confirmation"]["selected_route"]["view"]
    allowed_prefix = f"/derived/{confirmed_view}"
    if not (args.pointer == allowed_prefix or args.pointer.startswith(allowed_prefix + "/")):
        print(json.dumps({"exported": False, "status": "blocked", "errors": ["导出路径必须属于已确认的业务视图 /derived/" + confirmed_view]}, ensure_ascii=False, indent=2))
        return 1
    value = pointer_get(case, args.pointer)
    if args.format == "json":
        text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    else:
        text = "# JSON 导出\n\n"
        text += "&#96;&#96;&#96;json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n&#96;&#96;&#96;\n"
        text = text.replace("&#96;", chr(96))
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())