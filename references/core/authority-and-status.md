# 案件数据权威层与状态

只在模式确认通过且需要解释数据权威、证据或派生状态时加载。本文件不负责模式选择、视图业务规则或 Patch 提交。

## 单一数据入口

每个案件只有一个主 `case.json`。除 `bootstrap_import` 和用户明确确认的 `reimport_material` 外，任何计算、审计和导出只能读取该 JSON 的受控投影；`source_path`、URL 和其他 provenance 字段不得触发外部回读。

## 四层权威关系

| 层 | 内容 | 写入者 |
|---|---|---|
| `source_materials` | 导入快照、全文、片段、表格、图形/OCR、检索证据 | 导入事务 |
| `normalized` | 从导入快照提取并确认的规范化事实 | 规范化模块和用户确认 |
| `derived` | MBSE、检索、撰写、OA、无效答辩意见陈述、审计的可重算结果 | 对应视图 |
| `control` | 路由、revision、状态、索引、依赖、冲突和日志 | 总控 |

业务视图不得把推测或派生结果反写为已确认的 `normalized` 事实。审计只报告问题，不直接改写业务事实。

## 对象与状态

业务对象使用稳定 ID，并保存 `status`、`input_revision`、`dependency_ids`、`dependency_revisions`、`rule_version` 和 `computed_at`。不得把数组下标当作对象身份。

至少区分：

```text
fresh / stale / blocked / invalid
candidate / conditional / pending_review / [Q]
mocked_pass / pass
superseded / invalidated / deleted
```

结构校验、模拟门、候选和条件性分析不能表述为已核实事实、实体法律结论或可直接提交成果。

## 模型可见数据

模型只接收 RoutePlan 指定的 JSON 投影。默认排除 `raw_artifacts`、`content_base64`、完整历史日志和无关视图全文。需要全案检查时先由脚本遍历，再向模型返回异常、对象 ID 和必要证据摘录；不得把完整 `case.json` 原样送入上下文。

## 无效答辩视图的权威与结论边界

无效答辩属于独立业务视图，业务派生结果统一写入 `/derived/invalidity`。该视图只能从当前案件 `case.json` 的受控投影读取输入；`case_json_only` 下不得根据 `source_path`、URL、location 或其他 provenance 回读外部原件。只有已确认的 `bootstrap_import` 或 `reimport_material` 事务，才可按用户明文确认的文件清单读取外部材料并先写入案件 JSON。

无效答辩的材料准入、事实核实、MBSE 追溯、逐理由分析和意见陈述，都必须在 JSON 中保留来源片段、证据状态、权利要求特征映射、R/F/S/B/E 技术链和 response_round。技术链存在断点、证据不足、组合路径不连续或效果尚未证实，只能形成工程层面的 `candidate`、`conditional`、`pending_review` 或 `blocked` 状态；这些状态不自动转换为新颖性、创造性、支持、修改超范围等法律结论。法律结论必须以逐理由、逐权项、逐证据的核验记录为依据，并保留待人工确认事项。

Patch 只能修改 `/derived/invalidity`；不得修改 `/derived/oa`、`/derived/drafting`、`/derived/search`、`/derived/mbse`、`/normalized` 或 `/control`。引用其他视图对象时只记录稳定 ID、输入 revision 和依赖关系；跨视图失效由总控依赖机制处理。
