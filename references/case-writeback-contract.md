# Patch、字段所有权与写回合同

## Patch 信封

已有案件的一切业务修改与 `reimport_material` 必须使用如下信封并经统一提交器写回；首次建案是仅限目标不存在的创建型 Patch 例外，仍需显式信封、候选 Schema 校验、用户确认和排他原子创建。`export_from_json` 永远只读，不能提交 Patch：

```json
{
  "patch_id": "PATCH-0007",
  "case_id": "CASE-001",
  "base_revision": 12,
  "confirmation_id": "CONF-0007",
  "transaction": "case_json_only",
  "view": "drafting",
  "operation": "add_claim_candidate",
  "actor": "agent",
  "reason": "根据已确认的 CHAIN-002 生成从属项候选",
  "operations": [{"op": "add", "path": "/derived/drafting/claims/-", "value": {"id": "CLM-018", "status": "candidate", "input_revision": 12, "dependency_ids": ["CHAIN-002"], "dependency_revisions": {"CHAIN-002": 12}, "rule_version": "drafting-1", "computed_at": "2026-09-16T00:00:00Z"}}],
  "expected_affected_entities": ["CLM-018"]
}
```

`path` 使用 JSON Pointer。数组项必须由稳定 `id` 定位；提交器可以将带稳定 ID 的对象追加到数组，但不得把数组下标当作唯一身份。支持的最小操作为 `add`、`replace`、`remove`、`test`；逻辑删除优先使用 `status=deleted` 或 `deleted_at/deleted_by/reason/replacement_id`，不物理删除仍被历史引用的对象。

## 字段所有权

| 写入者 | 允许写入 | 禁止写入 |
|---|---|---|
| 导入/规范化 | `source_materials`、导入态 `normalized`、导入事务控制字段 | 任何视图派生业务结果 |
| MBSE | `/derived/mbse` | 技术事实原文、检索、撰写、OA |
| 检索 | `/derived/search` | MBSE 原始事实、撰写、OA |
| 撰写 | `/derived/drafting` | MBSE 原始事实、检索、OA |
| 答审/复审 | `/derived/oa` | 撰写原始权利要求、MBSE、检索 |
| 无效答辩意见陈述 | `/derived/invalidity` | `source_materials`、`normalized` 及经 JSON 导入的 MBSE/检索/撰写投影；不得写 `/derived/oa` 或 `/control` |
| 审计 | `/derived/audit` | 业务事实和其他视图结果 |
| 总控 | `/control`、事务状态 | `source_materials`、`normalized`、各视图业务结果 |

## 提交前九项检查

1. `base_revision` 等于当前 revision；
2. 权威 route_confirmation 的 confirmation_id、案件 ID、当前 revision 和完整 canonical 路由均匹配，并取得本次明确写回确认；
3. `view` 与所有操作路径所有权一致；
4. Schema 和字段类型有效；
5. 新对象 ID 稳定、唯一且不复用；
6. 引用闭合且未引用逻辑删除对象；
7. 状态转换合法；
8. expected_affected_entities 覆盖直接影响实体；提交门必须计算依赖闭包，在同一原子事务中使受影响的下游派生对象进入 stale/invalid，不能仅输出建议而留下 fresh；
9. 原子写回成功后再记录 committed 日志。

失败时不得部分写回；返回 `blocked` 或 `conflict`，保留错误路径和修复建议。

## 无效答辩视图的专用边界

无效答辩使用 `view=invalidity`、`submode=defense`、`profile=v2.1-invalidity`，阶段为
`phase_01` 至 `phase_05`：材料准入、事实核实、MBSE 追溯与逐理由分析、答辩意见起草、交付前核对。
首次答辩、补充答辩通过 `/derived/invalidity/response_rounds` 中的稳定
`response_round_id` 区分；不得为答辩轮次另造 submode。

该视图的业务 Patch 只能写 `/derived/invalidity` 及其子路径。即使对象携带 OA、撰写或检索引用，
也只能作为 `dependency_ids` 或证据/输入引用，不能修改被引用视图的对象。`control` 由总控事务更新，
不得由 invalidity Patch 直接写入。

无效请求、请求人证据、补充理由、活动权利要求版本、既往意见和专利权人证据的材料角色，必须在
`source_materials` 的导入批次/文档/证据记录中保留，并由 `/normalized` 中的确认事实引用；
答辩轮次和逐理由分析的派生记录只落在 `/derived/invalidity`。只有当前路由明确为
`bootstrap_import` 或 `reimport_material`，并且用户明文确认了文件清单、导入策略和旧批次处理方式，
才允许读取外部文件；`case_json_only` 下不得依据 `source_path`、`location` 或其他 provenance 回读原件。
