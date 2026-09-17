# 原文直接呈现模板兼容入口

本文件保留原有引用路径，避免旧任务找不到入口。正式模板已经拆分，不应在本文件中继续寻找完整正文。

## 正式模板

请先读取 `templates/template-registry.md`，再根据案件入口选择唯一主模板：

- 审查意见答复：`templates/external/oa-response.md`；
- 驳回复审意见陈述书：`templates/external/reexamination-statement.md`；
- 权利要求修改说明：`templates/external/amendment-explanation.md`；
- 内部准入和问题矩阵：`templates/internal/intake-and-issue-matrix.md`；
- 内部直接内容证据表：`templates/internal/evidence-direct-content-sheet.md`；
- 内部版本与重算登记：`templates/internal/claim-version-recalculation-sheet.md`。

## 统一直接内容要求

所有正式模板都必须遵守：

```text
审查意见/决定原文
→ 本申请文本原文
→ 对比文件原文
→ 审查员认知错误的具体内容
→ 申请人回应或修改动作
→ 处理结果和待核验事项
```

引用编号、路径、文件名、`source_ref` 和 `source_trace` 只能用于复核，不能替代原文。原文未提供时，必须写“原文未提供/待核验”，保持 `Q`、`conditional` 或 `blocked`。

详细的 JSON-only 字段读取、摘录完整性、`ArgumentOnly`/`AmendmentBased` 分流规则见 `oa-direct-content-rules.md`。
