# 普通版答审模板注册表

适用内部视图：`答审/复审视图`  
适用合同：`v2.1-oa`

## 一、模板选择总则

先判断案件入口、答复模式和交付对象，再选择一个主模板。模板只规定正文结构，不替代阶段一至三的事实、技术和追溯链分析，也不放宽阶段零或阶段五的门禁。

同一份对外文书只能选择一个主模板：

```text
入口类型 + 答复模式 + 交付对象
→ 模板注册表
→ 对应模板
→ 阶段五审计
```

## 二、正式模板目录

| 模板 ID | 文件 | 使用条件 | 主要交付物 | 不得替代 |
|---|---|---|---|---|
| `EXT-OA-01` | `external/oa-response.md` | 入口是第几次审查意见通知书 | 审查意见答复正文 | 事实核实、版本重算和提交准入 |
| `EXT-REEXAM-01` | `external/reexamination-statement.md` | 入口是驳回决定或复审材料 | 驳回复审意见陈述书 | 驳回决定事实核对和复审请求程序判断 |
| `EXT-AMEND-01` | `external/amendment-explanation.md` | 需要单独说明权利要求修改 | 修改说明和原始支持说明 | `AmendmentBased` 的版本重算 |
| `INT-ISSUE-01` | `internal/intake-and-issue-matrix.md` | 尚未形成对外正文 | 案件准入表、问题—动作矩阵 | 对外法律文书 |
| `INT-EVIDENCE-01` | `internal/evidence-direct-content-sheet.md` | 需要整理直接原文和事实核对 | 直接内容证据表 | 对比文件完整案卷 |
| `INT-VERSION-01` | `internal/claim-version-recalculation-sheet.md` | 发生权利要求修改或版本替代 | 版本、影响闭包和重算登记 | 对外修改说明 |

## 三、选择规则

### 3.1 审查意见通知书

读取：

1. `oa-direct-content-rules.md`；
2. `internal/intake-and-issue-matrix.md`；
3. `internal/evidence-direct-content-sheet.md`；
4. `external/oa-response.md`；
5. `phase-5-opinion-audit.md` 和 `output-checklist.md`。

如果本轮采用 `AmendmentBased`，增加读取：

6. `internal/claim-version-recalculation-sheet.md`；
7. `external/amendment-explanation.md`。

### 3.2 驳回复审意见陈述书

读取：

1. `oa-direct-content-rules.md`；
2. `internal/intake-and-issue-matrix.md`；
3. `internal/evidence-direct-content-sheet.md`；
4. `external/reexamination-statement.md`；
5. `reexamination-opinion-framework.md`；
6. `phase-5-opinion-audit.md` 和 `output-checklist.md`。

如果复审阶段发生补正，增加读取：

7. `internal/claim-version-recalculation-sheet.md`；
8. `external/amendment-explanation.md`。

### 3.3 仅内部分析

当 OA、决定、权利要求或支持依据不完整时，不强行套用对外模板。先使用三个内部模板形成：

```text
材料准入
→ 问题—动作矩阵
→ 原文证据表
→ 版本与重算登记
```

只有在材料和门禁满足后，才读取外部模板形成对外稿；否则只能输出内部条件性稿。

## 四、统一正文原则

所有外部模板都遵守以下共同规则：

- 直接原文必须先于来源定位和分析出现；只有引用编号、页码、段落号、路径或文件名的段落属于 `citation-only` 违规；
- 第一节只说明本次答复所针对的审查意见/决定及发文日期，不展开无关案件背景；
- 每个具体问题必须直接写明问题内容，不能只用“问题一”“问题二”作为唯一标题；
- 每个问题依次说明审查意见、本申请文本、对比文件、审查员认知错误、申请人回应和处理结果；
- OA 答复和复审陈述书不设置独立的“当前权利要求文本”总览章节；
- `ArgumentOnly` 不制造修改后版本，只在相关问题下呈现所需的当前权利要求原文；
- `AmendmentBased` 对外正文只在相应问题下呈现修改后的权利要求和原始支持，修改前文本保留在内部版本登记中；
- 对外正文不得出现内部对象名、状态标签、数据集 ID、任务 ID 或 MBSE 内部符号；
- 原文、日期、支持依据、活动快照或重算门缺失时，保持 `Q`、`conditional` 或 `blocked`；
- 模板不自动生成 DOCX、PDF 或其他非文本文件，除非用户另行明确指定格式和操作。

统一正文形状为：

```text
答复对象（审查意见/决定次数或名称 + 发文日）
→ 问题标题
→ 审查意见/决定原文
→ 本申请文本原文
→ 对比文件原文
→ 审查员认知错误或论证缺口
→ 申请人回应/修改后的权利要求
→ 处理结果和待核验事项
```

## 五、领域规则的挂接方式

机械、生化/材料、电子通信/AI/软件不复制三套完整正文模板，而是挂接相应的论证参考：

| 主 mode | 读取的领域参考 | 重点呈现内容 |
|---|---|---|
| `mechanical` | `domain-argument-patterns-mechanical.md`、`domain-rules-mechanical.md` | 结构、连接、运动、位置、受力、支撑和锁止关系 |
| `biochemical` | `domain-argument-patterns-biochemical.md`、`domain-rules-biochemical.md` | 组分、比例、工艺顺序、温度、转速、相容性和范围边界 |
| `electronic-communication` | `domain-argument-patterns-electronic-communication.md`、`domain-rules-electronic-communication.md` | 输入数据、处理步骤、技术对象、输出数据和技术效果 |

领域参考改变论证内容，不改变外部模板的章节骨架。
