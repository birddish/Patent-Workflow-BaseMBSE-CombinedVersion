# 撰写视图：精确渐进加载入口

本文件是人工可读的加载索引。机器规范源为：

- `references/routing/views/drafting.json`
- `references/routing/slice-profiles.json`
- `references/routing/rule-registry.json`

若本文件与上述 JSON 不一致，以 JSON 为准；本文件不定义新的 operation、别名或阶段。

## 合法路由

普通阶段只接受 `profile=standard`；受控权利要求核心路由只接受 `profile=controlled`。`phase` 必须使用机器配置中的下划线形式。

| submode | profile | phase | read_profile |
|---|---|---|---|
| `stage1` | `standard` | `stage_01` | `drafting.stage1` |
| `stage2` | `standard` | `stage_02` | `drafting.stage2` |
| `stage3` | `standard` | `stage_03` | `drafting.stage3` |
| `stage1_stage3_claim_core` | `controlled` | `stage_03` | `drafting.stage1_stage3_claim_core` |
| `stage4` | `standard` | `stage_04` | `drafting.stage4` |
| `stage5` | `standard` | `stage_05` | `drafting.stage5` |
| `stage6` | `standard` | `stage_06` | `drafting.stage6` |
| `stage7` | `standard` | `stage_07` | `drafting.stage7` |
| `stage8` | `standard` | `stage_08` | `drafting.stage8` |
| `stage9` | `standard` | `stage_09` | `drafting.stage9` |

`stage1_stage3_claim_core` 是机器合法的正式 `submode`，不是需要另行解释的自然语言别名。文档不登记 `stage1+stage3`、`claim_core` 等替代写法。

## 规则文件

### 普通阶段 `stage1`、`stage2`、`stage4`～`stage9`

每条普通阶段路由加载以下 4 个文件：

- 基础：`references/core/authority-and-status.md`
- 基础：`references/views/drafting/common-constraints.md`
- 基础：`references/views/drafting/drafting-guardrails.md`
- 当前阶段：
  - `stage1`：`references/views/drafting/stage-1-mbse-modeling.md`
  - `stage2`：`references/views/drafting/stage-2-search-and-comparison.md`
  - `stage4`：`references/views/drafting/stage-4-background-technology.md`
  - `stage5`：`references/views/drafting/stage-5-detailed-description.md`
  - `stage6`：`references/views/drafting/stage-6-figure-markdown.md`
  - `stage7`：`references/views/drafting/stage-7-vsdx-production.md`
  - `stage8`：`references/views/drafting/stage-8-existing-application-audit.md`
  - `stage9`：`references/views/drafting/stage-9-prosecution-handoff.md`

不得因阶段编号而加载其他阶段文件。各普通阶段的禁止组由机器配置逐条规定：

- `stage1`：`views/search`、`views/oa`、`drafting/stages/stage-02-through-09`
- `stage2`：`views/oa`、`drafting/stages/stage-03-through-09`
- `stage4`：`views/search`、`views/oa`、`drafting/stages/stage-05-through-09`
- `stage5`：`views/search`、`views/oa`、`drafting/stages/stage-06-through-09`
- `stage6`：`views/search`、`views/oa`、`drafting/stages/stage-07-through-09`
- `stage7`：`views/search`、`views/oa`、`drafting/stages/stage-08-through-09`
- `stage8`：`views/search`、`views/oa`、`drafting/stages/stage-09`
- `stage9`：`views/search`、`views/oa`

### `stage3 / standard / stage_03`

- 基础 3 个：`references/core/authority-and-status.md`、`references/views/drafting/common-constraints.md`、`references/views/drafting/drafting-guardrails.md`
- 当前阶段：`references/views/drafting/stage-3-claim-drafting.md`
- 必要例外：`references/views/drafting/protectable-unit-contract.md`、`references/views/drafting/claim-text-audit.md`、`references/views/drafting/dependent-claim-traceability.md`、`references/views/drafting/node-claim-mapping.md`
- 注册表展开总数：8 个；必要例外是阶段 3 的权利要求核心与追溯合同，不得继续叠加其他阶段。
- 禁止组：`views/search`、`views/oa`、`drafting/stages/stage-04-through-09`

### `stage1_stage3_claim_core / controlled / stage_03`

- 基础 3 个：`references/core/authority-and-status.md`、`references/views/drafting/common-constraints.md`、`references/views/drafting/drafting-guardrails.md`
- 阶段文件：`references/views/drafting/stage-1-mbse-modeling.md`、`references/views/drafting/stage-3-claim-drafting.md`
- 必要例外：`references/views/drafting/protectable-unit-contract.md`、`references/views/drafting/claim-text-audit.md`、`references/views/drafting/dependent-claim-traceability.md`、`references/views/drafting/node-claim-mapping.md`
- 注册表展开总数：9 个；不得加载阶段 2、阶段 4～9、检索或 OA 文件。
- 禁止组：`views/search`、`views/oa`、`drafting/stages/stage-04-through-09`
- 受控边界：`stage2=mocked_pass`、`allow_real_search=false`、`allow_oa=false`、`allow_legal_conclusion=false`、`release_grade_claim_text=false`。

## 写入与输出边界

- 所有路线写前缀均为：`/derived/drafting`
- 只返回当前阶段的候选/草案/审计对象、稳定 ID、Pointer、支持链、状态、输入 revision 和待确认项。
- 不写 MBSE、检索或 OA 业务结果；不把 `candidate`、`conditional`、`[Q]`、`blocked`、`mocked_pass` 表述为已证实法律结论。
- 先读对应 `read_profile` 的 JSON 投影，再读指定对象和证据闭包；不读取外部文件或完整案件 JSON。