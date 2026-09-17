# 原文直接呈现规则与 JSON 内容读取规则

适用范围：普通版 `答审/复审视图` 的内部分析和对外答复。

## 一、核心规则

引用编号、文件名、路径和段落号只能帮助复核，不能代替案件内容。凡是影响事实认定、权利要求解释、对比文件公开范围、技术效果、组合路径或修改支持的材料，必须在同一问题单元中直接呈现足以理解论点的连续原文或实际字段内容。只有“见 D1 第 X 段”或只有来源编号而没有原文的写法，属于 `citation-only` 违规，不得进入对外稿。

每个实质问题固定采用：

```text
审查意见/决定原文
→ 本申请文本原文
→ 对比文件原文
→ 审查员认知错误的具体内容
→ 申请人回应或修改动作
→ 处理结果和待核验事项
```

不允许把以下内容作为完整事实依据：

```text
见 D1 第 0034 段。
见说明书第 12 页。
见权利要求 1。
详见前述证据。
```

## 二、摘录完整性

- 保留对象、限定条件、范围端点、步骤顺序、连接关系、否定表达和例外；
- 不能只摘录一个名词，再用自己的话补成完整技术方案；
- 可以只摘录与当前问题直接相关的完整句子或连续段落，不要求复制无关案卷；
- 省略号不能省略区别特征、范围端点、步骤关系或因果关系；
- 原文后必须紧跟对应分析，使读者不需要跳转到其他文件才能理解论点；
- 原文缺失时写“原文未提供/待核验”，保持 `Q` 或条件性，不补造事实。

### 2.1 原文与来源定位的顺序

每个实质性事实或法律论点必须遵循：

```text
直接原文
→ 原文说明或对应关系
→ 来源定位
→ 申请人分析和处理动作
```

来源定位不得出现在直接原文之前并代替原文。不得先写“D1 已公开”“审查员认为”“本申请限定了……”等结论，再只用编号证明。对比文件或申请文件只有部分原文时，只能对该部分作出判断，不得把摘要、事件说明、定位字段或模型概括扩展为未提供的全文事实。

### 2.2 输出级直接内容检查

生成每个问题单元后，必须检查：

- 审查意见/决定的关键认定后有直接原文；
- 被评价的权利要求或申请文件限定后有直接原文；
- 审查员实际引用的对比文件内容后有直接原文；
- 技术效果、范围、步骤顺序、组合路径和修改支持的每一项实质主张后有直接原文或明确的“原文未提供/待核验”；
- 不存在只有 `D1/D2`、页码、段落号、路径或文件名的实质性事实段落；
- `ArgumentOnly` 没有单独生成“修改后权利要求”章节；
- `AmendmentBased` 的修改后权利要求直接出现在相应问题单元，且重算门已通过，否则只输出内部条件性稿。

任一项不满足时，对外正文不得标记为内容完整或可提交。

## 三、JSON-only 字段读取

当输入来自本项目自包含 JSON 时，只读取 JSON 内的实际内容字段：

- OA 和答复：`office_action_text`、`rebuttal_text`、`next_office_action_text`；
- 权利要求：`application_claims`、`claim_texts`；对象数组中的 `text` 才是直接文本；
- 对比文件：`prior_art_summaries` 中已经嵌入的实际摘要或原文；
- 技术关系：`technical_model`、`claim_mappings`、`support_links`；
- 版本和事件：`claim_versions`、`version_events`、`response_events`、`decision_trail`；
- 状态和门禁：`expected_extraction`、`expected_strategy`、`oa_context`、`candidate_answer_objects`、`version_recalculation`、`v21_contract`。

以下字段只用于溯源或治理，不得单独作为案件事实：

```text
path
location
source_file
source_ref
source_trace
数据集 ID
任务 ID
申请号样式
案例编号
```

## 四、对外稿与内部稿分离

内部稿可以保留 `OAIssue`、`CombinationPath`、`EffectEvidenceCard`、`ResponseEvent`、`AmendmentEvent`、`ClaimVersion`、`DecisionTrail`、`Q` 和门禁状态。

对外稿必须把这些对象转换为完整的技术和法律语言，不得出现内部对象名、内部 ID、`R/F/S/B/E`、`D/I/Q/X`、数据集标签或模型评分，但不得因此删除必要的原文。

## 五、权利要求版本规则

### `ArgumentOnly`

- 不创建新的权利要求版本；
- 不写“修改后权利要求”；
- 只直接呈现当前问题所必需的相关权利要求原文；
- 只处理事实认定、区别特征、技术效果、组合路径或技术启示。

### `AmendmentBased`

- 必须直接呈现修改后的权利要求；
- 必须核验原始支持；
- 必须使旧 NB/IS/ResponseTrace 失效；
- 必须重新冻结活动权利要求集合和分析快照；
- 必须完成影响闭包和 NB/IS 重算；
- 重算门未通过时只能输出内部条件性稿。

## 六、模板入口

具体正文模板不在本文件重复，按 `templates/template-registry.md` 选择：

- OA 答复：`templates/external/oa-response.md`；
- 复审意见陈述书：`templates/external/reexamination-statement.md`；
- 权利要求修改说明：`templates/external/amendment-explanation.md`；
- 内部问题矩阵：`templates/internal/intake-and-issue-matrix.md`；
- 内部直接内容证据表：`templates/internal/evidence-direct-content-sheet.md`；
- 内部版本重算表：`templates/internal/claim-version-recalculation-sheet.md`。

对外 OA 答复和复审意见陈述书默认采用“答复对象说明 → 具体问题单元 → 结论和请求”的结构，不设置独立的当前权利要求总览章节。专门说明 `AmendmentBased` 修改时，`external/amendment-explanation.md` 可以单独呈现修改后的权利要求，但这不改变版本重算和提交准入门。
