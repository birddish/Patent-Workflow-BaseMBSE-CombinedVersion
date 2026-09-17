# 明文模式确认门（唯一详细合同）

本文件是统一案件 Skill 的唯一详细模式合同。它只负责：取得用户明文选择、规范化路由、检查事务与视图组合、处理 AI/用户差异、绑定案件 revision，并把可执行路由交给 RoutePlan。它不执行 MBSE、检索、撰写、答审或审计计算。

规范来源只有：

- [`confirm_case_mode.py`](../../scripts/confirm_case_mode.py)：canonical 规范化、冲突和确认输出；
- [`transactions.json`](../routing/transactions.json)：四类事务的外部读取和案件存在性边界；
- [`mbse.json`](../routing/views/mbse.json)、[`search.json`](../routing/views/search.json)、[`drafting.json`](../routing/views/drafting.json)、[`oa.json`](../routing/views/oa.json)、[`audit.json`](../routing/views/audit.json)、[`invalidity.json`](../routing/views/invalidity.json)：合法视图路由；
- 确认通过后才读取 [`plan_case_route.py`](../../scripts/plan_case_route.py) 和 [`route-plan.schema.json`](../schemas/route-plan.schema.json) 生成 RoutePlan。

其他“导入与路由”或“模式确认”文件只是兼容入口，不复制本合同。

## 1. 首轮必须明文选择

首轮固定询问：

```text
请选择本次使用方式：

A. 首次导入外部案件材料
B. 仅使用已有案件 JSON
C. 明确重新导入或合并外部材料
D. 仅查看案件状态
```

这四项是数据来源/事务模式，不是 AI 可以代选的建议。用户只说“继续”“刷新”“重算”“按你判断”，不能视为确认。

除纯导入外，用户还必须明文确定：

```text
transaction
view
submode
domain
```

适用时还必须确定 `profile` 和 `phase`。固定单值的 `profile/phase` 可以由脚本规范化补齐，但不得由 AI 擅自改选；对外确认应说明其 canonical 值。

### A-D 与脚本事务名

| 用户选择 | canonical transaction | 案件与材料条件 | 读取边界 |
|---|---|---|---|
| A 首次导入 | `bootstrap_import` | `case.json` 必须不存在；必须明列材料并使用 `--materials-listed` | 只允许读取明列的外部材料 |
| B 使用已有 JSON | `case_json_only` | `case.json` 必须存在；必须另选业务视图，或选择 D 的 `status-only` | 严禁读取外部材料 |
| C 重新导入/合并 | `reimport_material` | `case.json` 必须存在；必须明列追加/重新导入材料并使用 `--materials-listed` | 只允许读取明列的外部材料 |
| D 查看状态 | `case_json_only --status-only` | `case.json` 必须存在；不接受无关 view/submode/profile/phase | 只读取 JSON 的状态投影 |

`export_from_json` 不是第五个首轮菜单项，而是用户要求生成输出时的独立事务：必须重新明文确认；它只能从已有 `case.json` 输入，禁止外部读取。

### 纯导入例外

A 或 C 可以只确认导入，不同时选择业务视图。此时允许暂缺：

```text
view / submode / profile / phase / domain
```

但仍必须提供案件路径、材料清单和 A/C 对应的案件存在性条件。C 的写确认必须以可重复的 `--material` 明列每一个文件路径，并明文确定 `--strategy` 和 `--old-batch-policy`；这些值写入 `route_confirmation.import_scope`，实际重新导入必须逐项匹配。纯导入只完成 `source_materials`、导入态 `normalized` 和必要的 `control` 写入，不加载业务视图规则，不执行业务计算，也不生成业务 RoutePlan；A 使用创建型导入 Patch，C 使用现有案件的统一 Patch 提交器。

导入完成后，如果要继续 MBSE、检索、撰写、答审或审计，必须以新 revision 重新明文确认业务视图和适用字段；不得把“导入”默认解释为后续业务操作。若 A/C 同时明文选择完整业务路由，则仍须通过该业务路由的组合和前置条件检查。

## 2. D=status-only

用户明文选择 D 后，脚本自动形成以下 canonical route：

```json
{
  "transaction": "case_json_only",
  "view": "audit",
  "submode": "status",
  "profile": "l0",
  "phase": "audit",
  "domain": "all",
  "status_only": true
}
```

因此 D 不要求用户重复选择业务视图；但用户仍必须明文选择 D。以下输入是 hard conflict：

```text
status-only + 非 audit 的 view
status-only + 非 status/l0 的 submode
status-only + profile 或 phase
status-only + 外部读取请求
```

D 只读取紧凑状态索引；详细 gate、question、conflict 或业务对象必须另行按 ID/路径读取。

## 3. canonical 路由值

以下是 `confirm_case_mode.py` 规范化后并由 `references/routing/views/*.json` 支持的值。RoutePlan 必须使用这些值，不能使用自然语言标签或未注册别名。

| view | canonical submode | canonical profile | canonical phase | canonical domain |
|---|---|---|---|---|
| `mbse` | `disclosure`、`document`、`search` | `standard` | `modeling` | `mechanical`、`electronics`、`biochemical` |
| `search` | `novelty`、`invalidity`、`FTO`、`landscape` | `quick`、`standard`、`formal` | `search` | `mechanical`、`electronics`、`biochemical` |
| `drafting` | `stage1`～`stage9`；`stage1_stage3_claim_core` | `standard`；受控模式为 `controlled` | `stage_01`～`stage_09` | `mechanical`、`electronics`、`biochemical` |
| `oa` | `opinion`、`reexamination` | `v2.1-oa` | `phase_01`～`phase_05` |
| `invalidity` | `defense` | `v2.1-invalidity` | `phase_01`～`phase_05` | `mechanical`、`electronics`、`biochemical` |
| `audit` | `status`、`consistency`、`ownership`、`dependencies` | `l0`、`l1`、`l2`、`l3` | `audit` | `all`、`mechanical`、`electronics`、`biochemical` |

组合约束：

```text
mbse：profile=standard，phase=modeling
search：profile 必须为 quick/standard/formal，phase=search
drafting：stageN → profile=standard、phase=stage_0N
          stage1_stage3_claim_core → profile=controlled、phase=stage_03
oa：profile=v2.1-oa，phase 必须为 phase_01 至 phase_05
invalidity：submode=defense，profile=v2.1-invalidity，phase 必须为 phase_01 至 phase_05；response_round 记录首次/补充答辩，不另造 submode
audit：profile 为 l0/l1/l2/l3，phase=audit
```

除 D 自动使用 `domain=all` 外，业务视图必须明文选择 domain。案件已有 `technical_domain` 且与用户选择不一致时，属于 hard conflict；不能用 AI 判断替换用户选择。

### 输入别名与 canonical 输出

别名只用于兼容输入，永远不写入 `canonical_route`：

```text
MBSE：mode_disclosure/mode_document/mode_search → disclosure/document/search
检索：fto → FTO
OA：response/oa_response/opinion_drafting/answer → opinion
    appeal/re_exam → reexamination
    submode=v2.1-oa → opinion，并补 profile=v2.1-oa
审计：submode=l0/l1/l2/l3 → submode=status，并将该值作为 profile
撰写：claim_core + phase=stage_01/stage_03 → stage1/stage3
    dependent_claims + stage_03 → stage3
    claim_text_audit/support_traceability + stage_03/stage_08 → 对应 stage3/stage8
```

阶段和审查阶段的输入可写成 `stage1`、`stage-1`、`stage_01` 或 `phase1`、`phase-1`；脚本输出统一为 `stage_01` 或 `phase_01`。撰写受控入口的正式 canonical 值仍是 `stage1_stage3_claim_core`，不是 `claim_core`。

## 4. invalidity 与 search.invalidity 的边界

- `view=search, submode=invalidity` 只表示无效相关检索、文献覆盖和检索风险分析；它不得自动生成专利权人的答辩意见。
- `view=invalidity, submode=defense` 只表示以专利权人立场对无效请求、具体理由、权利要求和证据进行答辩意见陈述；它写入 `/derived/invalidity`，不写入 `/derived/search` 或 `/derived/oa`。
- invalidity 的五阶段固定为：`phase_01` 材料准入、`phase_02` 事实核实、`phase_03` MBSE 追溯与逐理由分析、`phase_04` 答辩意见起草、`phase_05` 交付前核对。
- 每一轮意见以 `response_round` 表示首次或补充答辩；普通“继续”“刷新”“重算”不改变事务模式，也不触发外部材料读取。

## 5. 冲突分级：hard 不可 override

脚本输出同时保留：

```text
user_selection
canonical_route
route_scope
ai_routing_assessment
conflicts
hard_conflicts
advisory_conflicts
challenge_id
next_action
```

### hard conflict

以下任一情况都必须阻断，不得执行、读取业务规则或生成 Patch：

- 对需要完整业务路由的事务，transaction、view、submode、profile、phase、domain 缺失、非法或组合不被路由 JSON 支持；A/C 纯导入暂缺业务字段不适用此项；
- A 的案件已存在，或 A 未明列材料；C 的案件不存在，或 C 未明列材料；
- B/D/`case_json_only` 或 `export_from_json` 请求外部读取；
- B/D/导出缺少案件 JSON，或视图缺少脚本检查的必要输入；
- `status-only` 携带无关路由字段；
- `expected_revision` 与当前 revision 不一致，或确认写回期间 revision 发生变化；
- 使用错误的 `challenge_id`、缺少 `override_reason`，或试图用 advisory override 绕过 hard conflict。

hard conflict 的处理只有：修正明文选择、补足已允许的输入、重新导入，或重新读取当前 JSON。`--advisory-override` 永远不能解除 hard conflict。

### advisory conflict 与两步 challenge

当 AI 提供的候选 transaction、view、submode、profile、phase 或 domain 与用户明文选择不一致，而用户选择本身合法时，产生 advisory conflict。AI 只能提出候选，不能自动替换用户选择。

第一步：使用 `--ai-transaction`、`--ai-view`、`--ai-submode`、`--ai-profile`、`--ai-phase` 或 `--ai-domain` 产生差异时，必须暂停并向用户明示：用户选择、AI 候选、冲突字段、判断依据和可能后果。脚本返回：

```text
confirmation_status=challenge_required
challenge_required=true
challenge_id=<当前案件 revision、route scope 和冲突集合绑定的 ID>
```

即使同时带 `--write-confirmation`，第一次 challenge 也不得写入 confirmed。

第二步：用户若坚持原选择，必须针对第一次返回的同一个 `challenge_id` 再次明文确认，并同时提供：

```text
--challenge-id <第一次返回的 ID>
--advisory-override
--override-reason "用户坚持该路由的明确理由"
--write-confirmation
```

只有在“全部冲突均为 advisory、ID 匹配、理由非空、route scope 未改变、revision 未改变”时，才可记录 `override_keep_user_selection` 并继续。用户改选任何字段都应重新提交完整明文路由，不得沿用旧 challenge。

## 6. 确认与 revision 绑定

已有案件的确认写回会递增 `control.current_revision`，并在 `control.navigation` 保存：

```json
{
  "route_scope": {
    "transaction": "case_json_only",
    "view": "drafting",
    "submode": "stage3",
    "profile": "standard",
    "phase": "stage_03",
    "domain": "mechanical"
  },
  "confirmation_base_revision": 12,
  "confirmed_revision": 13,
  "confirmation_status": "confirmed",
  "challenge_required": false
}
```

确认有效必须同时满足：

```text
control.navigation.confirmation_status == confirmed
control.navigation.confirmed_revision == control.current_revision
control.navigation.route_scope == 当前 canonical route_scope
```

执行前必须重新检查。使用 `--check-confirmation` 可检查 revision 和 route scope；任一变化都返回 `invalidated`，并要求重新明文确认。使用 `--expected-revision` 防止基于过期 L0 计划确认。

脚本的无写回预览可能显示 `confirmation_status=confirmed`，但没有 `recorded_revision` 或有效的持久化 `confirmation_binding` 时，只能视为“无冲突预览”，不能视为案件已确认。首次 bootstrap 在案件尚未创建时可能返回 `confirmed_but_not_recorded_no_case_json`；案件创建后必须重新确认并绑定 revision。

## 7. RoutePlan 接续与最小加载

模式门通过后，按以下顺序接续：

```text
confirm_case_mode.py
    → 读取 canonical_route / route_scope
    → （必要时）写入并检查持久化确认
    → plan_case_route.py
    → 生成 RoutePlan
    → 只读取 RoutePlan 指定的 JSON 投影和 rule_files
```

`plan_case_route.py` 是只读规划器。除纯导入外，将确认输出中的 canonical `transaction/view/submode/profile/phase/domain` 传入，并将用户确认状态传为 `--confirmation-status confirmed`；不要把 AI 候选当作用户参数。规划器只允许引用当前视图路由 JSON 注册的规则文件和切片 profile。

RoutePlan 至少控制：

```text
status：ready / confirmation_required / challenge_required / blocked
read_profile
json_pointers
requested_ids
rule_files
forbidden_rule_groups
write_prefix
validators
context_budget
preconditions
ai_routing_assessment
ai_suggestion_applied=false
routing_basis=user_selection_only
```

只有 `status=ready` 且 `confirmation.execution_allowed=true` 才能加载规则或执行视图操作。`confirmation_required`、`challenge_required`、`blocked` 均停止在门上。模型只接收 `json_pointers` 对应的 L0/L1/L2 投影；不得为“方便”读取完整 `case.json`、父级大对象、`source_path`、外部原文件或未列入 RoutePlan 的视图规则。

视图完成后只交接对象 ID、变更路径、待处理 ID 和下一路由；下一视图重新按 RoutePlan 从案件 JSON 读取，不复制上一视图的完整结果。