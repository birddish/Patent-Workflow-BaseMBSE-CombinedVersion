# 检索视图：精确渐进加载入口

本文件是人工可读的加载索引。机器规范源为：

- `references/routing/views/search.json`
- `references/routing/slice-profiles.json`
- `references/routing/rule-registry.json`

若本文件与上述 JSON 不一致，以 JSON 为准；本文件不定义新的 operation、别名或路由。

## 合法路由

检索只有以下四种 `submode`：`novelty`、`invalidity`、`FTO`、`landscape`。每种均只接受 `phase=search`，并且必须明文选择一个 `profile`：`quick`、`standard` 或 `formal`。

| submode | profile | read_profile | 最低输入 |
|---|---|---|---|
| `novelty` | `quick` / `standard` / `formal` | `search.novelty.{profile}` | `/normalized/technical_facts` 或 `/normalized/claims` 或 `/derived/mbse` |
| `invalidity` | `quick` / `standard` / `formal` | `search.invalidity.{profile}` | 同时具备 `/normalized/claims` 与 (`/source_materials/search_results` 或 `/derived/search`) |
| `FTO` | `quick` / `standard` / `formal` | `search.fto.{profile}` | `/normalized/claims`、`/normalized/entities` 或 `/normalized/technical_facts` |
| `landscape` | `quick` / `standard` / `formal` | `search.landscape.{profile}` | `/normalized/technical_facts` 或 `/normalized/entities` |

`{profile}` 必须在上表的三个机器合法值中展开；不得写成未注册的其他 profile。

## 规则文件

每一行均使用同一结构：基础规则文件 3 个，模式文件 1 个，交付 profile 文件按下表追加。规则注册表展开后的超出部分是必要例外，必须保持精确清单，不得再追加其他视图规则。

### 基础文件（每条路由必需）

- `references/core/authority-and-status.md`
- `references/views/search/search-guide.md`
- `references/views/search/cn-search-guide.md`

### 模式文件（按 `submode` 选择 1 个）

- `novelty`：`references/views/search/mode-novelty.md`
- `invalidity`：`references/views/search/mode-invalidity.md`
- `FTO`：`references/views/search/mode-fto.md`
- `landscape`：`references/views/search/mode-landscape.md`

### profile 文件（按 `profile` 选择）

- `quick`：`references/views/search/delivery-profiles.md`
- `standard`：`references/views/search/delivery-profiles.md`、`references/views/search/review-prompt.md`
- `formal`：`references/views/search/delivery-profiles.md`、`references/views/search/review-prompt.md`、`references/views/search/handoff-templates.md`

因此机器注册表当前展开为：`quick=5` 个、`standard=6` 个、`formal=7` 个直接规则文件。相对 2–4 个文件目标，超出部分仅由上述模式文件和交付文件构成必要例外；不得把它解释为可以加载整套检索资料。

## 写入、禁止加载与输出边界

- 写前缀：`/derived/search`
- 禁止加载组：`views/oa`、`views/drafting/stages/stage-04-through-09`
- `quick` 只形成候选、查询块、筛选记录和风险提示；不得输出确定性法律结论。
- `standard` 可形成可定位文献证据和内部比较结果；结论仍受证据状态和覆盖范围约束。
- `formal` 只有在用户明文选择后，才可加载 `handoff-templates.md` 并形成正式检索交接结构。
- `FTO` 的地域范围与文献覆盖必须分别记录；`landscape` 不生成 Claim Chart，也不借此产生法律状态结论。
- 所有输出只能落入 `/derived/search`，以稳定 ID、JSON Pointer、证据状态、输入 revision 和覆盖限制表达；不得写入 MBSE、撰写或 OA 结果。

## 读取边界

先读取 L0，再按 `read_profile` 读取当前模式所需 Pointer、指定文献对象和有限证据闭包。禁止回读外部 `source_path`、完整 `source_materials`、完整 `normalized`、完整 `derived` 或 `raw_artifacts`。外部检索结果必须先导入主 JSON，随后检索分析只能从 JSON 读取。

本文不登记兼容别名。`FTO` 的大小写以机器配置为准。