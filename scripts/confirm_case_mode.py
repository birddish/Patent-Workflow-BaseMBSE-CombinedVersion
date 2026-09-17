"""Enforce explicit route selection, conflict resolution, and confirmation binding.

The command keeps the existing CLI names but adds optional --profile,
--phase and --status-only fields. A first AI/user mismatch always returns
a challenge. An advisory challenge can be resolved only by repeating the
same request with the returned challenge_id, --advisory-override and a
non-empty --override-reason. Hard conflicts are never overridable.
"""
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from _case_utils import load_json, now_iso, save_json_atomic


TRANSACTIONS = {"bootstrap_import", "case_json_only", "reimport_material", "export_from_json"}
VIEWS = {"mbse", "search", "drafting", "oa", "invalidity", "audit"}

MBSE_SUBMODES = {"disclosure", "document", "search"}
SEARCH_SUBMODES = {"novelty", "invalidity", "FTO", "landscape"}
DRAFTING_STAGE_SUBMODES = {f"stage{number}" for number in range(1, 10)}
DRAFTING_SUBMODES = DRAFTING_STAGE_SUBMODES | {"stage1_stage3_claim_core"}
OA_SUBMODES = {"opinion", "reexamination"}
INVALIDITY_SUBMODES = {"defense"}
AUDIT_SUBMODES = {"status", "consistency", "ownership", "dependencies"}
OA_PHASES = {f"phase_{number:02d}" for number in range(1, 6)}
INVALIDITY_PHASES = {f"phase_{number:02d}" for number in range(1, 6)}
SEARCH_PROFILES = {"quick", "standard", "formal"}
AUDIT_PROFILES = {"l0", "l1", "l2", "l3"}
DOMAINS = {"mechanical", "electronics", "biochemical"}


def _value(args: argparse.Namespace, name: str, default: Any = "") -> Any:
    return getattr(args, name, default)


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _conflict(code: str, message: str, severity: str = "hard", field: str = "") -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message, "field": field}


def _canonical_phase(value: str) -> str | None:
    value = _text(value).lower().replace("-", "_")
    compact = value.replace("_", "")
    if compact.startswith("phase") and compact[5:].isdigit():
        return f"phase_{int(compact[5:]):02d}"
    if compact.startswith("stage") and compact[5:].isdigit():
        return f"stage_{int(compact[5:]):02d}"
    return value or None


def _canonical_submode(view: str | None, value: str) -> str | None:
    value = _text(value)
    if not value or not view:
        return value or None
    lowered = value.lower().replace("-", "_")
    if view == "mbse":
        return {"mode_disclosure": "disclosure", "mode_document": "document", "mode_search": "search"}.get(lowered, lowered)
    if view == "search":
        return {"fto": "FTO"}.get(lowered, lowered)
    if view == "drafting":
        aliases = {
            "claim_core": "claim_core",
            "claimcore": "claim_core",
            "dependent_claim": "dependent_claims",
            "dependent_claims": "dependent_claims",
            "claim_text": "claim_text_audit",
            "claim_text_audit": "claim_text_audit",
            "support": "support_traceability",
            "support_traceability": "support_traceability",
            "stage1_3_claim_core": "stage1_stage3_claim_core",
            "stage1_stage3_claim_core": "stage1_stage3_claim_core",
        }
        return aliases.get(lowered, lowered)
    if view == "oa":
        return {
            "response": "opinion",
            "oa_response": "opinion",
            "opinion_drafting": "opinion",
            "answer": "opinion",
            "appeal": "reexamination",
            "reexamination": "reexamination",
            "re_exam": "reexamination",
        }.get(lowered, value)
    if view == "audit":
        return lowered
    return value


def _canonical_profile(view: str | None, value: str) -> str | None:
    value = _text(value)
    if not value:
        return None
    lowered = value.lower()
    if view == "search" and lowered in SEARCH_PROFILES:
        return lowered
    if view == "invalidity" and lowered == "v2.1-invalidity":
        return "v2.1-invalidity"
    if view == "oa" and lowered == "v2.1-oa":
        return "v2.1-oa"
    if view == "drafting" and lowered in {"standard", "controlled"}:
        return lowered
    if view == "audit" and lowered in AUDIT_PROFILES:
        return lowered
    return value


def normalized_route(args: argparse.Namespace) -> dict[str, Any]:
    """Return the machine-route canonical scope without deciding validity."""
    transaction = _text(_value(args, "transaction"))
    status_only = bool(_value(args, "status_only", False))
    raw_view = _text(_value(args, "view")) or None
    raw_submode = _text(_value(args, "submode")) or None
    raw_profile = _text(_value(args, "profile")) or None
    raw_phase = _text(_value(args, "phase")) or None
    raw_domain = _text(_value(args, "domain")) or None

    if status_only:
        view = "audit"
        submode = "status"
        profile = "l0"
        phase = "audit"
        domain = raw_domain or "all"
    else:
        view = raw_view
        submode = _canonical_submode(view, raw_submode or "")
        profile = _canonical_profile(view, raw_profile or "")
        phase = _canonical_phase(raw_phase or "")
        domain = raw_domain.lower() if raw_domain else None

        if view == "oa" and raw_submode and raw_submode.lower() == "v2.1-oa":
            submode = "opinion"
            profile = profile or "v2.1-oa"

        if view == "audit" and submode in AUDIT_PROFILES:
            profile = submode
            submode = "status"

        if view == "drafting" and submode in {"claim_core", "dependent_claims", "claim_text_audit", "support_traceability"}:
            alias_targets = {
                "claim_core": {"stage_01", "stage_03"},
                "dependent_claims": {"stage_03"},
                "claim_text_audit": {"stage_03", "stage_08"},
                "support_traceability": {"stage_03", "stage_08"},
            }
            if phase in alias_targets[submode]:
                submode = f"stage{int(phase.split('_')[1])}"

        if view == "mbse":
            profile = profile or "standard"
            phase = phase or "modeling"
        elif view == "search":
            phase = phase or "search"
        elif view == "drafting":
            if submode == "stage1_stage3_claim_core":
                profile = profile or "controlled"
                phase = phase or "stage_03"
            elif submode in DRAFTING_STAGE_SUBMODES:
                profile = profile or "standard"
                phase = phase or f"stage_{int(submode[5:]):02d}"
        elif view == "audit":
            phase = phase or "audit"
            if submode == "status":
                profile = profile or "l0"

    route: dict[str, Any] = {
        "transaction": transaction,
        "view": view,
        "submode": submode,
        "profile": profile,
        "phase": phase,
        "domain": domain,
    }
    if status_only:
        route["status_only"] = True
    return route

def route_scope(route: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in route.items() if value not in (None, "")}


def ai_route(args: argparse.Namespace) -> dict[str, Any]:
    ai_args = argparse.Namespace(
        transaction=_value(args, "ai_transaction"),
        view=_value(args, "ai_view"),
        submode=_value(args, "ai_submode"),
        profile=_value(args, "ai_profile"),
        phase=_value(args, "ai_phase"),
        domain=_value(args, "ai_domain"),
        status_only=False,
    )
    return normalized_route(ai_args)


def nonempty_collection(case: dict[str, Any], pointer: tuple[str, ...]) -> bool:
    value: Any = case
    for key in pointer:
        if not isinstance(value, dict):
            return False
        value = value.get(key)
    return isinstance(value, (list, dict)) and bool(value)


def current_revision(case: dict[str, Any] | None) -> int | None:
    if case is None:
        return None
    value = case.get("control", {}).get("current_revision", 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _route_conflicts(case: dict[str, Any] | None, args: argparse.Namespace, route: dict[str, Any]) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    transaction = route["transaction"]
    view = route["view"]
    submode = route["submode"]
    profile = route["profile"]
    phase = route["phase"]
    exists = case is not None
    status_only = bool(_value(args, "status_only", False))

    if transaction not in TRANSACTIONS:
        conflicts.append(_conflict("unsupported_transaction", f"用户选择的事务模式不受支持: {transaction}", field="transaction"))

    if status_only:
        if transaction != "case_json_only":
            conflicts.append(_conflict("status_transaction_mismatch", "--status-only 只能与 case_json_only 一起使用", field="transaction"))
        raw_view = _text(_value(args, "view"))
        raw_submode = _text(_value(args, "submode"))
        if raw_view and raw_view != "audit":
            conflicts.append(_conflict("status_unrelated_view", "D. 仅查看案件状态不接受无关业务视图；请省略 --view，或明确使用 audit", field="view"))
        if raw_submode and _canonical_submode("audit", raw_submode) not in {"status", "l0"}:
            conflicts.append(_conflict("status_unrelated_submode", "D. 状态查看不接受无关子模式；请省略 --submode，或使用 status/l0", field="submode"))
        if _text(_value(args, "profile")) or _text(_value(args, "phase")):
            conflicts.append(_conflict("status_extra_route_scope", "D. 状态查看不需要 profile 或 phase", field="profile/phase"))
    elif view is None:
        if transaction in {"case_json_only", "export_from_json"}:
            conflicts.append(_conflict("view_required", f"{transaction} 必须明文选择 view 和 submode", field="view"))
        if submode is not None or profile is not None or phase is not None:
            conflicts.append(_conflict("partial_route", "未选择 view 时不能单独提供 submode、profile 或 phase", field="view"))
    elif view not in VIEWS:
        conflicts.append(_conflict("unsupported_view", f"用户选择的业务视图不受支持: {view}", field="view"))

    if view in VIEWS:
        if submode is None:
            conflicts.append(_conflict("submode_required", f"业务视图 {view} 必须明文选择合法 submode", field="submode"))
        allowed_domains = DOMAINS | ({"all"} if view == "audit" else set())
        domain = route.get("domain")
        if domain not in allowed_domains:
            conflicts.append(_conflict("domain_required", f"视图 {view} 必须明文确认技术领域；合法值为 {sorted(allowed_domains)}", field="domain"))
        if view == "mbse":
            if submode not in MBSE_SUBMODES:
                conflicts.append(_conflict("invalid_mbse_submode", f"MBSE 合法 submode 为 disclosure/document/search，当前为 {submode}", field="submode"))
            if profile != "standard" or phase != "modeling":
                conflicts.append(_conflict("invalid_mbse_route", "MBSE 机器路由固定使用 profile=standard、phase=modeling", field="profile/phase"))
        elif view == "search":
            if submode not in SEARCH_SUBMODES:
                conflicts.append(_conflict("invalid_search_submode", f"检索合法 submode 为 novelty/invalidity/FTO/landscape，当前为 {submode}", field="submode"))
            if profile not in SEARCH_PROFILES:
                conflicts.append(_conflict("search_profile_required", "检索必须明文选择 profile：quick、standard 或 formal", field="profile"))
            if phase != "search":
                conflicts.append(_conflict("invalid_search_phase", "检索机器路由固定使用 phase=search", field="phase"))
        elif view == "drafting":
            if submode not in DRAFTING_SUBMODES:
                conflicts.append(_conflict("invalid_drafting_submode", f"撰写 canonical submode 为 stage1 至 stage9 或 stage1_stage3_claim_core，当前为 {submode}", field="submode"))
            if submode == "stage1_stage3_claim_core":
                if profile != "controlled" or phase != "stage_03":
                    conflicts.append(_conflict("invalid_controlled_drafting_route", "受控阶段1＋3固定使用 profile=controlled、phase=stage_03", field="profile/phase"))
            elif submode in DRAFTING_STAGE_SUBMODES:
                expected_phase = f"stage_{int(submode[5:]):02d}"
                if profile != "standard" or phase != expected_phase:
                    conflicts.append(_conflict("drafting_phase_mismatch", f"撰写 {submode} 必须使用 profile=standard、phase={expected_phase}", field="profile/phase"))
        elif view == "oa":
            if submode not in OA_SUBMODES:
                conflicts.append(_conflict("invalid_oa_submode", f"答审/复审合法 submode 为 opinion 或 reexamination，当前为 {submode}", field="submode"))
            if profile != "v2.1-oa":
                conflicts.append(_conflict("oa_profile_required", "答审/复审必须明确使用 v2.1-oa 版本合同", field="profile"))
            if phase not in OA_PHASES:
                conflicts.append(_conflict("oa_phase_required", "答审/复审必须明文选择 phase_01 至 phase_05", field="phase"))
        elif view == "invalidity":
            if submode not in INVALIDITY_SUBMODES:
                conflicts.append(_conflict("invalidity_submode_required", "无效答辩意见陈述合法 submode 仅为 defense，不能改用 search.invalidity 或 oa.opinion", field="submode"))
            if profile != "v2.1-invalidity":
                conflicts.append(_conflict("invalidity_profile_required", "无效答辩意见陈述必须明确使用 v2.1-invalidity 版本合同", field="profile"))
            if phase not in INVALIDITY_PHASES:
                conflicts.append(_conflict("invalidity_phase_required", "无效答辩意见陈述必须明文选择 phase_01 至 phase_05", field="phase"))
        elif view == "audit":
            if submode not in AUDIT_SUBMODES:
                conflicts.append(_conflict("invalid_audit_submode", f"审计合法 submode 为 status/consistency/ownership/dependencies，当前为 {submode}", field="submode"))
            if profile not in AUDIT_PROFILES:
                conflicts.append(_conflict("audit_profile_required", "审计必须选择读取级别 profile=l0/l1/l2/l3", field="profile"))
            if phase != "audit":
                conflicts.append(_conflict("invalid_audit_phase", "审计机器路由固定使用 phase=audit", field="phase"))
    if transaction == "bootstrap_import":
        if exists:
            conflicts.append(_conflict("bootstrap_case_exists", "主 JSON 已存在，不能把首次导入当作 bootstrap_import；请改选 reimport_material 或 case_json_only"))
        if not bool(_value(args, "materials_listed", False)):
            conflicts.append(_conflict("bootstrap_materials_required", "A. 首次导入必须明文列出待导入材料，并使用 --materials-listed"))
    elif transaction == "reimport_material":
        if not exists:
            conflicts.append(_conflict("reimport_case_missing", "C. 重新导入/合并要求主 JSON 已存在"))
        if not bool(_value(args, "materials_listed", False)):
            conflicts.append(_conflict("reimport_materials_required", "C. 重新导入/合并必须明文列出材料，并使用 --materials-listed"))
    elif transaction in {"case_json_only", "export_from_json"} and not exists:
        conflicts.append(_conflict("case_json_missing", f"用户选择 {transaction}，但主 JSON 不存在"))

    if transaction == "case_json_only" and bool(_value(args, "external_requested", False)):
        conflicts.append(_conflict("json_only_external_read", "case_json_only 禁止读取未先导入主 JSON 的外部材料；请保持 JSON-only 或改选 reimport_material"))
    if transaction == "export_from_json" and bool(_value(args, "external_requested", False)):
        conflicts.append(_conflict("export_external_read", "export_from_json 只能以主 JSON 为输入，不能读取未导入的外部材料"))

    if case is not None and _value(args, "expected_revision", None) is not None:
        revision = current_revision(case)
        if revision != _value(args, "expected_revision"):
            conflicts.append(_conflict("expected_revision_mismatch", f"案件当前 revision 为 {revision}，不是用户/计划指定的 {_value(args, 'expected_revision')}; 请重新读取 L0 后确认", field="current_revision"))

    if case is not None and view == "invalidity" and not (nonempty_collection(case, ("normalized", "issues")) or nonempty_collection(case, ("normalized", "claims")) or nonempty_collection(case, ("source_materials", "documents"))):
        conflicts.append(_conflict("invalidity_input_missing", "无效答辩视图缺少已导入的无效理由/权利要求/案件文档；JSON-only 下不得自动回读外部材料"))
    if case is not None and view == "oa" and not (nonempty_collection(case, ("normalized", "issues")) or nonempty_collection(case, ("source_materials", "documents"))):
        conflicts.append(_conflict("oa_input_missing", "OA/复审视图缺少已导入的审查意见、驳回决定或案件文档"))
    if case is not None and view == "drafting" and submode == "stage1_stage3_claim_core" and not nonempty_collection(case, ("normalized", "technical_facts")) and not nonempty_collection(case, ("derived", "mbse")):
        conflicts.append(_conflict("drafting_input_missing", "撰写阶段 1＋3 缺少已导入或已规范化的技术事实/MBSE 输入"))
    if case is not None and view == "search" and submode in SEARCH_SUBMODES and transaction == "case_json_only" and not (nonempty_collection(case, ("source_materials", "search_results")) or nonempty_collection(case, ("derived", "search"))):
        conflicts.append(_conflict("search_json_input_missing", "JSON-only 检索缺少已导入的检索结果或既有检索视图；不能自动访问外部数据库"))
    return conflicts


def _ai_conflicts(args: argparse.Namespace, route: dict[str, Any]) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    ai = ai_route(args)
    user_transaction = route.get("transaction")
    ai_transaction = ai.get("transaction")
    if _text(_value(args, "ai_transaction")) and ai_transaction != user_transaction:
        conflicts.append(_conflict("ai_transaction_mismatch", f"用户明文事务模式为 {user_transaction}，AI 判断为 {ai_transaction}", "advisory", "transaction"))
    if _text(_value(args, "ai_view")) and route.get("view") and ai.get("view") != route.get("view"):
        conflicts.append(_conflict("ai_view_mismatch", f"用户明文业务视图为 {route.get('view')}，AI 判断为 {ai.get('view')}", "advisory", "view"))
    if _text(_value(args, "ai_submode")) and route.get("submode") and ai.get("submode") != route.get("submode"):
        conflicts.append(_conflict("ai_submode_mismatch", f"用户明文子模式为 {route.get('submode')}，AI 判断为 {ai.get('submode')}", "advisory", "submode"))
    if _text(_value(args, "ai_profile")) and route.get("profile") != ai.get("profile"):
        conflicts.append(_conflict("ai_profile_mismatch", f"用户明文 profile 为 {route.get('profile')}，AI 判断为 {ai.get('profile')}", "advisory", "profile"))
    if _text(_value(args, "ai_phase")) and route.get("phase") != ai.get("phase"):
        conflicts.append(_conflict("ai_phase_mismatch", f"用户明文 phase 为 {route.get('phase')}，AI 判断为 {ai.get('phase')}", "advisory", "phase"))
    if _text(_value(args, "ai_domain")) and route.get("domain") != ai.get("domain"):
        conflicts.append(_conflict("ai_domain_mismatch", f"用户明文 domain 为 {route.get('domain')}，AI 判断为 {ai.get('domain')}", "advisory", "domain"))
    return conflicts


def collect_conflicts(case: dict[str, Any] | None, args: argparse.Namespace, route: dict[str, Any] | None = None) -> list[dict[str, str]]:
    route = route or normalized_route(args)
    return _route_conflicts(case, args, route) + _ai_conflicts(args, route)


def assess(case: dict[str, Any] | None, args: argparse.Namespace) -> list[str]:
    """Backward-compatible string-only assessment API."""
    return [item["message"] for item in collect_conflicts(case, args)]


def _challenge_id(case: dict[str, Any] | None, route: dict[str, Any], conflicts: list[dict[str, str]]) -> str:
    revision = current_revision(case)
    revision_text = "new" if revision is None else str(revision)
    codes = "+".join(item["code"] for item in conflicts)
    scope = "+".join(f"{key}={value}" for key, value in route_scope(route).items())
    safe_scope = scope.replace("/", "_").replace(" ", "_") or "route"
    return f"CHALLENGE-R{revision_text}-{safe_scope}-{codes}"


def _confirmation_binding(case: dict[str, Any] | None, route: dict[str, Any]) -> dict[str, Any]:
    requested = route_scope(route)
    if case is None:
        return {"valid": False, "reason": "case_json_not_created", "source": None, "confirmation_id": None, "current_revision": None, "confirmed_revision": None, "stored_route_scope": None, "requested_route_scope": requested}

    control = case.get("control", {})
    current = current_revision(case)
    authoritative = control.get("route_confirmation")
    if isinstance(authoritative, dict):
        confirmed = authoritative.get("confirmed_revision")
        stored_scope = authoritative.get("selected_route")
        case_id = case.get("case", {}).get("case_id")
        valid = (
            authoritative.get("status") == "confirmed"
            and isinstance(authoritative.get("confirmation_id"), str)
            and bool(authoritative.get("confirmation_id"))
            and authoritative.get("case_id") == case_id
            and isinstance(confirmed, int)
            and confirmed == current
            and stored_scope == requested
        )
        if valid:
            reason = "authoritative_confirmation_matches"
        elif authoritative.get("status") != "confirmed":
            reason = "not_confirmed"
        elif confirmed != current:
            reason = "current_revision_changed"
        elif authoritative.get("case_id") != case_id:
            reason = "case_id_changed"
        elif stored_scope != requested:
            reason = "route_scope_changed"
        else:
            reason = "confirmation_binding_invalid"
        return {"valid": valid, "reason": reason, "source": "control.route_confirmation", "confirmation_id": authoritative.get("confirmation_id"), "current_revision": current, "confirmed_revision": confirmed, "stored_route_scope": stored_scope, "requested_route_scope": requested}

    # Read-only compatibility for cases confirmed by an older installed version.
    navigation = control.get("navigation", {})
    confirmed = navigation.get("confirmed_revision") if isinstance(navigation, dict) else None
    stored_scope = navigation.get("route_scope") if isinstance(navigation, dict) else None
    valid = (
        isinstance(navigation, dict)
        and navigation.get("confirmation_status") == "confirmed"
        and isinstance(confirmed, int)
        and confirmed == current
        and stored_scope == requested
    )
    if valid:
        reason = "legacy_navigation_matches_reconfirm_required_for_route_plan"
    elif not isinstance(navigation, dict) or navigation.get("confirmation_status") != "confirmed":
        reason = "not_confirmed"
    elif confirmed != current:
        reason = "current_revision_changed"
    elif stored_scope != requested:
        reason = "route_scope_changed"
    else:
        reason = "confirmation_binding_invalid"
    return {"valid": valid, "reason": reason, "source": "control.navigation_legacy", "confirmation_id": None, "current_revision": current, "confirmed_revision": confirmed, "stored_route_scope": stored_scope, "requested_route_scope": requested}

def _user_selection(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "transaction": _text(_value(args, "transaction")) or None,
        "view": _text(_value(args, "view")) or None,
        "submode": _text(_value(args, "submode")) or None,
        "profile": _text(_value(args, "profile")) or None,
        "phase": _text(_value(args, "phase")) or None,
        "domain": _text(_value(args, "domain")) or None,
        "status_only": bool(_value(args, "status_only", False)),
    }


def _result(case: dict[str, Any] | None, args: argparse.Namespace, route: dict[str, Any], conflicts: list[dict[str, str]], challenge_id: str | None = None, resolved: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    binding = _confirmation_binding(case, route)
    hard = [item for item in conflicts if item["severity"] == "hard"]
    advisory = [item for item in conflicts if item["severity"] == "advisory"]
    return {
        "confirmation_status": "confirmed" if not conflicts else "challenge_required",
        "challenge_required": bool(conflicts),
        "user_selection": _user_selection(args),
        "canonical_route": route,
        "route_scope": route_scope(route),
        "ai_routing_assessment": {
            "transaction": _text(_value(args, "ai_transaction")) or None,
            "view": _text(_value(args, "ai_view")) or None,
            "submode": _text(_value(args, "ai_submode")) or None,
            "profile": _text(_value(args, "ai_profile")) or None,
            "phase": _text(_value(args, "ai_phase")) or None,
            "domain": _text(_value(args, "ai_domain")) or None,
        },
        "conflicts": conflicts,
        "reasons": [item["message"] for item in conflicts],
        "hard_conflicts": hard,
        "advisory_conflicts": advisory,
        "resolved_conflicts": resolved or [],
        "challenge_id": challenge_id,
        "confirmation_binding": binding,
        "confirmation_artifact": case.get("control", {}).get("route_confirmation") if isinstance(case, dict) else None,
        "next_action": (
            "先向用户明示 hard conflict；hard conflict 不允许 override"
            if hard
            else "请向用户明示 advisory conflict，并要求针对 challenge_id 明文选择保持或改选"
            if advisory
            else "可以按已确认模式加载对应 JSON 切片和内部规则"
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="明文模式、合法组合、冲突解决和 revision 绑定确认门")
    parser.add_argument("--case", required=True)
    parser.add_argument("--transaction", required=True, help="bootstrap_import/case_json_only/reimport_material/export_from_json")
    parser.add_argument("--view", default="", help="非纯导入事务必填；D 状态查看可省略并使用 --status-only")
    parser.add_argument("--submode", default="")
    parser.add_argument("--profile", default="")
    parser.add_argument("--phase", default="")
    parser.add_argument("--domain", default="", help="mechanical/electronics/biochemical；audit 可使用 all")
    parser.add_argument("--status-only", action="store_true", help="D. 仅查看案件状态；自动使用 audit/status，不要求无关视图字段")
    parser.add_argument("--ai-transaction", default="")
    parser.add_argument("--ai-view", default="")
    parser.add_argument("--ai-submode", default="")
    parser.add_argument("--ai-profile", default="")
    parser.add_argument("--ai-phase", default="")
    parser.add_argument("--ai-domain", default="")
    parser.add_argument("--materials-listed", action="store_true")
    parser.add_argument("--material", action="append", default=[], help="A/C 明文列出的单个外部材料路径；可重复")
    parser.add_argument("--strategy", choices=["append", "parallel", "replace"], default="")
    parser.add_argument("--old-batch-policy", choices=["retain"], default="")
    parser.add_argument("--external-requested", action="store_true")
    parser.add_argument("--expected-revision", type=int, default=None)
    parser.add_argument("--challenge-id", default="", help="第一次 challenge 返回的 challenge_id")
    parser.add_argument("--advisory-override", action="store_true", help="针对指定 challenge_id 明文坚持用户选择；仅 advisory 可用")
    parser.add_argument("--override-reason", default="", help="advisory override 的明文理由")
    parser.add_argument("--check-confirmation", action="store_true", help="只检查已有确认是否仍绑定当前 revision 和 route scope")
    parser.add_argument("--write-confirmation", action="store_true")
    parser.add_argument("--actor", default="user")
    return parser


def main() -> int:
    args = _parser().parse_args()
    case_path = Path(args.case)
    case = load_json(case_path) if case_path.exists() else None
    route = normalized_route(args)
    conflicts = collect_conflicts(case, args, route)
    if args.transaction == "reimport_material" and args.write_confirmation:
        if not args.material or any(not item.strip() for item in args.material):
            conflicts.append(_conflict("reimport_file_scope_required", "C. 确认前必须以 --material 明列每一个材料路径", "hard", "material"))
        if not args.strategy or not args.old_batch_policy:
            conflicts.append(_conflict("reimport_strategy_scope_required", "C. 确认前必须明文选择 strategy 和 old_batch_policy", "hard", "strategy"))
    base_challenge_id = _challenge_id(case, route, conflicts) if conflicts else None
    resolved: list[dict[str, Any]] = []

    if args.advisory_override:
        hard = [item for item in conflicts if item["severity"] == "hard"]
        advisory = [item for item in conflicts if item["severity"] == "advisory"]
        if hard:
            conflicts.append(_conflict("advisory_override_rejected", "存在 hard conflict，不能通过 advisory override 绕过", "hard"))
        elif not advisory:
            conflicts.append(_conflict("override_not_applicable", "当前没有可供 override 的 advisory conflict", "hard"))
        elif not args.challenge_id or args.challenge_id != base_challenge_id:
            conflicts.append(_conflict("challenge_id_mismatch", f"必须携带本次首次 challenge 返回的 challenge_id: {base_challenge_id}", "hard", "challenge_id"))
        elif not _text(args.override_reason):
            conflicts.append(_conflict("override_reason_required", "advisory override 必须明文填写 override_reason", "hard", "override_reason"))
        else:
            resolved = [
                {
                    **item,
                    "status": "resolved",
                    "resolution": "override_keep_user_selection",
                    "challenge_id": base_challenge_id,
                    "override_reason": args.override_reason,
                }
                for item in advisory
            ]
            conflicts = hard
    elif args.challenge_id and not conflicts:
        conflicts.append(_conflict("challenge_id_without_conflict", "没有待解决的冲突，不能使用 challenge_id 代替新的明文确认", "hard", "challenge_id"))

    challenge_id = _challenge_id(case, route, conflicts) if conflicts else base_challenge_id
    if args.check_confirmation:
        result = _result(case, args, route, conflicts, challenge_id, resolved)
        if not conflicts:
            binding = result["confirmation_binding"]
            result["confirmation_status"] = "confirmed" if binding["valid"] else "invalidated"
            result["challenge_required"] = not binding["valid"]
            result["next_action"] = "已有确认仍然有效，可以继续" if binding["valid"] else "确认已因 revision 或 route scope 变化失效；请重新明文确认"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["confirmation_status"] == "confirmed" and not conflicts else 1

    if conflicts or not args.write_confirmation:
        result = _result(case, args, route, conflicts, challenge_id, resolved)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if conflicts else 0

    if case is None:
        result = _result(case, args, route, [], challenge_id, resolved)
        result["confirmation_status"] = "confirmed_but_not_recorded_no_case_json"
        result["next_action"] = "可继续 bootstrap_import；案件创建后必须重新确认并记录绑定 revision"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # Re-read immediately before write so a revision change during the gate is not silently accepted.
    latest = load_json(case_path)
    initial_revision = current_revision(case)
    latest_revision = current_revision(latest)
    if latest_revision != initial_revision:
        race_conflict = _conflict("revision_changed_during_confirmation", f"确认期间案件 revision 从 {initial_revision} 变为 {latest_revision}；必须重新读取并确认", "hard", "current_revision")
        result = _result(latest, args, route, [race_conflict], _challenge_id(latest, route, [race_conflict]), resolved)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    revision = (latest_revision or 0) + 1
    control = latest.setdefault("control", {})
    control["current_revision"] = revision
    confirmation_id = f"CONF-{uuid.uuid4().hex[:12].upper()}"
    confirmed_at = now_iso()
    ai_assessment = _result(latest, args, route, [], challenge_id, resolved)["ai_routing_assessment"]
    navigation = control.setdefault("navigation", {})
    navigation.update({
        "user_selected_transaction": args.transaction,
        "user_selected_view": _text(args.view) or ("audit" if args.status_only else None),
        "user_selected_submode": _text(args.submode) or ("status" if args.status_only else None),
        "user_selected_profile": _text(args.profile) or None,
        "user_selected_phase": _text(args.phase) or None,
        "user_selected_domain": _text(args.domain) or None,
        "ai_routing_assessment": ai_assessment,
        "route_scope": route_scope(route),
        "confirmation_base_revision": latest_revision,
        "confirmed_revision": revision,
        "consistency_check": "pass",
        "challenge_required": False,
        "confirmation_status": "confirmed",
        "confirmed_at": confirmed_at,
    })
    if route.get("view"):
        selected_route = route_scope(route)
        case_id = latest.get("case", {}).get("case_id")
        control["active_route"] = selected_route
        control["route_confirmation"] = {
            "confirmation_id": confirmation_id,
            "status": "confirmed",
            "case_id": case_id,
            "base_revision": latest_revision,
            "confirmed_revision": revision,
            "selected_route": selected_route,
            **({"import_scope": {"files": [str(Path(item).resolve()) for item in args.material], "strategy": args.strategy, "old_batch_policy": args.old_batch_policy}} if args.transaction == "reimport_material" else {}),
            "user_selection": _user_selection(args),
            "ai_routing_assessment": ai_assessment,
            "challenge_ids": list(dict.fromkeys(item.get("challenge_id") for item in resolved if item.get("challenge_id"))),
            "confirmed_by": args.actor,
            "confirmed_at": confirmed_at,
        }
    transaction = {
        "transaction_id": f"TX-MODE-{uuid.uuid4().hex[:10].upper()}",
        "kind": args.transaction,
        "status": "confirmed",
        "confirmation_id": confirmation_id,
        "base_revision": latest_revision,
        "result_revision": revision,
        "actor": args.actor,
        "user_selection": _user_selection(args),
        "canonical_route": route,
        "route_scope": route_scope(route),
        "ai_routing_assessment": navigation["ai_routing_assessment"],
        "finished_at": now_iso(),
    }
    if resolved:
        transaction["advisory_overrides"] = resolved
        control.setdefault("conflicts", []).extend({**item, "resolved_revision": revision} for item in resolved)
        control.setdefault("challenge_resolutions", []).extend({**item, "resolved_revision": revision} for item in resolved)
    control.setdefault("transactions", []).append(transaction)
    save_json_atomic(case_path, latest)
    result = _result(latest, args, route, [], challenge_id, resolved)
    result["recorded_revision"] = revision
    result["confirmation_binding"] = _confirmation_binding(latest, route)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
