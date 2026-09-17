"""Build a bounded, machine-readable RoutePlan from an explicit user selection.

The planner is read-only.  ``rule_files`` is the base rule set and is never
allowed to exceed four files.  Operation-gated rule groups are described in
``conditional_rule_groups`` and resolved into ``conditional_rule_files``;
only ``active_conditional_rule_files`` may be appended by the total controller
when the trigger is satisfied.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


EXIT_READY = 0
EXIT_CONFIRMATION_REQUIRED = 2
EXIT_CHALLENGE_REQUIRED = 3
EXIT_BLOCKED = 4
BASE_RULE_FILE_LIMIT = 4

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ROUTING_ROOT = PACKAGE_ROOT / "references" / "routing"
TRANSACTION_PATH = ROUTING_ROOT / "transactions.json"
REGISTRY_PATH = ROUTING_ROOT / "rule-registry.json"
SLICE_PROFILE_PATH = ROUTING_ROOT / "slice-profiles.json"
VIEW_ROOT = ROUTING_ROOT / "views"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"配置文件顶层必须是对象: {path}")
    return value


def json_pointer_get(document: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise ValueError(f"JSON Pointer 必须以 / 开头: {pointer}")
    current = document
    if pointer == "/":
        return current
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise KeyError(pointer)
            current = current[token]
        elif isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError):
                raise KeyError(pointer) from None
        else:
            raise KeyError(pointer)
    return current


def is_present(document: dict[str, Any] | None, pointer: str) -> bool:
    if document is None:
        return False
    try:
        value = json_pointer_get(document, pointer)
    except (KeyError, TypeError, ValueError):
        return False
    if value is None or value is False:
        return False
    if isinstance(value, (str, list, dict, tuple, set)):
        return bool(value)
    return True


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def render(value: str, selection: dict[str, Any]) -> str:
    """Render only known route placeholders; unknown placeholders are errors."""
    try:
        return value.format(**selection)
    except KeyError as exc:
        raise ValueError(f"路由配置引用了未定义占位符: {value} -> {exc.args[0]}") from exc


def route_id_fallback(view: str, submode: str) -> str:
    return f"unresolved.{view or 'unknown-view'}.{submode or 'unknown-submode'}"


def error(code: str, message: str, severity: str = "hard", field: str | None = None) -> dict[str, str]:
    item = {"code": code, "severity": severity, "message": message}
    if field:
        item["field"] = field
    return item


def load_case(case_path: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    if not case_path.exists():
        return None, []
    if not case_path.is_file():
        return None, [error("invalid_case_path", f"案件路径不是文件: {case_path}")]
    try:
        case = load_json(case_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, [error("invalid_case_json", f"无法读取主案件 JSON: {exc}", field="case")]
    errors: list[dict[str, str]] = []
    if not isinstance(case.get("case"), dict) or not case.get("case", {}).get("case_id"):
        errors.append(error("invalid_case_json", "主案件 JSON 缺少 case.case_id", field="/case/case_id"))
    control = case.get("control")
    if not isinstance(control, dict) or not isinstance(control.get("current_revision"), int):
        errors.append(error("invalid_case_json", "主案件 JSON 缺少整数 control.current_revision", field="/control/current_revision"))
    return case, errors


def select_route(view_config: dict[str, Any] | None, args: argparse.Namespace, errors: list[dict[str, str]]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    selection = {
        "transaction": args.transaction,
        "view": args.view,
        "submode": args.submode,
        "profile": args.profile,
        "phase": args.phase,
        "domain": args.domain,
        "operation": args.operation,
    }
    if view_config is None:
        errors.append(error("invalid_view", f"不支持的业务视图: {args.view}", field="view"))
        return None, selection

    allowed_domains = view_config.get("allowed_domains", [])
    if args.domain not in allowed_domains:
        errors.append(error("invalid_domain", f"视图 {args.view} 不支持领域 {args.domain}；合法值为 {allowed_domains}", field="domain"))

    candidates = [route for route in view_config.get("routes", []) if route.get("submode") == args.submode]
    if not candidates:
        valid_submodes = unique([str(route.get("submode")) for route in view_config.get("routes", [])])
        errors.append(error("invalid_submode", f"视图 {args.view} 不支持子模式 {args.submode}；合法值为 {valid_submodes}", field="submode"))
        return None, selection

    route = candidates[0]
    profiles = [str(value) for value in route.get("profiles", [])]
    phases = [str(value) for value in route.get("phases", [])]
    profile = args.profile
    phase = args.phase
    if profile is None:
        profile = route.get("default_profile")
    if profile is None and len(profiles) == 1:
        profile = profiles[0]
    if profile is None:
        errors.append(error("profile_required", f"子模式 {args.submode} 必须明文选择 profile；合法值为 {profiles}", field="profile"))
    elif profile not in profiles:
        errors.append(error("invalid_profile", f"子模式 {args.submode} 不支持 profile {profile}；合法值为 {profiles}", field="profile"))

    if phase is None:
        phase = route.get("default_phase")
    if phase is None and len(phases) == 1:
        phase = phases[0]
    if phase is None:
        errors.append(error("phase_required", f"子模式 {args.submode} 必须明文选择 phase；合法值为 {phases}", field="phase"))
    elif phase not in phases:
        errors.append(error("invalid_phase", f"子模式 {args.submode} 不支持 phase {phase}；合法值为 {phases}", field="phase"))

    selection.update({"profile": profile, "phase": phase})
    return route, selection


def check_transaction(transaction_config: dict[str, Any] | None, args: argparse.Namespace, case: dict[str, Any] | None, errors: list[dict[str, str]]) -> None:
    if transaction_config is None:
        errors.append(error("invalid_transaction", f"不支持的事务模式: {args.transaction}", field="transaction"))
        return
    if args.view not in transaction_config.get("allowed_views", []):
        errors.append(error("transaction_view_not_allowed", f"事务 {args.transaction} 不允许业务视图 {args.view}", field="view"))
    exists = case is not None
    if transaction_config.get("case_required") and not exists:
        errors.append(error("missing_case", f"事务 {args.transaction} 要求主案件 JSON 已存在", field="case"))
    if transaction_config.get("case_must_be_absent") and exists:
        errors.append(error("existing_case", "bootstrap_import 只能用于尚不存在的主案件 JSON；请改选 reimport_material 或 case_json_only", field="case"))
    if transaction_config.get("materials_required") and not args.materials_listed:
        errors.append(error("materials_not_listed", f"事务 {args.transaction} 必须先明文列出外部材料", field="materials_listed"))
    if transaction_config.get("external_read") == "forbidden" and args.external_requested:
        errors.append(error("external_read_forbidden", f"事务 {args.transaction} 禁止读取未导入主 JSON 的外部材料；请保持 JSON-only 或改选 reimport_material", field="external_requested"))


def check_case_domain(case: dict[str, Any] | None, args: argparse.Namespace, errors: list[dict[str, str]]) -> None:
    if case is None:
        return
    case_info = case.get("case", {})
    case_domain = case_info.get("technical_domain") if isinstance(case_info, dict) else None
    if case_domain and case_domain != "pending" and args.domain != "all" and case_domain != args.domain:
        errors.append(error("case_domain_mismatch", f"案件 JSON 的 technical_domain 为 {case_domain}，与用户选择的 domain {args.domain} 不一致", field="domain"))


ROUTE_CONFIRMATION_FIELDS = ("transaction", "view", "submode", "profile", "phase", "domain")
RECONFIRMATION_CODES = {
    "route_confirmation_required",
    "route_confirmation_not_confirmed",
    "route_confirmation_id_missing",
    "route_confirmation_revision_mismatch",
    "route_confirmation_route_mismatch",
}


def validate_stored_route_confirmation(case: dict[str, Any] | None, selection: dict[str, Any], errors: list[dict[str, str]], warnings: list[str]) -> dict[str, Any]:
    """Validate the persisted control gate; CLI flags are intentionally ignored."""
    result: dict[str, Any] = {
        "status": "deferred" if case is None else "required",
        "confirmation_id": None,
        "base_revision": None,
        "fatal": False,
    }
    if case is None:
        warnings.append("bootstrap_import 尚未创建 case.json；导入完成后必须重新写入并验证 control.route_confirmation")
        return result

    control = case.get("control")
    current_revision = control.get("current_revision") if isinstance(control, dict) else None
    if isinstance(current_revision, int) and current_revision >= 0:
        result["base_revision"] = current_revision
    stored = control.get("route_confirmation") if isinstance(control, dict) else None
    if stored is None:
        errors.append(error("route_confirmation_required", "已有案件必须提供 control.route_confirmation；--confirmation-status 不能替代持久化确认", field="/control/route_confirmation"))
        return result
    if not isinstance(stored, dict):
        errors.append(error("route_confirmation_required", "control.route_confirmation 必须是对象；请由总控重新写入确认", field="/control/route_confirmation"))
        return result

    confirmation_id = stored.get("confirmation_id")
    if isinstance(confirmation_id, str) and confirmation_id.strip():
        result["confirmation_id"] = confirmation_id
    else:
        errors.append(error("route_confirmation_id_missing", "control.route_confirmation.confirmation_id 必须为非空字符串", field="/control/route_confirmation/confirmation_id"))

    if stored.get("status") != "confirmed":
        errors.append(error("route_confirmation_not_confirmed", "control.route_confirmation.status 必须为 confirmed；CLI confirmation-status 不能绕过", field="/control/route_confirmation/status"))

    case_id = case.get("case", {}).get("case_id") if isinstance(case.get("case"), dict) else None
    stored_case_id = stored.get("case_id")
    if stored_case_id is not None and stored_case_id != case_id:
        errors.append(error("route_confirmation_case_mismatch", f"route_confirmation.case_id={stored_case_id!r} 与案件 case.case_id={case_id!r} 不一致", field="/control/route_confirmation/case_id"))
        result["fatal"] = True
    elif stored_case_id is None:
        errors.append(error("route_confirmation_required", "control.route_confirmation.case_id 缺失，无法绑定当前案件", field="/control/route_confirmation/case_id"))

    confirmed_revision = stored.get("confirmed_revision")
    if not isinstance(confirmed_revision, int) or result["base_revision"] is None or confirmed_revision != result["base_revision"]:
        errors.append(error("route_confirmation_revision_mismatch", f"route_confirmation.confirmed_revision={confirmed_revision!r} 必须等于 control.current_revision={result['base_revision']!r}", field="/control/route_confirmation/confirmed_revision"))

    selected_route = stored.get("selected_route")
    expected_route = {field: selection.get(field) for field in ROUTE_CONFIRMATION_FIELDS}
    route_mismatch = not isinstance(selected_route, dict)
    if isinstance(selected_route, dict):
        # route_scope() from the confirmation gate keeps the status-only
        # marker for D, although it is not a user-selectable route field.
        # Permit that one derived marker only for audit.status; every other
        # extra or missing key makes the persisted binding non-canonical.
        allowed_extra = {"status_only"} if (
            selection.get("view") == "audit" and selection.get("submode") == "status"
        ) else set()
        actual_keys = set(selected_route)
        expected_keys = set(ROUTE_CONFIRMATION_FIELDS)
        unexpected_keys = actual_keys - expected_keys - allowed_extra
        missing_keys = expected_keys - actual_keys
        invalid_status_marker = "status_only" in actual_keys and selected_route.get("status_only") is not True
        route_mismatch = bool(unexpected_keys or missing_keys or invalid_status_marker)
        route_mismatch = route_mismatch or any(
            selected_route.get(field) != expected_route[field]
            for field in ROUTE_CONFIRMATION_FIELDS
        )
    if route_mismatch:
        errors.append(error("route_confirmation_route_mismatch", f"route_confirmation.selected_route 必须精确匹配本次 canonical route: {expected_route}", field="/control/route_confirmation/selected_route"))
    gate_codes = {item["code"] for item in errors} & (RECONFIRMATION_CODES | {"route_confirmation_case_mismatch"})
    if not result["fatal"] and not gate_codes:
        result["status"] = "valid"
    elif result["fatal"]:
        result["status"] = "blocked"
    return result


def collect_requirements(route: dict[str, Any] | None, selection: dict[str, Any], case: dict[str, Any] | None, transaction: str, errors: list[dict[str, str]], warnings: list[str]) -> dict[str, Any]:
    preconditions: dict[str, Any] = {
        "status": "not_checked",
        "required_any": [],
        "required_all": [],
        "required_any_groups": [],
        "missing_pointers": [],
        "deferred": False,
    }
    if route is None:
        return preconditions

    required_any = list(route.get("required_any", []))
    required_all = list(route.get("required_all", []))
    required_any_groups = [list(group) for group in route.get("required_any_groups", [])]
    phase_requirements = route.get("phase_requirements", {}).get(selection.get("phase"), {})
    required_any.extend(phase_requirements.get("required_any", []))
    required_all.extend(phase_requirements.get("required_all", []))
    required_any_groups.extend([list(group) for group in phase_requirements.get("required_any_groups", [])])
    preconditions.update({
        "required_any": unique([str(pointer) for pointer in required_any]),
        "required_all": unique([str(pointer) for pointer in required_all]),
        "required_any_groups": [[str(pointer) for pointer in group] for group in required_any_groups],
    })

    if case is None and transaction == "bootstrap_import":
        preconditions["status"] = "deferred"
        preconditions["deferred"] = True
        warnings.append("bootstrap_import 尚未创建 case.json；业务视图前置输入将在导入完成后重新检查")
        return preconditions
    if case is None:
        return preconditions

    missing: list[str] = []
    if required_any and not any(is_present(case, pointer) for pointer in required_any):
        missing.extend(required_any)
    for pointer in required_all:
        if not is_present(case, pointer):
            missing.append(pointer)
    for group in required_any_groups:
        if group and not any(is_present(case, pointer) for pointer in group):
            missing.extend(group)
    preconditions["missing_pointers"] = unique(missing)
    if missing:
        preconditions["status"] = "missing"
        errors.append(error("missing_prerequisite", f"路由 {selection['view']}.{selection['submode']} 缺少前置输入，请补充或改选事务/模式: {unique(missing)}", field="preconditions"))
    else:
        preconditions["status"] = "satisfied"
    return preconditions


def resolve_group_names(raw_groups: list[Any], selection: dict[str, Any], registry: dict[str, Any], errors: list[dict[str, str]], field: str) -> list[str]:
    groups: list[str] = []
    for raw_group in raw_groups:
        try:
            group = render(str(raw_group), selection)
        except ValueError as exc:
            errors.append(error("invalid_rule_group_template", str(exc), field=field))
            continue
        groups.append(group)
        if group not in registry.get("groups", {}):
            errors.append(error("unknown_rule_group", f"规则注册表没有定义 rule group: {group}", field=field))
    return unique(groups)


def files_for_groups(groups: list[str], registry: dict[str, Any], errors: list[dict[str, str]], field: str) -> list[str]:
    files: list[str] = []
    for group in groups:
        files.extend([str(path).replace("\\", "/") for path in registry.get("groups", {}).get(group, [])])
    files = unique(files)
    for relative in files:
        if not (PACKAGE_ROOT / relative).is_file():
            errors.append(error("missing_rule_file", f"路由引用的规则文件不存在: {relative}", field=field))
    return files


def resolve_rule_files(route: dict[str, Any] | None, selection: dict[str, Any], registry: dict[str, Any], errors: list[dict[str, str]]) -> tuple[list[str], list[str]]:
    if route is None:
        return [], []
    groups = resolve_group_names(list(route.get("rule_groups", [])), selection, registry, errors, "rule_files")
    files = files_for_groups(groups, registry, errors, "rule_files")
    if len(files) > BASE_RULE_FILE_LIMIT:
        errors.append(error("base_rule_file_budget_exceeded", f"RoutePlan 基础 rule_files 必须不超过 {BASE_RULE_FILE_LIMIT} 个，当前为 {len(files)} 个: {files}", field="rule_files"))
    return files, groups


def trigger_matches(trigger: Any, selection: dict[str, Any]) -> bool:
    if not isinstance(trigger, dict):
        return False
    if "all" in trigger:
        items = trigger.get("all")
        return isinstance(items, list) and all(trigger_matches(item, selection) for item in items)
    if "any" in trigger:
        items = trigger.get("any")
        return isinstance(items, list) and any(trigger_matches(item, selection) for item in items)
    recognized = False
    for key, expected in trigger.items():
        if key.endswith("_in"):
            field = key[:-3]
            recognized = True
            allowed = expected if isinstance(expected, list) else [expected]
            if selection.get(field) not in allowed:
                return False
        elif key.endswith("_equals"):
            field = key[:-7]
            recognized = True
            if selection.get(field) != expected:
                return False
        else:
            return False
    return recognized


def resolve_conditional_rules(route: dict[str, Any] | None, selection: dict[str, Any], registry: dict[str, Any], errors: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    descriptors: list[dict[str, Any]] = []
    groups_output: list[dict[str, Any]] = []
    active_files: list[str] = []
    if route is None:
        return groups_output, descriptors, active_files
    # conditional_rule_files is the canonical machine-readable route
    # field. conditional_rule_groups remains a read-only compatibility
    # alias for older source tables during migration.
    entries = route.get("conditional_rule_files")
    if entries is None:
        entries = route.get("conditional_rule_groups", [])
    if not isinstance(entries, list):
        errors.append(error("invalid_conditional_rule_groups", "conditional_rule_groups 必须是数组", field="conditional_rule_groups"))
        return groups_output, descriptors, active_files
    seen_ids: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(error("invalid_conditional_rule_group", f"条件规则组第 {index} 项必须是对象", field="conditional_rule_groups"))
            continue
        identifier = str(entry.get("id", f"conditional-{index + 1}"))
        if identifier in seen_ids:
            errors.append(error("duplicate_conditional_rule_group", f"条件规则组 ID 重复: {identifier}", field="conditional_rule_groups"))
            continue
        seen_ids.add(identifier)
        trigger = entry.get("trigger", {})
        reason = str(entry.get("reason", ""))
        raw_groups = entry.get("rule_groups", [])
        if raw_groups is None:
            raw_groups = []
        if not isinstance(raw_groups, list):
            errors.append(error("invalid_conditional_rule_groups", f"条件规则组 {identifier} 的 rule_groups 必须是数组", field="conditional_rule_files"))
            raw_groups = []
        groups = resolve_group_names(list(raw_groups), selection, registry, errors, "conditional_rule_files")
        configured_files = entry.get("files")
        if configured_files is not None:
            if not isinstance(configured_files, list):
                errors.append(error("invalid_conditional_rule_files", f"条件规则组 {identifier} 的 files 必须是数组", field="conditional_rule_files"))
                files = []
            else:
                files = unique([str(path).replace("\\", "/") for path in configured_files])
                for relative in files:
                    if not (PACKAGE_ROOT / relative).is_file():
                        errors.append(error("missing_rule_file", f"条件规则引用的规则文件不存在: {relative}", field="conditional_rule_files"))
        else:
            files = files_for_groups(groups, registry, errors, "conditional_rule_files")
        active = trigger_matches(trigger, selection)
        group_descriptor = {"id": identifier, "trigger": trigger, "reason": reason, "rule_groups": groups, "active": active}
        file_descriptor = {"id": identifier, "trigger": trigger, "reason": reason, "rule_groups": groups, "files": files, "active": active}
        groups_output.append(group_descriptor)
        descriptors.append(file_descriptor)
        if active:
            active_files.extend(files)
    return groups_output, descriptors, unique(active_files)


def resolve_context(route: dict[str, Any] | None, selection: dict[str, Any], profiles_config: dict[str, Any], errors: list[dict[str, str]]) -> tuple[str | None, list[str], dict[str, Any]]:
    if route is None:
        return None, [], {}
    try:
        profile_name = render(str(route.get("read_profile", "")), selection)
    except ValueError as exc:
        errors.append(error("invalid_read_profile_template", str(exc)))
        return None, [], {}
    profile = profiles_config.get("profiles", {}).get(profile_name)
    if not isinstance(profile, dict):
        errors.append(error("unknown_read_profile", f"切片配置未定义 read profile: {profile_name}", field="read_profile"))
        return profile_name, [], {}
    pointers = [str(pointer) for pointer in profile.get("pointers", [])]
    context_budget = dict(profiles_config.get("defaults", {}))
    context_budget.update(profile.get("context_budget", {}))
    required_budget = {"max_output_chars", "max_items", "evidence_hops", "max_excerpt_chars_per_source", "exclude_fields"}
    missing_budget = sorted(required_budget - set(context_budget))
    if missing_budget:
        errors.append(error("invalid_context_budget", f"read profile {profile_name} 缺少预算字段: {missing_budget}", field="context_budget"))
    return profile_name, unique(pointers), context_budget


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[str] = []
    try:
        transactions_config = load_json(TRANSACTION_PATH)
        registry = load_json(REGISTRY_PATH)
        profiles_config = load_json(SLICE_PROFILE_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(error("routing_configuration_error", f"无法加载路由配置: {exc}"))
        transactions_config = {"transactions": {}}
        registry = {"groups": {}}
        profiles_config = {"profiles": {}}

    case, case_errors = load_case(Path(args.case))
    errors.extend(case_errors)
    transaction_config = transactions_config.get("transactions", {}).get(args.transaction)
    check_transaction(transaction_config, args, case, errors)
    view_config: dict[str, Any] | None = None
    view_path = VIEW_ROOT / f"{args.view}.json"
    if view_path.is_file():
        try:
            view_config = load_json(view_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(error("routing_configuration_error", f"无法加载视图路由配置 {args.view}: {exc}"))
    else:
        errors.append(error("invalid_view", f"未找到视图路由配置: {args.view}", field="view"))

    route, selection = select_route(view_config, args, errors)
    check_case_domain(case, args, errors)
    preconditions = collect_requirements(route, selection, case, args.transaction, errors, warnings)
    rule_files, base_groups = resolve_rule_files(route, selection, registry, errors)
    conditional_rule_groups, conditional_rule_files, active_conditional_rule_files = resolve_conditional_rules(route, selection, registry, errors)
    conditional_paths = {
        relative
        for item in conditional_rule_files
        for relative in item.get("files", [])
        if isinstance(relative, str)
    }
    overlap = sorted(set(rule_files) & conditional_paths)
    if overlap:
        errors.append(error("conditional_rule_merged_into_base", f"条件规则文件不得进入基础 rule_files: {overlap}", field="rule_files"))
    read_profile, pointers, context_budget = resolve_context(route, selection, profiles_config, errors)
    confirmation_gate = validate_stored_route_confirmation(case, selection, errors, warnings)
    if args.confirmation_status != "required":
        warnings.append("--confirmation-status 已弃用；是否 ready 只由 control.route_confirmation 的有效绑定决定")

    ai = {
        "transaction": args.ai_transaction,
        "view": args.ai_view,
        "submode": args.ai_submode,
        "profile": args.ai_profile,
        "phase": args.ai_phase,
        "domain": args.ai_domain,
        "operation": args.ai_operation,
    }
    for field in ("transaction", "view", "submode", "profile", "phase", "domain", "operation"):
        suggestion = ai[field]
        selected = selection.get(field)
        if suggestion is not None and selected is not None and suggestion != selected:
            errors.append(error("ai_user_selection_mismatch", f"用户明文选择的 {field} 为 {selected}，AI 仅作候选判断为 {suggestion}；不得静默替用户改选", "advisory", field))
    if any(item["code"] == "ai_user_selection_mismatch" for item in errors):
        warnings.append("AI 判断仅作为候选；请由用户明确选择保持当前路由或重新提交其他路由")
    inactive_count = sum(1 for item in conditional_rule_files if not item["active"])
    if inactive_count:
        warnings.append(f"{inactive_count} 个条件规则组尚未触发；只有其 trigger 满足时，总控才能追加对应文件")

    route_id = route_id_fallback(args.view, args.submode)
    if route is not None and selection.get("profile") is not None and selection.get("phase") is not None:
        try:
            route_id = render(str(route["route_id_template"]), selection)
        except (KeyError, ValueError) as exc:
            errors.append(error("invalid_route_id_template", f"无法生成 route_id: {exc}"))

    if transaction_config and transaction_config.get("write_prefix") == "view_owned":
        write_prefix = route.get("write_prefix") if route else None
    elif transaction_config:
        write_prefix = transaction_config.get("write_prefix")
    else:
        write_prefix = None

    hard_errors = [
        item for item in errors
        if item.get("severity") == "hard" and item.get("code") not in RECONFIRMATION_CODES
    ]
    advisory_errors = [item for item in errors if item.get("severity") == "advisory"]
    if hard_errors or confirmation_gate["status"] == "blocked":
        status = "blocked"
        confirmation_status = "blocked"
    elif advisory_errors:
        status = "challenge_required"
        confirmation_status = "challenge_required"
    elif confirmation_gate["status"] != "valid":
        status = "confirmation_required"
        confirmation_status = "required"
    else:
        status = "ready"
        confirmation_status = "confirmed"

    if status == "confirmation_required":
        warnings.append("RoutePlan 只能在用户明文确认完整事务、视图、子模式、profile、phase、domain 和 operation 后执行")
    execution_allowed = status == "ready"
    return {
        "schema_version": "route-plan-1.0",
        "status": status,
        "route_id": route_id,
        "transaction": args.transaction,
        "view": args.view,
        "submode": args.submode,
        "profile": selection.get("profile"),
        "phase": selection.get("phase"),
        "domain": args.domain,
        "operation": selection.get("operation"),
        "selection": selection,
        "confirmation_id": confirmation_gate["confirmation_id"],
        "base_revision": confirmation_gate["base_revision"],
        "confirmation": {
            "required": True,
            "status": confirmation_status,
            "challenge_required": bool(advisory_errors),
            "execution_allowed": execution_allowed,
            "ai_is_advisory": True,
            "confirmation_id": confirmation_gate["confirmation_id"],
            "base_revision": confirmation_gate["base_revision"],
            "deferred": confirmation_gate["status"] == "deferred",
            "confirmation_source": "stored_case_route_confirmation" if status == "ready" else "awaiting_control_route_confirmation",
        },
        "read_profile": read_profile,
        "json_pointers": pointers,
        "requested_ids": unique(args.requested_ids),
        "rule_files": rule_files,
        "conditional_rule_groups": conditional_rule_groups,
        "conditional_rule_files": conditional_rule_files,
        "active_conditional_rule_files": active_conditional_rule_files,
        "rule_file_budget": {
            "base_limit": BASE_RULE_FILE_LIMIT,
            "base_count": len(rule_files),
            "active_conditional_count": len(active_conditional_rule_files),
            "conditional_group_count": len(conditional_rule_files),
        },
        "forbidden_rule_groups": unique([str(item) for item in (route or {}).get("forbidden_rule_groups", [])]),
        "write_prefix": write_prefix,
        "validators": unique([str(item) for item in (route or {}).get("validators", [])]),
        "context_budget": context_budget,
        "preconditions": preconditions,
        "errors": errors,
        "warnings": unique(warnings),
        "ai_routing_assessment": ai,
        "ai_suggestion_applied": False,
        "routing_basis": "user_selection_only",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="根据明文用户选择生成统一案件工作流 RoutePlan")
    parser.add_argument("--case", required=True, help="主案件 JSON 路径；bootstrap_import 时可以是尚不存在的路径")
    parser.add_argument("--transaction", required=True, help="四类事务之一")
    parser.add_argument("--view", required=True, help="mbse/search/drafting/oa/invalidity/audit")
    parser.add_argument("--submode", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--phase")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--operation", help="当前明确选择的具体操作；用于触发条件规则组")
    parser.add_argument("--id", dest="requested_ids", action="append", default=[])
    parser.add_argument("--confirmation-status", choices=["required", "confirmed"], default="required")
    parser.add_argument("--materials-listed", action="store_true")
    parser.add_argument("--external-requested", action="store_true")
    parser.add_argument("--ai-transaction")
    parser.add_argument("--ai-view")
    parser.add_argument("--ai-submode")
    parser.add_argument("--ai-profile")
    parser.add_argument("--ai-phase")
    parser.add_argument("--ai-domain")
    parser.add_argument("--ai-operation")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_plan(args)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if plan["status"] == "ready":
        return EXIT_READY
    if plan["status"] == "confirmation_required":
        return EXIT_CONFIRMATION_REQUIRED
    if plan["status"] == "challenge_required":
        return EXIT_CHALLENGE_REQUIRED
    return EXIT_BLOCKED


if __name__ == "__main__":
    raise SystemExit(main())
