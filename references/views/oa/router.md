# 答审/复审视图：精确渐进加载入口

本文件是人工可读的加载索引。机器规范源为：

- `references/routing/views/oa.json`
- `references/routing/slice-profiles.json`
- `references/routing/rule-registry.json`

若本文件与上述 JSON 不一致，以 JSON 为准；本文件不定义新的 operation、别名、版本或 phase。

## 合法路由

只有以下两种 `submode`：`opinion`、`reexamination`。二者均只接受 `profile=v2.1-oa`，且必须明文选择一个 `phase`：`phase_01`、`phase_02`、`phase_03`、`phase_04` 或 `phase_05`。

| submode | profile | phase | read_profile |
|---|---|---|---|
| `opinion` | `v2.1-oa` | `phase_01`～`phase_05` | `oa.opinion.{phase}` |
| `reexamination` | `v2.1-oa` | `phase_01`～`phase_05` | `oa.reexamination.{phase}` |

`{phase}` 只能展开为上述五个机器合法值。`v2.1-oa` 是当前机器 profile，不得省略或替换为其他版本。

## 规则文件

每个 phase 都有以下 6 个基础文件：

- `references/core/authority-and-status.md`
- `references/views/oa/general-workflow.md`
- `references/views/oa/intake-and-readiness-gates.md`
- `references/views/oa/version-and-recalculation-gates.md`
- `references/views/oa/evidence-and-inference-control.md`
- `references/views/oa/oa-evidence-pack-schema.md`

再按 phase 追加机器注册表指定的文件：

| phase | 追加文件 | 展开总数 |
|---|---|---:|
| `phase_01` | `references/views/oa/phase-1-mbse-modeling.md` | 7 |
| `phase_02` | `references/views/oa/phase-2-fact-audit.md` | 7 |
| `phase_03` | `references/views/oa/phase-3-traceability-analysis.md` | 7 |
| `phase_04` | `references/views/oa/phase-4-opinion-drafting.md`、`references/views/oa/oa-direct-content-rules.md` | 8 |
| `phase_05` | `references/views/oa/phase-5-opinion-audit.md`、`references/views/oa/output-checklist.md` | 8 |

因此 OA 当前无法真实压缩成 2–4 个直接规则文件；超出的 7–8 个是机器注册表已经强制要求的必要例外。除表内文件外，不得加载 MBSE、检索或撰写规则，也不得因 `opinion`/`reexamination` 切换而重复加载同一文件。

## 各 phase 最低输入

以下条件原样对应机器配置；缺少时返回 `blocked` 或 `pending_review`，不得自动改读外部材料：

- `phase_01`：`/normalized/documents`、`/normalized/issues` 或 `/source_materials/documents` 至少一项。
- `phase_02`：满足 `(/normalized/issues 或 /source_materials/documents)` 且 `/normalized/documents`。
- `phase_03`：同时具备 `/normalized/issues` 与 (`/normalized/claims` 或 `/derived/drafting`)。
- `phase_04`：同时具备 `/normalized/issues` 与 (`/normalized/claims` 或 `/derived/drafting`)。
- `phase_05`：`/derived/oa` 或 `/derived/drafting` 至少一项。

## 写入、禁止加载与输出边界

- 写前缀：`/derived/oa`
- 所有 phase 的禁止加载组：`views/mbse`、`views/search`、`views/drafting`
- 只输出当前答审/复审 phase 的问题、事实核验、追溯、意见、重算门和审计对象；输出包含稳定 ID、Pointer、状态、输入 revision 和证据引用。
- 不覆盖 `/derived/drafting` 的权利要求原始版本，不修改 MBSE/检索事实；跨视图输入只通过 JSON Pointer、对象 ID 和 revision 引用。
- 正文生成也只能读取主 `case.json` 的当前受控投影；不得回读 DOCX、PDF、图片、网页或 `source_path`。

兼容说明：`oa_response` 是 compat alias，仅允许由总控模式确认阶段规范化为 `opinion` 或 `reexamination`；它不是机器 `submode`，不能作为新的文档路由。