---
name: cn-patent-case-workflow
description: >-
  统一管理中国专利案件的材料导入、MBSE、专利检索、专利撰写、审查意见答复、复审、专利权人无效答辩意见陈述与跨视图审计。
  每个案件仅使用一个主 case.json；用户必须明文确认事务模式和业务路由，AI 判断不一致时必须先质疑。
  只有首次导入或明确重新导入可读取外部材料，其余计算、审计和导出仅从案件 JSON 的受控投影读取并通过版本化 Patch 写回。
---

# 中国专利案件统一工作流

这是唯一运行入口。MBSE、检索、撰写、答审/复审、专利权人无效答辩意见陈述和审计只是同一 `case.json` 的内部视图，不得作为独立 Skill 触发。`search.invalidity` 仅表示无效相关检索，`invalidity.defense` 专用于专利权人针对无效请求的答辩意见陈述，二者不得混用。

## 1. 先取得明文选择

除非用户在当前请求中已经逐项明文给出，否则第一轮只询问：

```text
请选择本次使用方式：

A. 首次导入外部案件材料
B. 仅使用已有案件 JSON
C. 明确重新导入或合并外部材料
D. 仅查看案件状态
```

不得把“继续”“刷新”“重算”“按你判断”或业务描述本身当作确认。

- A 对应 `bootstrap_import`；C 对应 `reimport_material`。还要确认 `case.json` 路径、明确文件清单、覆盖/追加/并行策略、旧批次保留方式和是否允许写回。纯导入不强迫选择业务视图；导入后若继续分析，必须按新 revision 再确认业务路由。
- B 对应 `case_json_only`。还要确认 `case.json` 路径、业务视图、子模式、必要的 profile/phase 和技术领域。
- D 对应 `case_json_only + audit/status/l0/audit + domain=all`，只需案件路径，不追问无关业务视图。
- 用户要求从 JSON 生成文件或正文时，另行明文确认 `export_from_json`；它只能以主 JSON 为输入。

业务路由的 canonical 值仅限：

| view | submode | profile | phase |
|---|---|---|---|
| `mbse` | `disclosure` / `document` / `search` | `standard` | `modeling` |
| `search` | `novelty` / `invalidity` / `FTO` / `landscape` | `quick` / `standard` / `formal` | `search` |
| `drafting` | `stage1` 至 `stage9` | `standard` | 对应 `stage_01` 至 `stage_09` |
| `drafting` | `stage1_stage3_claim_core` | `controlled` | `stage_03` |
| `oa` | `opinion` / `reexamination` | `v2.1-oa` | `phase_01` 至 `phase_05` |
| `invalidity` | `defense` | `v2.1-invalidity` | `phase_01` 至 `phase_05` |
| `audit` | `status` / `consistency` / `ownership` / `dependencies` | `l0` / `l1` / `l2` / `l3` | `audit` |

业务领域为 `mechanical`、`electronics` 或 `biochemical`；审计可用 `all`。兼容别名只能由模式门规范化，后续一律使用 canonical 值。

## 2. 模式门和质疑

先加载 `references/core/mode-gate.md`，使用 `scripts/confirm_case_mode.py` 检查用户选择、案件状态、当前 revision、JSON-only 边界和 AI 候选判断。

- hard conflict：直接阻断，不能 override；
- advisory conflict：必须向用户列出“用户选择、AI 判断、依据、后果、保持/改选方案”和 `challenge_id`；
- 用户坚持原选择时，必须针对同一 `challenge_id` 明文给出理由，再记录 `advisory-override`；
- 用户改选、案件 revision 变化或 route scope 变化后，旧确认立即失效；
- 未达到 `confirmation_status=confirmed`，不得加载业务规则、计算或生成 Patch。

AI 只能提出候选，不能静默替用户改选。

## 3. 生成 RoutePlan，再加载规则

确认后使用 `scripts/plan_case_route.py` 生成 RoutePlan。只有 `status=ready` 且 `confirmation.execution_allowed=true` 才执行。

RoutePlan 是本次任务的唯一运行清单：

- 只读取 `read_profile`、`json_pointers` 和明确请求的稳定对象 ID；
- 先只加载 `rule_files`（基础文件最多四个）；`conditional_rule_files` 只在本次明确的 operation 满足 trigger 时，按 `active_conditional_rule_files` 加载并记录 reason。不得浏览并批量加载整个 `references/views/`；
- 不加载 `forbidden_rule_groups`；
- 遵守 `context_budget`、`write_prefix`、`validators` 和 `preconditions`；
- 缺少前置输入时返回 `blocked` 或建议重新导入，不得扩大读取范围绕过。

视图路由说明只在需要人工核对 RoutePlan 时读取对应的 `references/views/<view>/router.md`。领域规则仅在技术领域已确认且 RoutePlan 明确列入时加载，最多一个领域文件。

## 4. 单一 JSON 与受控投影

每个案件只有 `<案件目录>/case.json`，权威层固定为 `source_materials`、`normalized`、`derived`、`control`。

- 仅 A/C 可读取用户明确列出的外部文件；B、D 和 `export_from_json` 禁止回读 DOCX、PDF、图片、网页、公报或 `source_path`；
- 外部检索响应必须先作为导入事务写入 JSON，之后才能分析；
- L0 只返回案件导航、revision、视图状态以及 gate/question/conflict 的数量和 ID；
- L1 使用 RoutePlan 的 operation profile；
- L2 仅返回指定稳定 ID 及有界依赖/证据闭包；
- L3 只返回异常摘要、受影响 ID 和有界路径，不返回完整 `case.json`；
- 模型投影排除原始二进制、base64、无关全文和完整历史。

使用 `scripts/inspect_case_json.py`；`scripts/read_case_slice.py` 仅为兼容入口。跨视图只传稳定 ID、JSON Pointer、输入 revision 和状态，下一视图必须重新投影读取。

需要解释证据权威、对象状态或失效关系时才加载 `references/core/authority-and-status.md`。

## 5. 写回只走 Patch

视图写权限固定为：

```text
mbse      → /derived/mbse
search    → /derived/search
drafting  → /derived/drafting
oa        → /derived/oa
invalidity → /derived/invalidity
audit     → /derived/audit
总控      → /control
```

只有任务需要写回时才加载 `references/core/patch-policy.md`。不得直接覆盖整个 `case.json`。写回前必须：

1. 校验确认绑定和 `base_revision`；
2. 校验字段所有权、Schema、稳定 ID、引用闭合和状态转换；
3. 计算影响集，只把受影响对象标为 `stale` 或 `invalid`；
4. 向用户展示变更计划并取得明确写回确认；
5. 使用 `scripts/commit_case_patch.py` 原子提交并记录新 revision、事务和冲突。

默认逻辑删除；审计视图只报告问题，不直接修改业务事实。

## 6. 真实性边界与短交付

必须区分 `fresh`、`stale`、`blocked`、`invalid`、`candidate`、`conditional`、`[Q]`、`mocked_pass` 和 `pass`。结构校验、模拟门、候选文本或静态回归不得被表述为实际检索结论、实体法律结论或可直接提交文件。

`stage1_stage3_claim_core` 始终保持：阶段 2 为 `mocked_pass`，不执行真实检索、阶段 4 至 9、OA/复审或实体法律结论，且 `release_grade_claim_text=false`。

完成后只返回当前任务所需的短结果：确认状态、RoutePlan ID、已读 JSON 路径、变更路径、创建/待处理 ID、是否写回、阻断项和下一视图输入路径；不得复制完整视图对象或声称未完成事项已完成。