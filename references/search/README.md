# 检索视图入口

唯一路由文档：[router.md](router.md)。机器规范源：[search.json](../../routing/views/search.json)、[slice-profiles.json](../../routing/slice-profiles.json) 和 [rule-registry.json](../../routing/rule-registry.json)。

合法组合为：

| submode | profile | phase |
|---|---|---|
| `novelty`、`invalidity`、`FTO`、`landscape` | `quick`、`standard`、`formal` | `search` |

实际 `read_profile`、规则文件、禁止加载组和输出限制以 `router.md` 为准。所有检索结果先进入主 `case.json`，分析只读受控 JSON 切片，只写 `/derived/search`。不使用未登记别名；`FTO` 大小写保持机器配置形式。