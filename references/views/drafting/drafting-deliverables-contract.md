# 撰写视图阶段交付契约

本文件把撰写视图的 JSON 数据层与用户可见阶段交付层连接起来。

## 1. 权威关系

案件主 JSON 是唯一权威数据源，路径为：案件目录/case.json。
阶段交付文件是从当前 JSON revision 导出的人工可读投影，不是新的事实来源。每个交付文件必须登记到 control.deliverables，并绑定生成时的 revision、阶段、视图和来源路径。
Skill 源稿目录不保存具体案件的 case.json、权利要求草案或说明书草案。

## 2. 案件目录

案件目录应包含：

- case.json
- deliverables/00-intake/
- deliverables/01-technical-facts/
- deliverables/02-mbse-model/
- deliverables/03-claim-core/
- deliverables/04-claim-branches/
- deliverables/05-specification-outline/
- deliverables/06-specification-draft/
- deliverables/07-figures-and-consistency/
- deliverables/08-drafting-audit/
- deliverables/09-final-export/
- patches/
- snapshots/

## 3. 事务前置条件

每次撰写操作必须：

1. 要求用户明文确认事务模式和目标阶段；
2. 定位案件目录和 case.json；
3. 读取 L0 索引、当前 revision、阶段状态、待确认事项和交付物登记；
4. 根据当前 JSON 判断推荐阶段；
5. 如果用户选择与 JSON 状态不一致，先向用户提出质疑，不得直接执行；
6. 仅读取当前阶段允许的 JSON 路径；
7. 生成并校验带 base_revision 的 Patch；
8. Patch 原子写回成功后，才生成阶段交付文件。

普通的“继续”“刷新”“重算”不得解释为重新导入外部材料。

## 4. 交付物登记

control.deliverables 中的每个条目至少包含：

- deliverable_id
- stage
- view
- type
- path
- source_revision
- source_object_paths
- status
- human_review
- content_scope
- generated_at

交付物状态至少包括：planned、generating、generated、review_pending、accepted、stale、superseded、blocked、failed。
来源对象发生变化时，受影响交付物必须标记为 stale 或 superseded。

## 5. 撰写阶段交付矩阵

### 00：导入和撰写模式确认

JSON 路径：source_materials、normalized、control.transaction、control.navigation。
最低交付文件：

- deliverables/00-intake/intake-summary.md
- deliverables/00-intake/selected-writing-mode.md
- deliverables/00-intake/pending-questions.md

必须记录用户明文选择、AI 推荐、二者是否一致和最终确认状态。

### 01：技术事实整理

JSON 路径：normalized.technical_facts、normalized.terminology、normalized.constraints。
最低交付文件：

- deliverables/01-technical-facts/technical-facts.md
- deliverables/01-technical-facts/confirmed-facts.md
- deliverables/01-technical-facts/pending-facts.md
- deliverables/01-technical-facts/terminology-table.md

### 02：MBSE 模型和保护链

JSON 路径：derived.mbse。
最低交付文件：

- deliverables/02-mbse-model/mbse-model-summary.md
- deliverables/02-mbse-model/protection-chain.md
- deliverables/02-mbse-model/evidence-chain.md
- deliverables/02-mbse-model/protection-candidates.md

若本阶段仍为模拟门，文件必须标注 mocked_pass，不得表述为专利性法律结论。

### 03：权利要求核心

JSON 路径：derived.drafting.claims、claim_versions、protection_units、support_links、claim_paths。
最低交付文件：

- deliverables/03-claim-core/claim-core-draft.md
- deliverables/03-claim-core/independent-claim-candidates.md
- deliverables/03-claim-core/necessary-features.md
- deliverables/03-claim-core/claim-source-traceability.md
- deliverables/03-claim-core/claim-core-review.md

### 04：从属项和回退路径

JSON 路径：derived.drafting.dependent_claim_branches、fallback_routes、claim_paths。
最低交付文件：

- deliverables/04-claim-branches/claim-tree.md
- deliverables/04-claim-branches/dependent-claim-candidates.md
- deliverables/04-claim-branches/fallback-routes.md
- deliverables/04-claim-branches/branch-support-matrix.md

### 05：说明书提纲

JSON 路径：derived.drafting.specification_outline、claim_support_map。
最低交付文件：

- deliverables/05-specification-outline/specification-outline.md
- deliverables/05-specification-outline/claim-support-matrix.md
- deliverables/05-specification-outline/embodiment-plan.md
- deliverables/05-specification-outline/section-missing-items.md

### 06：说明书正文

JSON 路径：derived.drafting.specification_sections、embodiments、terminology。
最低交付文件：

- deliverables/06-specification-draft/specification-draft.md
- deliverables/06-specification-draft/embodiments.md
- deliverables/06-specification-draft/terminology-list.md
- deliverables/06-specification-draft/claim-to-specification-trace.md

### 07：附图、标号和一致性

JSON 路径：derived.drafting.figures、reference_numbers、terminology_consistency。
最低交付文件：

- deliverables/07-figures-and-consistency/figures-description.md
- deliverables/07-figures-and-consistency/reference-number-table.md
- deliverables/07-figures-and-consistency/figure-text-map.md
- deliverables/07-figures-and-consistency/terminology-consistency.md

### 08：撰写审计

JSON 路径：derived.drafting.claim_text_audits、derived.audit。
最低交付文件：

- deliverables/08-drafting-audit/claim-text-audit.md
- deliverables/08-drafting-audit/support-audit.md
- deliverables/08-drafting-audit/terminology-audit.md
- deliverables/08-drafting-audit/dependency-audit.md
- deliverables/08-drafting-audit/missing-feature-audit.md
- deliverables/08-drafting-audit/blocking-items.md

### 09：从 JSON 导出当前撰写交付包

输入只能是当前版本的 case.json。
最低交付文件：

- deliverables/09-final-export/claims-draft.md
- deliverables/09-final-export/specification-draft.md
- deliverables/09-final-export/abstract-draft.md
- deliverables/09-final-export/drawings-description.md
- deliverables/09-final-export/drafting-delivery-summary.md
- deliverables/09-final-export/unresolved-items.md

最终只表示当前案件版本下的候选交付包，不自动表示可以提交或已经形成法律结论。

## 6. 生成顺序

每次阶段事务必须遵循：用户确认模式和阶段 → 读取 JSON 切片 → 生成业务结果 → 生成并校验 Patch → 原子写回 case.json → 从写回后的 JSON 生成当前阶段文件 → 登记 control.deliverables → 返回 revision、文件路径、状态和待确认事项。

Patch 写回失败时，不得登记成功交付物。文件生成失败时，应登记为 failed，不得把阶段报告为完成。

## 7. 人工修改交付文件

用户直接修改阶段 Markdown 后，系统不得自动将其视为案件事实变化。用户必须明确选择：

- A：将人工修改重新导入 case.json；
- B：仅保留为外部参考版本；
- C：与当前 JSON 版本比较后生成 Patch。

只有 A 或 C 通过版本、字段权限和引用校验后，修改才进入案件主 JSON。
