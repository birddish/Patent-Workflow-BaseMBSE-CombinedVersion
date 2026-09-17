"""Validate the machine route contract against the mode gate and RoutePlan.

This validator is intentionally read-only and dependency-free.  It treats the
JSON route tables as the executable contract, expands every declared route
combination, and evaluates the same selection through ``confirm_case_mode.py``
and ``plan_case_route.py``.  A route is valid only when both implementations
accept the exact same spelling of view, submode, profile, and phase.

The current source package contains a few known generations of route naming
(for example ``phase_03`` versus ``stage3``).  Those are reported as explicit
failures; this script does not silently normalize them because doing so would
hide a production routing bug.

Usage::

    python validate_route_contract.py
    python validate_route_contract.py --package-root <skill-package>

Exit status is 0 only when no contract error is found.  Output is JSON so the
validator can be consumed by the workbench tests or another release gate.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable


VIEW_NAMES = ("mbse", "search", "drafting", "oa", "invalidity", "audit")
ROUTER_NAMES = ("mbse", "search", "drafting", "oa", "invalidity")
REQUIRED_ROUTING_FILES = (
    "transactions.json",
    "rule-registry.json",
    "slice-profiles.json",
)
REQUIRED_PLAN_FIELDS = {
    "schema_version",
    "status",
    "route_id",
    "transaction",
    "view",
    "submode",
    "profile",
    "phase",
    "domain",
    "operation",
    "selection",
    "confirmation",
    "confirmation_id",
    "base_revision",
    "read_profile",
    "json_pointers",
    "requested_ids",
    "rule_files",
    "conditional_rule_groups",
    "conditional_rule_files",
    "active_conditional_rule_files",
    "forbidden_rule_groups",
    "rule_file_budget",
    "write_prefix",
    "validators",
    "context_budget",
    "preconditions",
    "errors",
    "warnings",
    "ai_routing_assessment",
    "ai_suggestion_applied",
    "routing_basis",
}
REQUIRED_BUDGET_FIELDS = {
    "max_output_chars",
    "max_items",
    "evidence_hops",
    "max_excerpt_chars_per_source",
    "exclude_fields",
}
REQUIRED_PROFILE_FIELDS = {"pointers", "context_budget"}
REQUIRED_TRANSACTION_NAMES = {
    "bootstrap_import",
    "case_json_only",
    "reimport_material",
    "export_from_json",
}


def _load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{path}: {exc}"


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "message": message}
    result.update(details)
    return result


def _deduplicate_issues(issues: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in issues:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _module_from_path(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载脚本模块: {path}")
    module = importlib.util.module_from_spec(spec)
    # The scripts use local compatibility helpers such as _case_utils.
    script_dir = str(path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec.loader.exec_module(module)
    return module


def _json_pointer_is_legal(pointer: Any) -> bool:
    """Check RFC 6901 spelling without resolving it against a case."""

    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return False
    if pointer == "/":
        return True
    for token in pointer[1:].split("/"):
        if re.search(r"~(?![01])", token):
            return False
    return True


def _render_template(template: Any, selection: dict[str, Any]) -> str | None:
    if not isinstance(template, str):
        return None
    try:
        return template.format(**selection)
    except (KeyError, IndexError, ValueError):
        return None


def _case_fixture(path: Path, confirmed_selection: dict[str, Any] | None = None) -> None:
    """Create an in-memory-equivalent rich case for route evaluation.

    The fixture is only a temporary input to the two existing read-only
    route scripts.  Every declared precondition is populated so that a route
    failure means a contract mismatch, not an unrelated missing-data gate.
    """

    def one(identifier: str) -> list[dict[str, Any]]:
        return [{"id": identifier, "status": "confirmed"}]

    case: dict[str, Any] = {
        "schema_version": "case-json-1.0",
        "case": {
            "case_id": "CASE-ROUTE-CONTRACT-001",
            "technical_domain": "electronics",
        },
        "runtime_policy": {
            "default_transaction": "case_json_only",
            "external_read_requires": "bootstrap_or_explicit_reimport",
        },
        "source_materials": {
            "documents": one("DOC-SOURCE-001"),
            "evidence": one("EV-001"),
            "search_results": one("SR-001"),
            "import_batches": one("BATCH-001"),
            "raw_artifacts": [],
        },
        "normalized": {
            "technical_facts": one("TF-001"),
            "entities": one("ENT-001"),
            "documents": one("DOC-001"),
            "claims": one("CLM-001"),
            "issues": one("ISS-001"),
            "product_specifications": one("PRODUCT-001"),
            "jurisdiction_scope": one("JUR-001"),
            "patent_metadata": one("META-001"),
            "landscape_scope": one("LAND-001"),
        },
        "derived": {
            "mbse": {"model": one("MBSE-001"), "chains": one("CHAIN-001")},
            "search": {"results": one("SEARCH-001"), "comparisons": one("COMP-001")},
            "drafting": {
                "claims": one("CLM-D-001"),
                "claim_paths": one("PATH-001"),
                "stage_status": one("STAGE-001"),
            },
            "oa": {
                "issue_registry": one("OA-ISSUE-001"),
                "analysis_snapshots": one("SNAP-001"),
                "response_versions": one("RESP-001"),
                "recalculation_gate": one("GATE-001"),
            },
            "invalidity": {
                "issue_registry": one("INV-ISSUE-001"),
                "traceability": one("INV-TRACE-001"),
                "statement_versions": one("INV-STATEMENT-001"),
            },
            "audit": {"findings": one("AUDIT-001")},
        },
        "control": {
            "current_revision": 12,
            "navigation": {"active_view": "audit"},
            "summary": {"status": "ready"},
            "open_gates": [],
            "pending_questions": [],
            "conflicts": [],
            "transactions": [],
            "access_log": [],
            "change_log": [],
            "dependency_index": {"CHAIN-001": []},
        },
    }
    if confirmed_selection is not None:
        confirmation_scope = {
            field: confirmed_selection.get(field)
            for field in ("transaction", "view", "submode", "profile", "phase", "domain")
        }
        case["control"]["route_confirmation"] = {
            "confirmation_id": "CONF-ROUTE-CONTRACT-001",
            "case_id": case["case"]["case_id"],
            "status": "confirmed",
            "confirmed_revision": case["control"]["current_revision"],
            "selected_route": confirmation_scope,
            "confirmed_by": "validator",
        }
    path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _namespace(
    case: Path,
    selection: dict[str, Any],
    *,
    confirmation_status: str = "confirmed",
    external_requested: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        case=str(case),
        transaction=selection.get("transaction", "case_json_only"),
        view=selection.get("view", ""),
        submode=selection.get("submode", ""),
        profile=selection.get("profile"),
        phase=selection.get("phase"),
        domain=selection.get("domain", "electronics"),
        operation=selection.get("operation"),
        requested_ids=[],
        confirmation_status=confirmation_status,
        materials_listed=bool(selection.get("materials_listed", False)),
        external_requested=external_requested,
        ai_transaction=None,
        ai_view=None,
        ai_submode=None,
        ai_profile=None,
        ai_phase=None,
        ai_domain=None,
        ai_operation=None,
        status_only=bool(selection.get("status_only", False)),
        expected_revision=None,
        challenge_id="",
        advisory_override=False,
        override_reason="",
        check_confirmation=False,
        write_confirmation=False,
        actor="validator",
    )


def _route_combinations(view_configs: dict[str, Any]) -> list[dict[str, Any]]:
    combinations: list[dict[str, Any]] = []
    for view in VIEW_NAMES:
        config = view_configs.get(view)
        if not isinstance(config, dict):
            continue
        for route_index, route in enumerate(config.get("routes", [])):
            if not isinstance(route, dict):
                continue
            raw_profiles = route.get("profiles")
            raw_phases = route.get("phases")
            profiles = list(raw_profiles) if isinstance(raw_profiles, list) else [route.get("default_profile")]
            phases = list(raw_phases) if isinstance(raw_phases, list) else [route.get("default_phase")]
            if not profiles:
                profiles = [None]
            if not phases:
                phases = [None]
            for profile in profiles:
                for phase in phases:
                    selection = {
                        "transaction": "case_json_only",
                        "view": view,
                        "submode": route.get("submode"),
                        "profile": profile,
                        "phase": phase,
                        "domain": "electronics",
                        "operation": route.get("default_operation"),
                    }
                    route_id = _render_template(route.get("route_id_template"), selection)
                    if route_id is None:
                        route_id = f"{view}.route-{route_index}"
                    combinations.append(
                        {
                            "view": view,
                            "route_index": route_index,
                            "route": route,
                            "selection": selection,
                            "route_id": route_id,
                        }
                    )
    return combinations


def _check_schema_definition(schema: Any, issues: list[dict[str, Any]]) -> None:
    if not isinstance(schema, dict):
        issues.append(_issue("invalid_route_plan_schema", "route-plan.schema.json 顶层不是对象"))
        return
    required = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required, list) or not isinstance(properties, dict):
        issues.append(_issue("invalid_route_plan_schema", "RoutePlan Schema 缺少 required/properties"))
        return
    missing = sorted(REQUIRED_PLAN_FIELDS - set(required))
    if missing:
        issues.append(_issue("route_plan_schema_missing_fields", f"RoutePlan Schema 缺少字段: {missing}"))
    missing_properties = sorted(REQUIRED_PLAN_FIELDS - set(properties))
    if missing_properties:
        issues.append(_issue("route_plan_schema_missing_properties", f"RoutePlan Schema 缺少属性定义: {missing_properties}"))


def _check_plan_shape(plan: Any, schema: dict[str, Any], *, route_id: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not isinstance(plan, dict):
        return [_issue("route_plan_output_not_object", "RoutePlan 输出不是对象", route_id=route_id)]
    required = set(schema.get("required", []))
    missing = sorted(required - set(plan))
    if missing:
        issues.append(_issue("route_plan_output_missing_fields", f"RoutePlan 输出缺少字段: {missing}", route_id=route_id))
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        extras = sorted(set(plan) - set(properties))
        if extras:
            issues.append(_issue("route_plan_output_extra_fields", f"RoutePlan 输出出现未声明字段: {extras}", route_id=route_id))
    if plan.get("schema_version") != "route-plan-1.0":
        issues.append(_issue("route_plan_schema_version_drift", f"RoutePlan schema_version 异常: {plan.get('schema_version')!r}", route_id=route_id))
    if plan.get("status") not in {"ready", "confirmation_required", "challenge_required", "blocked"}:
        issues.append(_issue("route_plan_status_invalid", f"RoutePlan status 异常: {plan.get('status')!r}", route_id=route_id))
    if plan.get("ai_suggestion_applied") is not False or plan.get("routing_basis") != "user_selection_only":
        issues.append(_issue("route_plan_ai_override_drift", "RoutePlan 不能自动采用 AI 路由建议", route_id=route_id))
    selection = plan.get("selection")
    if not isinstance(selection, dict):
        issues.append(_issue("route_plan_selection_invalid", "RoutePlan selection 不是对象", route_id=route_id))
    elif any(key not in selection for key in ("transaction", "view", "submode", "profile", "phase", "domain", "operation")):
        issues.append(_issue("route_plan_selection_incomplete", "RoutePlan selection 缺少完整路由字段", route_id=route_id))
    confirmation = plan.get("confirmation")
    if not isinstance(confirmation, dict):
        issues.append(_issue("route_plan_confirmation_invalid", "RoutePlan confirmation 不是对象", route_id=route_id))
    else:
        if plan.get("status") == "ready" and (
            confirmation.get("status") != "confirmed"
            or confirmation.get("execution_allowed") is not True
            or not isinstance(plan.get("confirmation_id"), str)
            or not plan.get("confirmation_id")
        ):
            issues.append(_issue("route_plan_ready_without_confirmation", "ready RoutePlan 必须绑定非空 confirmation_id、confirmed 状态并允许执行", route_id=route_id))
        if plan.get("status") != "ready" and confirmation.get("execution_allowed") is True:
            issues.append(_issue("route_plan_confirmation_bypass", "非 ready RoutePlan 不得允许执行", route_id=route_id))
    budget = plan.get("context_budget")
    if not isinstance(budget, dict) or not REQUIRED_BUDGET_FIELDS.issubset(budget):
        issues.append(_issue("route_plan_context_budget_invalid", "RoutePlan 缺少完整 context_budget", route_id=route_id))
    for field in ("json_pointers", "rule_files", "validators", "requested_ids", "forbidden_rule_groups"):
        if not isinstance(plan.get(field), list):
            issues.append(_issue("route_plan_array_field_invalid", f"RoutePlan {field} 不是数组", route_id=route_id))
    return issues


def _check_routing_config(
    package_root: Path,
    route_configs: dict[str, Any],
    transactions: Any,
    registry: Any,
    profiles: Any,
    schema: Any,
    issues: list[dict[str, Any]],
) -> None:
    if not isinstance(transactions, dict) or not isinstance(transactions.get("transactions"), dict):
        issues.append(_issue("invalid_transactions_config", "transactions.json 缺少 transactions 对象"))
        transaction_map: dict[str, Any] = {}
    else:
        transaction_map = transactions["transactions"]
    missing_transactions = sorted(REQUIRED_TRANSACTION_NAMES - set(transaction_map))
    if missing_transactions:
        issues.append(_issue("transaction_registry_incomplete", f"四类事务缺失: {missing_transactions}"))
    if not isinstance(registry, dict) or not isinstance(registry.get("groups"), dict):
        issues.append(_issue("invalid_rule_registry", "rule-registry.json 缺少 groups 对象"))
        group_map: dict[str, Any] = {}
    else:
        group_map = registry["groups"]
    if not isinstance(profiles, dict) or not isinstance(profiles.get("profiles"), dict):
        issues.append(_issue("invalid_slice_profiles", "slice-profiles.json 缺少 profiles 对象"))
        profile_map: dict[str, Any] = {}
    else:
        profile_map = profiles["profiles"]

    if isinstance(profiles, dict):
        defaults = profiles.get("defaults")
        if not isinstance(defaults, dict) or not REQUIRED_BUDGET_FIELDS.issubset(defaults):
            issues.append(_issue("slice_profile_defaults_incomplete", "slice-profiles.json defaults 缺少完整上下文预算"))
    for name, profile in profile_map.items():
        if not isinstance(profile, dict) or not REQUIRED_PROFILE_FIELDS.issubset(profile):
            issues.append(_issue("slice_profile_incomplete", f"slice profile {name} 缺少 pointers/context_budget"))
            continue
        pointers = profile.get("pointers")
        if not isinstance(pointers, list) or not pointers:
            issues.append(_issue("slice_profile_pointers_empty", f"slice profile {name} 没有 pointers"))
        else:
            for pointer in pointers:
                if not _json_pointer_is_legal(pointer):
                    issues.append(_issue("invalid_json_pointer", f"slice profile {name} 的 JSON Pointer 非法: {pointer!r}", profile=name, pointer=pointer))
        budget = profile.get("context_budget")
        if not isinstance(budget, dict) or not REQUIRED_BUDGET_FIELDS.issubset({**(profiles.get("defaults", {}) if isinstance(profiles, dict) else {}), **budget}):
            issues.append(_issue("slice_profile_budget_invalid", f"slice profile {name} 缺少可解析预算字段", profile=name))

    for view in VIEW_NAMES:
        config = route_configs.get(view)
        if not isinstance(config, dict):
            issues.append(_issue("missing_view_route_config", f"缺少视图路由配置: {view}"))
            continue
        if config.get("view") != view:
            issues.append(_issue("view_name_drift", f"{view}.json 的 view 字段为 {config.get('view')!r}"))
        if not isinstance(config.get("routes"), list) or not config.get("routes"):
            issues.append(_issue("view_route_config_empty", f"视图 {view} 没有 routes"))
        for route_index, route in enumerate(config.get("routes", [])):
            if not isinstance(route, dict):
                issues.append(_issue("invalid_view_route", f"视图 {view} route[{route_index}] 不是对象"))
                continue
            selection = {
                "view": view,
                "submode": route.get("submode"),
                "profile": route.get("default_profile") or (route.get("profiles") or [None])[0],
                "phase": route.get("default_phase") or (route.get("phases") or [None])[0],
                "domain": "electronics",
            }
            groups = route.get("rule_groups", [])
            if not isinstance(groups, list):
                issues.append(_issue("rule_group_list_invalid", f"{view} route[{route_index}] rule_groups 不是数组"))
                groups = []
            resolved_groups: list[str] = []
            base_files: list[str] = []
            for raw_group in groups:
                group = _render_template(raw_group, selection)
                if group is None:
                    issues.append(_issue("rule_group_template_invalid", f"{view} route[{route_index}] 无法展开 rule group: {raw_group!r}"))
                    continue
                resolved_groups.append(group)
                if group not in group_map:
                    issues.append(_issue("unknown_rule_group", f"路由引用了未注册 rule group: {group}", view=view, route_index=route_index))
                    casefold_matches = sorted(key for key in group_map if isinstance(key, str) and key.casefold() == group.casefold())
                    if casefold_matches:
                        issues.append(_issue("rule_group_naming_drift", f"rule group 命名大小写漂移: 机器路由使用 {group}，注册表使用 {casefold_matches}", view=view, route_index=route_index, machine_name=group, registry_names=casefold_matches))
                    continue
                paths = group_map[group]
                if not isinstance(paths, list):
                    issues.append(_issue("rule_group_paths_invalid", f"rule group {group} 的文件列表不是数组"))
                    continue
                for relative in paths:
                    if isinstance(relative, str):
                        base_files.append(relative.replace("\\", "/"))
                    if not isinstance(relative, str) or not (package_root / relative).is_file():
                        issues.append(_issue("missing_rule_file", f"rule group {group} 引用的规则文件不存在: {relative!r}", view=view, route_index=route_index, rule_group=group))
            if len(resolved_groups) != len(set(resolved_groups)):
                issues.append(_issue("duplicate_rule_group", f"{view} route[{route_index}] 重复加载 rule group", view=view, route_index=route_index))
            unique_base_files = list(dict.fromkeys(base_files))
            if len(unique_base_files) > 4:
                issues.append(_issue("base_rule_file_budget_exceeded", f"{view} route[{route_index}] 基础规则文件超过 4 个: {unique_base_files}", view=view, route_index=route_index, count=len(unique_base_files)))
            conditional_entries = route.get("conditional_rule_files")
            if conditional_entries is None:
                conditional_entries = route.get("conditional_rule_groups", [])
            if not isinstance(conditional_entries, list):
                issues.append(_issue("conditional_rule_files_invalid", f"{view} route[{route_index}] conditional_rule_files 必须是数组", view=view, route_index=route_index))
                conditional_entries = []
            conditional_ids: set[str] = set()
            for conditional_index, entry in enumerate(conditional_entries):
                if not isinstance(entry, dict):
                    issues.append(_issue("conditional_rule_file_entry_invalid", f"{view} route[{route_index}] 条件规则项不是对象", view=view, route_index=route_index, conditional_index=conditional_index))
                    continue
                identifier = entry.get("id")
                if not isinstance(identifier, str) or not identifier:
                    issues.append(_issue("conditional_rule_file_id_missing", f"{view} route[{route_index}] 条件规则项缺少非空 id", view=view, route_index=route_index, conditional_index=conditional_index))
                elif identifier in conditional_ids:
                    issues.append(_issue("duplicate_conditional_rule_file_id", f"{view} route[{route_index}] 条件规则 id 重复: {identifier}", view=view, route_index=route_index))
                else:
                    conditional_ids.add(identifier)
                if not isinstance(entry.get("trigger"), dict) or not entry.get("trigger"):
                    issues.append(_issue("conditional_rule_file_trigger_invalid", f"{view} route[{route_index}] 条件规则项缺少 trigger", view=view, route_index=route_index, conditional_index=conditional_index))
                if not isinstance(entry.get("reason"), str) or not entry.get("reason"):
                    issues.append(_issue("conditional_rule_file_reason_missing", f"{view} route[{route_index}] 条件规则项缺少 reason", view=view, route_index=route_index, conditional_index=conditional_index))
                conditional_paths: list[str] = []
                raw_conditional_groups = entry.get("rule_groups", [])
                if raw_conditional_groups is not None and not isinstance(raw_conditional_groups, list):
                    issues.append(_issue("conditional_rule_group_list_invalid", f"{view} route[{route_index}] 条件规则项 rule_groups 不是数组", view=view, route_index=route_index, conditional_index=conditional_index))
                    raw_conditional_groups = []
                for raw_group in raw_conditional_groups or []:
                    group = _render_template(raw_group, selection)
                    if group is None or group not in group_map:
                        continue
                    paths = group_map.get(group)
                    if isinstance(paths, list):
                        conditional_paths.extend(str(relative).replace("\\", "/") for relative in paths if isinstance(relative, str))
                direct_paths = entry.get("files")
                if direct_paths is not None:
                    if not isinstance(direct_paths, list):
                        issues.append(_issue("conditional_rule_file_paths_invalid", f"{view} route[{route_index}] 条件规则项 files 不是数组", view=view, route_index=route_index, conditional_index=conditional_index))
                    else:
                        conditional_paths.extend(str(relative).replace("\\", "/") for relative in direct_paths if isinstance(relative, str))
                        for relative in direct_paths:
                            if not isinstance(relative, str) or not (package_root / relative).is_file():
                                issues.append(_issue("missing_conditional_rule_file", f"条件规则文件不存在: {relative!r}", view=view, route_index=route_index, conditional_index=conditional_index))
                overlap = sorted(set(unique_base_files) & set(conditional_paths))
                if overlap:
                    issues.append(_issue("conditional_rule_merged_into_base", f"{view} route[{route_index}] 条件规则文件被并入基础 rule_files: {overlap}", view=view, route_index=route_index, conditional_index=conditional_index))
            read_template = route.get("read_profile")
            read_profile = _render_template(read_template, selection)
            if not read_profile or read_profile not in profile_map:
                issues.append(_issue("missing_slice_profile", f"{view} route[{route_index}] 的 read_profile 不存在: {read_profile!r}", view=view, route_index=route_index))
            validators = route.get("validators", [])
            if isinstance(validators, list):
                for validator in validators:
                    if not isinstance(validator, str) or not (package_root / "scripts" / validator).is_file():
                        issues.append(_issue("missing_route_validator", f"{view} route[{route_index}] 的 validator 不存在: {validator!r}", view=view, route_index=route_index))
    _check_schema_definition(schema, issues)


def _check_router_documents(package_root: Path, route_configs: dict[str, Any], issues: list[dict[str, Any]]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for view in ROUTER_NAMES:
        path = package_root / "references" / "views" / view / "router.md"
        if not path.is_file():
            issues.append(_issue("missing_router_document", f"缺少 {view} router.md", view=view))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            issues.append(_issue("router_document_unreadable", f"无法读取 {path}: {exc}", view=view))
            continue
        texts[view] = text
        markers = {
            "mbse": ("机器规范源为：", "MBSE 只有以下三种 `submode`", "profile=standard", "phase=modeling"),
            "search": ("机器规范源为：", "检索只有以下四种 `submode`", "FTO", "phase=search"),
            "drafting": ("机器规范源为：", "stage1_stage3_claim_core", "profile=controlled", "stage_03"),
            "oa": ("机器规范源为：", "v2.1-oa", "phase_05", "read_profile"),
            "invalidity": ("机器规范源为：", "v2.1-invalidity", "phase_05", "read_profile"),
        }[view]
        for marker in markers:
            if marker not in text:
                issues.append(_issue("router_contract_marker_missing", f"{view}/router.md 缺少合同标记: {marker}", view=view, marker=marker))

        # Every literal reference to an actual markdown resource must resolve.
        for relative in sorted(set(re.findall(r"references/[A-Za-z0-9_./-]+\\.md", text))):
            if "<" in relative or "*" in relative:
                continue
            if not (package_root / relative).is_file():
                issues.append(_issue("router_rule_file_missing", f"{view}/router.md 引用的文件不存在: {relative}", view=view, path=relative))

        config = route_configs.get(view, {})
        routes = config.get("routes", []) if isinstance(config, dict) else []
        # The current router files declare the JSON tables to be authoritative.
        # Check concrete route vocabulary, rather than the English word
        # "operation", which can occur in ordinary prose.
        for route in routes:
            if not isinstance(route, dict):
                continue
            for field in ("submode", "default_profile", "default_phase"):
                value = route.get(field)
                if isinstance(value, str) and value not in text:
                    issues.append(_issue("router_vocabulary_missing", f"{view}/router.md 未出现机器路由 {field}={value}", view=view, field=field, value=value))
            for field in ("profiles", "phases"):
                values = route.get(field)
                if isinstance(values, list):
                    for value in values:
                        if isinstance(value, str) and value not in text:
                            issues.append(_issue("router_vocabulary_missing", f"{view}/router.md 未出现机器路由 {field}={value}", view=view, field=field, value=value))
    return texts
def _check_explicit_naming_drift(
    route_configs: dict[str, Any],
    confirm_module: ModuleType,
    router_texts: dict[str, str],
    issues: list[dict[str, Any]],
) -> None:
    """Report cross-generation spellings instead of silently canonicalizing."""

    search_routes = route_configs.get("search", {}).get("routes", [])
    search_submodes = {route.get("submode") for route in search_routes if isinstance(route, dict)}
    if re.search(r"\|\s*`fto`\s*\|", router_texts.get("search", "")) and "FTO" in search_submodes and "fto" not in search_submodes:
        issues.append(_issue("submode_case_naming_drift", "检索 router 使用 fto，但机器路由使用 FTO；模式门也按 FTO 区分大小写", view="search", router_name="fto", machine_name="FTO"))

    for view, expected_prefix in (("drafting", "stage_"), ("oa", "phase_"), ("invalidity", "phase_")):
        values = {
            str(value)
            for route in route_configs.get(view, {}).get("routes", [])
            if isinstance(route, dict)
            for value in route.get("phases", [])
            if isinstance(value, str)
        }
        bad_values = sorted(value for value in values if value.startswith(expected_prefix))
        canonical_failures: list[str] = []
        for value in bad_values:
            canonical = getattr(confirm_module, "_canonical_phase")(value)
            if canonical != value:
                canonical_failures.append(f"{value}->{canonical}")
        if canonical_failures:
            issues.append(_issue("phase_naming_drift", f"{view} 机器 phase 与模式门 canonical phase 不一致: {canonical_failures}", view=view, values=bad_values))

    # Compare every machine vocabulary with the mode gate's accepted sets.
    accepted_by_view = {
        "mbse": getattr(confirm_module, "MBSE_SUBMODES", set()),
        "search": getattr(confirm_module, "SEARCH_SUBMODES", set()),
        "drafting": getattr(confirm_module, "DRAFTING_SUBMODES", set()),
        "oa": getattr(confirm_module, "OA_SUBMODES", set()),
        "invalidity": getattr(confirm_module, "INVALIDITY_SUBMODES", set()),
        "audit": getattr(confirm_module, "AUDIT_SUBMODES", set()),
    }
    for view, accepted in accepted_by_view.items():
        for route in route_configs.get(view, {}).get("routes", []):
            if not isinstance(route, dict):
                continue
            submode = route.get("submode")
            if submode not in accepted:
                issues.append(_issue("mode_gate_vocabulary_drift", f"机器路由 submode={submode!r} 不在模式门 {view} 合法集合中", view=view, value=submode))

    expected_route_shapes = {
        "mbse": ({"standard"}, {"modeling"}),
        "search": (set(getattr(confirm_module, "SEARCH_PROFILES", set())), {"search"}),
        "drafting": ({"standard", "controlled"}, {f"stage_{number:02d}" for number in range(1, 10)}),
        "oa": ({"v2.1-oa"}, set(getattr(confirm_module, "OA_PHASES", set()))),
        "invalidity": ({"v2.1-invalidity"}, set(getattr(confirm_module, "INVALIDITY_PHASES", set()))),
        "audit": (set(getattr(confirm_module, "AUDIT_PROFILES", set())), {"audit"}),
    }
    for view, (accepted_profiles, accepted_phases) in expected_route_shapes.items():
        for route in route_configs.get(view, {}).get("routes", []):
            if not isinstance(route, dict):
                continue
            route_profiles = {value for value in route.get("profiles", []) if isinstance(value, str)}
            route_phases = {value for value in route.get("phases", []) if isinstance(value, str)}
            if view == "mbse" and route_profiles != accepted_profiles:
                issues.append(_issue("profile_naming_drift", f"MBSE route profile 集合与模式门不一致: {sorted(route_profiles)} != {sorted(accepted_profiles)}", view=view, submode=route.get("submode")))
            elif view != "mbse" and not route_profiles.issubset(accepted_profiles):
                issues.append(_issue("profile_naming_drift", f"{view} route profile 含模式门不接受的值: {sorted(route_profiles - accepted_profiles)}", view=view, submode=route.get("submode")))
            if view == "mbse" and route_phases != accepted_phases:
                issues.append(_issue("phase_naming_drift", f"MBSE route phase 集合与模式门不一致: {sorted(route_phases)} != {sorted(accepted_phases)}", view=view, submode=route.get("submode")))
            elif view != "mbse" and not route_phases.issubset(accepted_phases):
                issues.append(_issue("phase_naming_drift", f"{view} route phase 含模式门不接受的值: {sorted(route_phases - accepted_phases)}", view=view, submode=route.get("submode")))
def _resolve_rule_files(package_root: Path, route: dict[str, Any], selection: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    files: list[str] = []
    groups = registry.get("groups", {}) if isinstance(registry, dict) else {}
    for raw_group in route.get("rule_groups", []):
        group = _render_template(raw_group, selection)
        if group is None:
            continue
        for relative in groups.get(group, []) if isinstance(groups.get(group), list) else []:
            if isinstance(relative, str) and relative not in files:
                files.append(relative.replace("\\", "/"))
    return files


def _check_route_combinations(
    package_root: Path,
    route_configs: dict[str, Any],
    registry: dict[str, Any],
    profiles: dict[str, Any],
    schema: dict[str, Any],
    confirm_module: ModuleType,
    planner_module: ModuleType,
    issues: list[dict[str, Any]],
) -> dict[str, int]:
    combinations = _route_combinations(route_configs)
    counts = {
        "declared_combinations": len(combinations),
        "mode_gate_checked": 0,
        "routeplan_checked": 0,
        "mode_gate_rejected": 0,
        "routeplan_rejected": 0,
    }
    with tempfile.TemporaryDirectory(prefix="route-contract-") as temp_dir:
        case = Path(temp_dir) / "case.json"
        for combination in combinations:
            counts["mode_gate_checked"] += 1
            counts["routeplan_checked"] += 1
            route_id = combination["route_id"]
            selection = combination["selection"]
            # RoutePlan requires a persisted, revision-bound confirmation.  A
            # single case cannot confirm every route at once, so each matrix
            # row receives an isolated fixture with the row's exact scope.
            _case_fixture(case, selection)
            args = _namespace(case, selection)
            try:
                canonical = confirm_module.normalized_route(args)
                conflicts = confirm_module.collect_conflicts(case and json.loads(case.read_text(encoding="utf-8")), args, canonical)
            except Exception as exc:  # pragma: no cover - defensive contract reporting
                counts["mode_gate_rejected"] += 1
                issues.append(_issue("mode_gate_evaluation_error", f"模式门执行异常: {exc}", route_id=route_id))
            else:
                if conflicts:
                    counts["mode_gate_rejected"] += 1
                    issues.append(
                        _issue(
                            "route_not_accepted_by_mode_gate",
                            "该机器路由组合未被 confirm_case_mode.py 接受",
                            route_id=route_id,
                            view=selection["view"],
                            submode=selection["submode"],
                            profile=selection["profile"],
                            phase=selection["phase"],
                            conflict_codes=[item.get("code") for item in conflicts],
                            conflicts=conflicts,
                        )
                    )

                if not conflicts:
                    expected_gate_scope = {key: selection.get(key) for key in ("transaction", "view", "submode", "profile", "phase", "domain")}
                    actual_gate_scope = {key: canonical.get(key) for key in expected_gate_scope}
                    if actual_gate_scope != expected_gate_scope:
                        counts["mode_gate_rejected"] += 1
                        issues.append(_issue("route_selection_normalization_drift", "模式门规范化后没有保留机器路由的精确字段", route_id=route_id, expected=expected_gate_scope, actual=actual_gate_scope))

            try:
                planner_args = copy.copy(args)
                plan = planner_module.build_plan(planner_args)
            except Exception as exc:  # pragma: no cover - defensive contract reporting
                counts["routeplan_rejected"] += 1
                issues.append(_issue("routeplan_evaluation_error", f"RoutePlan 执行异常: {exc}", route_id=route_id))
                continue

            shape_issues = _check_plan_shape(plan, schema, route_id=route_id)
            issues.extend(shape_issues)
            route_errors = plan.get("errors", []) if isinstance(plan, dict) else []
            if not isinstance(plan, dict) or plan.get("status") != "ready" or route_errors or shape_issues:
                counts["routeplan_rejected"] += 1
                issues.append(
                    _issue(
                        "route_not_accepted_by_routeplan",
                        "该机器路由组合未生成可执行 RoutePlan",
                        route_id=route_id,
                        view=selection["view"],
                        submode=selection["submode"],
                        profile=selection["profile"],
                        phase=selection["phase"],
                        plan_status=plan.get("status") if isinstance(plan, dict) else None,
                        plan_error_codes=[item.get("code") for item in route_errors if isinstance(item, dict)],
                    )
                )
                continue

            expected_profile = _render_template(combination["route"].get("read_profile"), selection)
            actual_profile = plan.get("read_profile")
            if expected_profile != actual_profile:
                issues.append(_issue("read_profile_naming_drift", f"RoutePlan read_profile 与 route 配置不一致: {expected_profile!r} != {actual_profile!r}", route_id=route_id))
            profile_map = profiles.get("profiles", {}) if isinstance(profiles, dict) else {}
            profile = profile_map.get(actual_profile) if isinstance(profile_map, dict) else None
            expected_pointers = profile.get("pointers", []) if isinstance(profile, dict) else None
            if expected_pointers is None:
                issues.append(_issue("routeplan_profile_missing", f"RoutePlan 引用了不存在的 profile: {actual_profile!r}", route_id=route_id))
            elif plan.get("json_pointers") != list(dict.fromkeys(expected_pointers)):
                issues.append(_issue("routeplan_pointer_drift", "RoutePlan json_pointers 与 slice profile 不一致", route_id=route_id, profile=actual_profile))
            for pointer in plan.get("json_pointers", []):
                if not _json_pointer_is_legal(pointer):
                    issues.append(_issue("routeplan_pointer_invalid", f"RoutePlan 输出非法 JSON Pointer: {pointer!r}", route_id=route_id, pointer=pointer))
            for relative in plan.get("rule_files", []):
                if not isinstance(relative, str) or not (package_root / relative).is_file():
                    issues.append(_issue("routeplan_rule_file_missing", f"RoutePlan 输出的 rule_file 不存在: {relative!r}", route_id=route_id, path=relative))
            expected_files = _resolve_rule_files(package_root, combination["route"], selection, registry)
            if plan.get("rule_files") != expected_files:
                issues.append(_issue("routeplan_rule_file_drift", "RoutePlan rule_files 与 route/registry 展开结果不一致", route_id=route_id))

    return counts


def _check_special_boundaries(
    route_configs: dict[str, Any],
    confirm_module: ModuleType,
    planner_module: ModuleType,
    issues: list[dict[str, Any]],
) -> dict[str, bool]:
    checks = {
        "controlled_drafting_boundary": False,
        "oa_v21_contract": False,
        "status_shortcut": False,
        "json_only_external_block": False,
    }
    drafting_routes = route_configs.get("drafting", {}).get("routes", [])
    controlled = next((route for route in drafting_routes if isinstance(route, dict) and route.get("submode") == "stage1_stage3_claim_core"), None)
    expected_boundary = {
        "stage2": "mocked_pass",
        "allow_real_search": False,
        "allow_oa": False,
        "allow_legal_conclusion": False,
        "release_grade_claim_text": False,
    }
    if not isinstance(controlled, dict) or controlled.get("boundary") != expected_boundary:
        issues.append(_issue("controlled_drafting_boundary_drift", "stage1_stage3_claim_core 的受控边界不符合合同", expected=expected_boundary, actual=controlled.get("boundary") if isinstance(controlled, dict) else None))
    else:
        checks["controlled_drafting_boundary"] = True

    oa_routes = route_configs.get("oa", {}).get("routes", [])
    if not oa_routes or any(route.get("default_profile") != "v2.1-oa" or route.get("profiles") != ["v2.1-oa"] for route in oa_routes if isinstance(route, dict)):
        issues.append(_issue("oa_v21_contract_drift", "OA 路由没有统一使用 v2.1-oa profile"))
    else:
        checks["oa_v21_contract"] = True

    with tempfile.TemporaryDirectory(prefix="route-special-") as temp_dir:
        case = Path(temp_dir) / "case.json"
        status_selection = {
            "transaction": "case_json_only",
            "view": "audit",
            "submode": "status",
            "profile": "l0",
            "phase": "audit",
            "domain": "all",
        }
        _case_fixture(case, status_selection)
        status_args = _namespace(case, {"transaction": "case_json_only", "status_only": True})
        try:
            status_route = confirm_module.normalized_route(status_args)
            status_conflicts = confirm_module.collect_conflicts(json.loads(case.read_text(encoding="utf-8")), status_args, status_route)
        except Exception as exc:  # pragma: no cover
            status_conflicts = [{"code": "exception", "message": str(exc)}]
        if status_conflicts:
            issues.append(_issue("status_shortcut_not_accepted", "D 状态查看捷径未被模式门接受", conflicts=status_conflicts))
        else:
            checks["status_shortcut"] = True

        status_plan_args = _namespace(
            case,
            status_selection,
        )
        status_plan = planner_module.build_plan(status_plan_args)
        if status_plan.get("status") != "ready" or status_plan.get("route_id") != "audit.status.l0.audit":
            issues.append(_issue("status_routeplan_not_accepted", "D 状态查看的 RoutePlan 等价路径未准备就绪", status=status_plan.get("status"), route_id=status_plan.get("route_id")))

        external_args = _namespace(
            case,
            status_selection,
            external_requested=True,
        )
        external_route = confirm_module.normalized_route(external_args)
        external_conflicts = confirm_module.collect_conflicts(json.loads(case.read_text(encoding="utf-8")), external_args, external_route)
        hard_external = [item for item in external_conflicts if item.get("severity") == "hard" and item.get("code") in {"json_only_external_read", "external_read_forbidden"}]
        if not hard_external:
            issues.append(_issue("json_only_external_not_hard_blocked", "B JSON-only + external_requested 没有产生 hard conflict", conflicts=external_conflicts))
        else:
            checks["json_only_external_block"] = True
        external_plan = planner_module.build_plan(external_args)
        if external_plan.get("status") != "blocked" or not any(item.get("code") == "external_read_forbidden" for item in external_plan.get("errors", []) if isinstance(item, dict)):
            issues.append(_issue("routeplan_external_not_blocked", "RoutePlan 没有阻断 case_json_only 的外部读取请求", status=external_plan.get("status")))

    return checks


def validate_contract(package_root: Path | None = None) -> dict[str, Any]:
    root = Path(package_root or Path(__file__).resolve().parents[1]).resolve()
    routing_root = root / "references" / "routing"
    issues: list[dict[str, Any]] = []
    loaded: dict[str, Any] = {}
    for relative in REQUIRED_ROUTING_FILES:
        value, error = _load_json(routing_root / relative)
        if error:
            issues.append(_issue("routing_file_unreadable", error, path=relative))
        else:
            loaded[relative] = value
    schema, schema_error = _load_json(root / "references" / "schemas" / "route-plan.schema.json")
    if schema_error:
        issues.append(_issue("route_plan_schema_unreadable", schema_error))
        schema = {}
    route_configs: dict[str, Any] = {}
    for view in VIEW_NAMES:
        value, error = _load_json(routing_root / "views" / f"{view}.json")
        if error:
            issues.append(_issue("view_route_file_unreadable", error, view=view))
        else:
            route_configs[view] = value

    try:
        confirm_module = _module_from_path(root / "scripts" / "confirm_case_mode.py", "_route_contract_confirm")
        planner_module = _module_from_path(root / "scripts" / "plan_case_route.py", "_route_contract_planner")
    except (OSError, ImportError, SyntaxError) as exc:
        issues.append(_issue("route_runtime_unloadable", f"无法加载模式门或 RoutePlan 脚本: {exc}"))
        confirm_module = planner_module = None  # type: ignore[assignment]

    if all(name in loaded for name in REQUIRED_ROUTING_FILES):
        _check_routing_config(
            root,
            route_configs,
            loaded["transactions.json"],
            loaded["rule-registry.json"],
            loaded["slice-profiles.json"],
            schema,
            issues,
        )
    router_texts = _check_router_documents(root, route_configs, issues)
    if confirm_module is not None:
        _check_explicit_naming_drift(route_configs, confirm_module, router_texts, issues)

    counts: dict[str, int] = {
        "declared_combinations": 0,
        "mode_gate_checked": 0,
        "routeplan_checked": 0,
        "mode_gate_rejected": 0,
        "routeplan_rejected": 0,
    }
    special_checks = {
        "controlled_drafting_boundary": False,
        "oa_v21_contract": False,
        "status_shortcut": False,
        "json_only_external_block": False,
    }
    if confirm_module is not None and planner_module is not None and all(name in loaded for name in REQUIRED_ROUTING_FILES) and isinstance(schema, dict):
        counts = _check_route_combinations(
            root,
            route_configs,
            loaded["rule-registry.json"],
            loaded["slice-profiles.json"],
            schema,
            confirm_module,
            planner_module,
            issues,
        )
        special_checks = _check_special_boundaries(route_configs, confirm_module, planner_module, issues)

    issues = _deduplicate_issues(issues)
    by_code: dict[str, int] = {}
    for item in issues:
        code = str(item.get("code", "unknown"))
        by_code[code] = by_code.get(code, 0) + 1
    return {
        "passed": not issues,
        "package_root": str(root),
        "checks": {
            "route_configuration_loaded": all(name in loaded for name in REQUIRED_ROUTING_FILES),
            "router_documents_loaded": all(view in router_texts for view in ROUTER_NAMES),
            "route_plan_schema_loaded": isinstance(schema, dict) and bool(schema),
            "mode_gate_and_routeplan_matrix": counts["mode_gate_rejected"] == 0 and counts["routeplan_rejected"] == 0 and counts["declared_combinations"] > 0,
            **special_checks,
        },
        "counts": counts,
        "error_counts": by_code,
        "errors": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="验证统一案件 Skill 的路由合同一致性")
    parser.add_argument("--package-root", type=Path, default=None, help="Skill package 根目录；默认使用当前脚本所在 package")
    args = parser.parse_args(argv)
    report = validate_contract(args.package_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
