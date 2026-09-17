# Patch、所有权与提交门

只在当前事务可能写回 `case.json` 时加载。纯状态查看和不写回的读取任务不加载本文件。

## 唯一写入方式

业务模块不得整文件覆盖 `case.json`。已有案件的新增、修改、逻辑删除、状态变化、重新导入和失效传播都通过带 `base_revision` 的 Patch 信封及统一提交器提交。首次导入只在目标不存在时允许创建型 Patch 例外：仍需确认、候选校验和排他原子创建。`export_from_json` 是只读事务，严禁 Patch 写回。

## 写入边界

| actor/view | 允许路径 |
|---|---|
| 导入/规范化 | `/source_materials`、导入态 `/normalized`、导入事务控制字段 |
| `mbse` | `/derived/mbse` |
| `search` | `/derived/search` |
| `drafting` | `/derived/drafting` |
| `oa` | `/derived/oa` |
| `invalidity` | `/derived/invalidity` |
| `audit` | `/derived/audit` |
| 总控 | `/control` 和事务状态 |

视图不得越权写入其他视图、来源快照或规范化事实。

## 提交门

提交前依次检查：

1. 模式确认仍对当前 revision 和 route scope 有效；
2. `base_revision` 等于 `control.current_revision`；
3. Patch 路径符合字段所有权；
4. Schema、稳定 ID、引用闭合和状态转换有效；
5. 影响集可解释，并只标记依赖闭包中的对象；
6. 用户已确认本次 Patch 预览；
7. 临时文件完整校验通过后再原子替换；
8. 成功后只递增一次 revision，并记录事务和变更摘要。

失败时不得部分写回。旧 revision、并发路径冲突或确认失效时返回 `conflict`/`blocked`，重新读取最小投影并生成新 Patch；不得静默 last-write-wins。

逻辑删除保留删除人、时间、原因和替代对象；仍被历史引用的对象不得物理删除。
