# MBSE 视图入口

唯一路由文档：[router.md](router.md)。机器规范源：[mbse.json](../../routing/views/mbse.json)、[slice-profiles.json](../../routing/slice-profiles.json) 和 [rule-registry.json](../../routing/rule-registry.json)。

合法组合只有：

| submode | profile | phase | read_profile |
|---|---|---|---|
| `disclosure` | `standard` | `modeling` | `mbse.disclosure.standard` |
| `document` | `standard` | `modeling` | `mbse.document.standard` |
| `search` | `standard` | `modeling` | `mbse.search.standard` |

按 `router.md` 选一个组合后，只读取该 profile 和注册表展开的规则文件；只写 `/derived/mbse`。不得把 MBSE `search` 与检索视图 `search` 混同，也不在本 README 增加别名或 operation。