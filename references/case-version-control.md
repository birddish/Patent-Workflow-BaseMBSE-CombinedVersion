# 版本、失效、冲突与恢复

## revision 与派生状态

主 JSON 的 `control.current_revision` 为非负递增整数。每次成功提交 Patch 只递增一次；失败事务不能改变它。派生对象保存 `input_revision`、`dependency_ids`、`dependency_revisions` 和 `rule_version`，输入对象变化时只将依赖闭包中的对象标记为 `stale` 或 `invalid`。

固定依赖方向：

```text
source_materials → normalized → mbse
                              ├→ search
                              ├→ drafting → oa
                              │           └→ invalidity
                              ├→ invalidity
                              └→ audit
```

审查意见导入只影响引用这些意见的 OA 对象；活动权利要求版本变化影响相应 OA 映射；未受影响对象保持 `fresh`。缺少必需输入、引用断裂或规则版本不可用时使用 `blocked`/`invalid`，不能自动全案重算。

无效请求、补充理由或请求人证据的新导入批次只使引用这些材料的 `derived.invalidity` 对象及其依赖闭包失效，不应无条件使 OA 对象失效。活动权利要求版本改变时，相应无效理由—权项映射、特征对照和答辩稿进入 `stale`，未受影响对象保持原状态。无效检索属于 `derived.search`，其结果须先导入 JSON，且不会自动转成无效答辩结论。

## 事务状态

事务记录至少含 `transaction_id`、`kind`、`status`、`base_revision`、`actor`、`started_at`、`finished_at` 和错误/影响信息。状态可为 `pending`、`processing`、`awaiting_confirmation`、`committed`、`aborted`、`conflict`。

## 冲突与恢复

- Patch 的 `base_revision` 不是当前 revision 时拒绝直接合并，写入 `control.conflicts`，状态为 `conflict`；
- 同一路径发生并发修改时不做静默 last-write-wins；需重新读取 L0/L1、重新计算影响集并生成新的 Patch；
- 提交器先写同目录临时文件，完整 JSON 校验通过后原子替换；失败时保留原文件；
- 恢复优先使用最近一次 `committed` 版本或明确的备份快照；恢复动作也必须产生新事务和新 revision；
- 历史对象保留 `superseded` 或 `invalidated`，逻辑删除保留删除人、时间、原因和替代对象。

## 访问审计

每次读取记录 `transaction_id`、`actor`、`read_level`、JSON Pointer 路径、对象 ID、`revision`、是否命中外部读取阻断和时间。`case_json_only` 的访问日志中不得出现外部文件读取事件；出现即视为测试失败。
