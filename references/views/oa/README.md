# 答审/复审视图入口

唯一路由文档：[router.md](router.md)。机器规范源：[oa.json](../../routing/views/oa.json)、[slice-profiles.json](../../routing/slice-profiles.json) 和 [rule-registry.json](../../routing/rule-registry.json)。

合法组合为：

| submode | profile | phase |
|---|---|---|
| `opinion`、`reexamination` | `v2.1-oa` | `phase_01`～`phase_05` |

具体 `read_profile`、各 phase 的规则文件、最低输入、禁止加载组和输出边界以 `router.md` 为准。所有答审/复审写入只能落在 `/derived/oa`，不使用 `oa_response` 等未登记 submode。