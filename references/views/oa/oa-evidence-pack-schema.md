# OA 专利证据包 Schema（v2.1-oa）

## 1. 目的、版本与兼容性

`patent_evidence_pack.json` 是申请文件、MBSE模型、审查意见、权利要求修改和答复之间的唯一结构化交接件。`v2.1-oa` 继承 `v2.0-oa` 的 `DOC/CLM/CF/REL/EV/NB/IS/OA/AMD/RT` 语义，新增活动权利要求集合、分析快照、问题注册表、修改策略和重算门。

- 新任务必须写 `schema_version: "2.1-oa"`。
- `v2.0-oa` 仍可读取，但只能通过兼容性基础校验；应使用 `scripts/normalize_oa_evidence_pack.py` 生成不覆盖的 `v2.1-oa` 副本。
- 升级保留原ID、原文、证据定位和 `D/I/Q/X` 事实语义；活动集合、文献资格或主策略无法唯一确定时必须标 `Q/candidate/blocked`，不得猜测。

## 2. 顶层字段

在 `v2.0-oa` 全部字段基础上，必须增加：

```json
{
  "claim_sets": [],
  "active_claim_set_id": "CLMSET-...",
  "analysis_snapshots": [],
  "active_snapshot_id": "SNAP-...",
  "issue_registry": [],
  "amendment_strategies": [],
  "primary_strategy_id": "STR-...",
  "combination_paths": [],
  "teaching_records": [],
  "effect_evidence_cards": [],
  "decision_trails": [],
  "recalculation_gate": {}
}
```

活动ID只能各指向一个 `status=active/primary` 对象。不能确定时ID置空，相关对象置 `candidate` 或 `blocked`，并使重算门失败。

## 3. 事实状态与文献法律资格双轴

模型节点、关系、证据和事实主张继续使用：

- `D`：材料明确记载；
- `I`：依规则从已记载事实受限推断；
- `Q`：材料不足、冲突或待核验；
- `X`：明确排除或与原文矛盾。

文献对每个评价轴分别使用：

```json
"eligibility": {
  "novelty": "eligible | conditional | Q | ineligible | not_applicable",
  "inventive_step": "eligible | conditional | Q | ineligible | not_applicable",
  "status": "D | I | Q | X",
  "reason": "资格事实、日期和法律角色说明"
}
```

`conditional` 只表示测试材料已明确给出日期或角色、但官方材料尚待核验；日期缺失、互相冲突或抵触申请条件无法判断时必须为 `Q`。仅具抵触申请新颖性资格的文件，其 `inventive_step` 必须为 `ineligible`。

文献和证据对象可增加 `source_status` 与 `research_role`（具体枚举见 §3.1）。该字段只描述来源性质和研究用途，不改变 `D/I/Q/X` 事实状态或文献法律资格；数据集页面、社论和预印本不得在论证中被当作同等强度的正式实证。

### 3.1 来源性质元数据（可选）

`documents` 及其引用台账可增加：

```json
{
  "source_status": "peer_reviewed | dissertation | conference | preprint | dataset | official_manual | official_report | official_presentation | official_web | user_supplied",
  "research_role": "direct_method | normative_baseline | practice_precedent | empirical_context | tool_evidence | comparative_support | excluded"
}
```

字段只记录资料形式和研究用途，不改变 `D/I/Q/X` 事实状态，也不替代 `eligibility`。旧版 `v2.0-oa` 或缺少字段的 `v2.1-oa` 包继续只读兼容；新建包在资料性质已知时填写。

## 4. 权利要求集合与引用路径

`claims` 中每个新版本必须有稳定ID、`version`、完整文本、`feature_group_ids`、`status`；替代旧版本时写 `supersedes` 并由 `claim_amendment_events` 指向。

`claim_sets` 至少记录：

```json
{
  "id": "CLMSET-AMENDED-01",
  "claim_ids": ["CLM-NEW-01", "CLM-NEW-02"],
  "status": "active | candidate | superseded | invalidated",
  "supersedes": "CLMSET-ORIGINAL",
  "fact_status": "D"
}
```

任一时点必须且只能有一组活动权利要求。活动从属项按每条合法引用路径展开；路径记录写入活动快照的 `claim_paths`，不得只评价其新增限定。

## 5. 分析快照

阶段三前冻结：

```json
{
  "id": "SNAP-01",
  "claim_set_id": "CLMSET-AMENDED-01",
  "claim_paths": [
    {"id": "PATH-C2-C1", "claim_id": "CLM-NEW-02", "ancestor_claim_ids": ["CLM-NEW-01"]}
  ],
  "document_eligibility": {
    "DOC-D1": {"novelty": "eligible", "inventive_step": "eligible"}
  },
  "combination_path_ids": ["CP-01"],
  "teaching_record_ids": ["TR-01"],
  "effect_evidence_card_ids": ["EEC-01"],
  "decision_trail_ids": ["DT-01"],
  "primary_strategy_id": "STR-01",
  "status": "active",
  "snapshot_id": "SNAP-01",
  "freeze_revision": "REV-0001",
  "frozen_at": "2026-09-06T00:00:00+08:00",
  "freeze_status": "active"
}
```

新任务使用 `snapshot_id + freeze_revision` 标识冻结版本。`freeze_revision` 是单调递增或人工明确的版本号，`frozen_at` 记录冻结时间（未知时可为 `null`），`freeze_status` 取 `active | superseded | invalidated`。不得为新任务生成或比较内容 Hash。旧 v2.0/v2.1 包中已有 `frozen_hash` 时仅原样保留、只读兼容，不重新计算，也不以其作为新任务的通过条件。全部活动 `NB/IS/RT` 必须引用同一 `active_snapshot_id`；旧快照记录只能为 `superseded/invalidated`。

## 6. 问题注册表

每个OA问题以法律依据、权利要求范围、文献组合路径和主张类型形成稳定指纹：

```json
{
  "id": "IR-01",
  "issue_id": "OA-01",
  "fingerprint": {
    "legal_basis": "专利法第二十二条第三款",
    "claim_ids": ["CLM-NEW-01"],
    "document_path": ["DOC-D1", "DOC-D2"],
    "assertion_type": "inventive_step"
  },
  "status": "active"
}
```

`issue_registry`、`office_action_issues` 与活动 `response_trace.issue_ids` 必须一一对应；OA问题调整颗粒度时新建注册记录并明确替代关系，不得悄然合并或遗漏。

每个 `OAIssue` 还应记录 `claim_version_id`、`evidence_paragraph_ids`、`difference_feature_ids`、`effect_evidence_card_ids`、`combination_path_ids` 和 `response_mode`。其中 `response_mode` 取 `ArgumentOnly | AmendmentBased | Interview | Appeal`。

## 6A. 组合路径、效果证据卡与决定轨迹

以下对象为 v2.1-oa 的增量字段，旧证据包缺失时按空数组兼容，不改变原有 ID：

```json
{
  "combination_paths": [
    {
      "id": "CP-01",
      "claim_version_id": "CLM-V-01",
      "start_document_id": "DOC-D1",
      "supplement_document_ids": ["DOC-D2"],
      "operations": [
        {"type": "replace", "from": "D1.S2", "to": "D2.S3", "order": 1}
      ],
      "allowed_transformations": ["Ω-interface-adaptation"],
      "interface_conditions": [],
      "parameter_conditions": [],
      "teaching_record_ids": ["TR-01"],
      "expected_success": {"status": "D | I | Q | X", "evidence_ids": []},
      "breakpoint_ids": ["BP-01"],
      "fusion_feasible": "true | false | conditional | Q",
      "lifecycle_status": "active | superseded | invalidated"
    }
  ],
  "effect_evidence_cards": [
    {
      "id": "EEC-01",
      "claim_version_id": "CLM-V-01",
      "effect_text": "",
      "causal_chain": ["R-01", "F-01", "S-01", "B-01", "E-01"],
      "comparison_baseline": "",
      "source_document_ids": [],
      "evidence_date": "",
      "scope_coverage": "full | partial | unknown",
      "fact_status": "D | I | Q | X",
      "lifecycle_status": "active | superseded | invalidated"
    }
  ],
  "decision_trails": [
    {
      "id": "DT-01",
      "issue_id": "OA-01",
      "claim_version_id": "CLM-V-01",
      "combination_path_ids": ["CP-01"],
      "response_event_ids": ["RE-01"],
      "amendment_event_ids": [],
      "decision_event_ids": ["DE-01"],
      "result_reason_ids": ["RR-01"],
      "closure_status": "open | closed | Q"
    }
  ]
}
```

`combination_paths` 记录可重放的具体操作，不能以文献编号相加替代；`fusion_feasible` 是工程事实状态，不是法律结论。`effect_evidence_cards` 必须说明比较基准、来源日期及权利要求范围覆盖；申请日后实验只能作为补强材料。`decision_trails` 连接 OA 争点、申请人行动和审查结果理由，用于正向/反向闭包审计。以上新增对象不要求对文件计算或比较 Hash。

### 6B. 权利要求—说明书支持链接（可选桥接）

当 OA 任务需要消费撰写流程的支持审计时，可在顶层增加 `support_links` 数组。每项至少包括：

```json
{
  "id": "SL-01",
  "claim_id": "CLM-01",
  "claim_version_id": "CLM-V-01",
  "claim_span": "权利要求片段或限定编号",
  "description_id": "AP-DESC-01",
  "source_location": "段落[0008]/图2/实施例1",
  "relation_type": "itself | description | example",
  "confidence": 0.0,
  "figure_or_assay_anchor": "可选锚点",
  "human_decision": "pending | accepted | rejected",
  "review_note": "人工复核理由"
}
```

`confidence` 仅用于排序候选证据；没有原文位置和人工决定时不得关闭支持问题或通过补正重算门。该桥接不新建权利要求树，仍以活动 `ClaimVersion`、合法引用路径和既有 `DepPath` 为准。

`teaching_records` 对应第四章的 `TeachingRecord(p)`，至少记录起点和补充来源、技术作用、正向动机、反向教导、合理成功预期、证据状态及其所服务的 `CombinationPath`；缺失或为 `Q` 时，不得使组合路径获得确定性法律结论。

### 6C. 统一对象合同

本文件中的数组名称就是普通版 `v2.1-oa` 的唯一对象入口，不另建同义数组：

| 对象语义 | JSON数组 | 最小交接字段 |
|---|---|---|
| `OAIssue` | `office_action_issues` | `id`、`claim_version_id`、`assertion`、`evidence_paragraph_ids`、`difference_feature_ids`、`response_mode`、`fact_status`/`fact_audit_status` |
| `CombinationPath` | `combination_paths` | `id`、`claim_version_id`、起点/补充文献、`operations`、接口/参数条件、`fusion_feasible`、证据状态、生命周期 |
| `TeachingRecord` | `teaching_records` | `id`、服务路径、技术作用、正向动机、反向教导、合理成功预期、证据状态 |
| `EffectEvidenceCard` | `effect_evidence_cards` | `id`、`claim_version_id`、效果文本、因果链、比较基准、来源文件/日期、范围覆盖、事实状态、生命周期 |
| `ResponseEvent` | `response_trace` | `id`、问题集合、`claim_version_id`、证据回指、`response_mode`、生命周期 |
| `AmendmentEvent` | `claim_amendment_events` | `id`、旧/新权利要求ID、支持依据、目标问题、重算状态、生命周期 |
| `ClaimVersion` | `claims` | `id`、版本号、完整文本、特征组、`supersedes`（如有）、状态 |
| `AnalysisSnapshot` | `analysis_snapshots` | `id`、活动集合、路径、资格、主策略、`freeze_revision`、冻结状态、生命周期 |
| `DecisionTrail` | `decision_trails` | `id`、问题、答复/补正事件、决定事件、结果理由、闭合状态 |
| `SupportLink` | `support_links` | `id`、权利要求/版本、片段、说明书位置、关系类型、人工决定 |

所有对象必须保留稳定 `id`，并具有 `claim_version_id` 或 `issue_id`（按语义适用）、`source_refs`/`evidence_refs`、`fact_status` 和 `lifecycle_status`/`human_decision`。历史包缺少新增数组时按空数组读取；不得通过复制对象名称建立第二套合同。

## 7. 主修改策略与原子修改事务

`amendment_strategies` 的 `status` 取 `primary/candidate/blocked/superseded`。必须且只能有一个 `primary_strategy_id`；备选策略使用独立权利要求集合和快照，不得混入当前NB/IS、区别链或答复。

修改必须按以下顺序作为一个事务执行：

```text
新建CLM版本
→ 记录supersedes和支持依据
→ 使旧NB/IS/RT失效
→ 冻结新活动权利要求集合
→ 计算修改影响闭包
→ 重新生成TA
→ 重算全部受影响NB/IS
→ 切换response_trace
→ 通过recalculation_gate
```

修改影响闭包包括直接修改项、其全部引用后代，以及因编号、引用路径或保护主题改变而受影响的权利要求。修改支持为 `Q` 时策略只能是 `candidate/blocked`。

`claim_amendment_events` 应增加 `response_mode: "AmendmentBased"`、`old_claim_version_id`、`new_claim_version_id`、`support_evidence_ids`、`affected_combination_path_ids`、`invalidated_effect_evidence_card_ids` 和 `recalculation_status`。`response_trace` 的每个事件应增加 `response_mode`、`claim_version_id`、`oai_issue_id`、`combination_path_ids`、`effect_evidence_card_ids` 与 `decision_trail_id`；`ArgumentOnly` 事件不得改变活动权利要求集合。

## 8. NB/IS评价记录

每条活动权利要求的每条有效引用路径必须各有NB和IS记录，增加：

```json
{
  "path_id": "PATH-...",
  "assessment_mode": "full | inherited | no_separate_issue",
  "conclusion_status": "confirmed | conditional | undetermined",
  "snapshot_id": "SNAP-01",
  "lifecycle_status": "active | superseded | invalidated"
}
```

- `full`：针对完整展开对象进行完整评价；
- `inherited`：明确引用某一上位路径评价并补充本项新增限定；
- `no_separate_issue`：OA未对该路径单独争议，但仍记录其继承对象、证据资格和为什么无需独立展开。

每个NB仍只允许一个 `document_id`；新颖性不得多文献拼接。创造性候选文献必须在快照的 `inventive_step` 轴具备资格。

## 9. 决定性Q传播

| 决定性对象为Q | 强制结果 |
|---|---|
| 日期或法律资格 | 对应NB/IS `conclusion_status=undetermined`、`risk=undetermined` |
| NB覆盖特征 | 不得认定完整覆盖或明确不覆盖 |
| 修改支持 | 策略只能 `candidate/blocked` |
| 技术启示、动机、接口兼容或成功预期 | IS组合路径不得闭合 |
| 活动集合或主策略 | 不得产生活动快照，重算门失败 |

`Q` 不能被说明文字、风险字段、相似度、模型推断或一般常识补足。文献资格为 `conditional` 时结论至多为 `conditional`，不得为 `confirmed`。

## 10. 重算门

```json
"recalculation_gate": {
  "snapshot_id": "SNAP-01",
  "impact_claim_ids": ["CLM-NEW-01"],
  "impact_path_ids": ["PATH-CLM-NEW-01-SELF"],
  "expected_nb_keys": ["CLM-NEW-01::PATH-CLM-NEW-01-SELF"],
  "expected_is_keys": ["CLM-NEW-01::PATH-CLM-NEW-01-SELF"],
  "completed_nb_keys": ["CLM-NEW-01::PATH-CLM-NEW-01-SELF"],
  "completed_is_keys": ["CLM-NEW-01::PATH-CLM-NEW-01-SELF"],
  "response_trace_switched": true,
  "old_analysis_invalidated": true,
  "passed": true
}
```

阶段四定稿必须要求预期与完成集合相等、答复已切换、旧分析已失效。门禁未通过时，只能生成内部条件性草稿。

## 11. 就绪状态与标准交付

`readiness.content_status` 取 `pass/conditional/fail`；`submission_status` 取 `ready/blocked`。存在材料、日期、修改支持、范围取舍、期限、形式信息或客户确认阻塞时，不得标 `ready`。

验证器直接要求标准文件名 `00`—`09`、`run-metadata.json`，其中：

- `08-模型到答复追溯报告.md`
- `09-质量审计与提交状态.md`

运行：

```powershell
python scripts/validate_oa_delivery.py <run_dir> --report <run_dir>/validation.json
```

结构性判断只读取JSON；文本扫描仅用于对外答复内部ID和少量禁止措辞检查。
