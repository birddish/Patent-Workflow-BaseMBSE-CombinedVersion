# MBSE 视图：精确渐进加载入口

本文件是人工可读的加载索引。机器规范源为：

- `references/routing/views/mbse.json`
- `references/routing/slice-profiles.json`
- `references/routing/rule-registry.json`

若本文件与上述 JSON 不一致，以 JSON 为准；本文件不定义新的 operation、别名或路由。

## 合法路由

MBSE 只有以下三种 `submode`；三者均只接受 `profile=standard`、`phase=modeling`。

### `disclosure / standard / modeling`

- `read_profile`：`mbse.disclosure.standard`
- 最低输入：`/normalized/technical_facts` 或 `/source_materials/documents`
- 基础规则文件（3 个）：
  - `references/core/authority-and-status.md`
  - `references/views/mbse/mbse-framework.md`
  - `references/views/mbse/unified-evidence-rules.md`
- 必要例外文件（注册表强制追加 2 个）：
  - `references/views/mbse/modes/mode-disclosure.md`
  - `references/views/mbse/patent-evidence-pack.md`
- 写前缀：`/derived/mbse`
- 禁止加载组：`views/search`、`views/drafting`、`views/oa`
- 输出边界：仅输出 MBSE 交底模型、证据状态和候选对象的 ID、Pointer、状态及本次计算元数据；不得写入其他视图。

### `document / standard / modeling`

- `read_profile`：`mbse.document.standard`
- 最低输入：`/normalized/documents` 或 `/source_materials/documents`
- 基础规则文件（3 个）：
  - `references/core/authority-and-status.md`
  - `references/views/mbse/mbse-framework.md`
  - `references/views/mbse/unified-evidence-rules.md`
- 必要例外文件（注册表强制追加 3 个）：
  - `references/views/mbse/modes/mode-document.md`
  - `references/views/mbse/document-comparison-guide.md`
  - `references/views/mbse/claim-semantic-bridge.md`
- 写前缀：`/derived/mbse`
- 禁止加载组：`views/search`、`views/drafting`、`views/oa`
- 输出边界：仅输出文件模型、对比/追溯桥接和证据包所需的 MBSE 对象；不得生成检索、权利要求或答审正文。

### `search / standard / modeling`

- `read_profile`：`mbse.search.standard`
- 最低输入：`/normalized/technical_facts`、`/normalized/entities` 或 `/derived/mbse`
- 基础规则文件（3 个）：
  - `references/core/authority-and-status.md`
  - `references/views/mbse/mbse-framework.md`
  - `references/views/mbse/unified-evidence-rules.md`
- 必要例外文件（注册表强制追加 3 个）：
  - `references/views/mbse/modes/mode-search.md`
  - `references/views/mbse/search-bridge-guide.md`
  - `references/views/mbse/claim-semantic-bridge.md`
- 写前缀：`/derived/mbse`
- 禁止加载组：`views/search`、`views/drafting`、`views/oa`
- 输出边界：仅输出 F/S/B 轻量检索模型、桥接关系和对象引用；不执行 `search` 视图的 novelty、invalidity、FTO 或 landscape 分析。

## 统一执行边界

1. 先由总 Skill 完成明文事务、视图和子模式确认，再按上表选择一个 `read_profile`；不得并行加载三个 MBSE mode 文件。
2. 规则文件数量以注册表展开结果为准。上表的“必要例外”不是新路由，也不得在其上继续叠加其他视图规则。
3. 读取只取对应 profile 的 JSON Pointer 和必要对象闭包；不得回读 `source_path`、完整案件 JSON、其他视图根节点或 `raw_artifacts`。
4. 所有写入必须通过版本化 Patch；只能写 `/derived/mbse`，并保留稳定实体 ID、`input_revision`、依赖和状态。
5. 本文不登记兼容别名。任何旧输入如需兼容，只能由总控模式确认器规范化为上述机器合法值，不能成为文档路由。