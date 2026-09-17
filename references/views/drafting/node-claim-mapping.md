# MBSE—保护单元—权利要求—申请文件映射规则

本文件适用于阶段1至阶段5和阶段8。对象与状态定义以`protectable-unit-contract.md`为准。

## 一、符号定义

| 符号 | 含义 |
|---|---|
| `CF` | Claim Feature，权利要求中的原子技术特征 |
| `REL` | Relation，结构连接、输入输出、先后、触发、反馈等必要关系 |
| `CT` | Constraint，材料、数值、几何、时序、阈值或逻辑约束 |
| `INT` | Integration，不可任意拆分且共同产生技术作用的组合单元 |
| `DepPath` | 以独立权利要求为根、终止于从属权利要求的合法引用路径集合 |
| `ΔSem` | 从属权利要求相对直接上位权项新增或细化的CF/REL/CT/INT |
| `Sem_eff` | 沿某一合法引用路径累计继承后的完整权利要求语义 |
| `ΔT` | 从属权利要求相对直接上位权项的增量追溯子网络 |
| `Bridge` | 增量子网络与继承网络之间的`refine/allocate/flow/trigger/guard/contributes-to`关系 |
| `ClaimTextAudit` | 权利要求要素、关系、依存、术语、清楚性、支持、效果和修改一致性的技术审计对象 |
| `ConceptRelationAudit` | 上下位/细化/收窄/组成/实现关系、替换测试、效果依赖、支持范围和权利要求落位的审计对象 |
| `SupportLink` | 权利要求片段与说明书/附图/实施例支持位置的关系记录 |

CHAIN、PU、PST、CTX、STATE、IF、CV和IU的定义见对象合同，不在本文件重复定义。

## 二、映射状态边界

映射状态仅使用`一致/待回写/已回写/例外确认`，只描述模型、权利要求和申请文件的一致性。它不得替代：

- 阶段状态：草稿、待确认、确认、退回修订、已替代；
- `fact_status`和`drafting_status`；
- `technical_closure/source_maturity/text_location_maturity/legal_evidence_maturity/search_maturity/drafting_admission`。

`C_v`在本文件表示固定的技术分析对象；第六章的`ClaimVersion`才表示治理层版本对象。不得用版本治理字段改变`Sem(C_v)`、`DepPath`或`Sem_eff`的业务含义。

## 三、四层映射账本

```text
MBSE节点/关系
→ CHAIN/PU/PST/CTX
→ ConceptRelationAudit
→ CF/REL/CT/INT
→ 不限项母版及提交候选版权项
```

| 映射ID | MBSE节点/关系及类型 | 原始证据 | CHAIN | PU/PST/CTX | CF/REL/CT/INT及聚合号 | 转换方式 | 母版权项 | 提交候选版权项/其他去向 | 分轴状态 | 说明书/附图 | 映射状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|

一个技术单元可因不同PST具有多个权项落位，但每个落位必须保留相同来源和语义边界。关系至少覆盖接口、连接、输入输出、条件、顺序、状态迁移、反馈、共同受控对象和效果因果关系。

## 三A、从属有效语义和支持链接

从属权利要求不得只映射其限定部分。对每条合法路径`p`，四层账本另行登记：

| 路径字段 | 最低内容 |
|---|---|
| `DepPath` | 根独权、逐级上位权项、目标从权及路径兼容性 |
| `inherited_units` | 沿路径累计的全部CF/REL/CT/INT |
| `delta_sem` | 本项新增或细化单元，不得包含被静默替换的上位限定 |
| `anchor_ids` | 新增单元所依附的继承节点或链路 |
| `bridge_relations` | `refine/allocate/flow/trigger/guard/contributes-to`等桥接关系 |
| `effective_network_id` | 组合后的路径特定`TA`标识 |
| `scope_relation` | 模型限定累积、保护范围收缩 |

多项从权按各择一路径分别填写；不得把多个上位项的限制取并集，也不得把兄弟分支的新增单元带入当前路径。参数或结构细化应通过`refine`连接继承节点，不以新节点替换继承节点。

支持关系单独记录为`SupportLink`，至少包含`claim_span`、`description_id`、`relation_type`、`confidence`、`figure_or_assay_anchor`和`human_decision`。`confidence`仅用于候选排序，不能代替人工确认或法律结论。

## 三B、概念关系到权利要求特征的转换

概念关系不是新的MBSE模型层，而是阶段1技术模型到权利要求特征的派生审计视图。转换时必须保留关系类型及其来源：

- `is_a/specializes` 可以支持同一保护对象类别内的上位概括，但仍须通过支持范围和替换测试；
- `refines` 生成对既有CF/REL/CT/INT的功能、行为或机制细化，不能删除继承节点；
- `narrows` 生成对既有范围、参数、条件或时序的收窄，必须保留被收窄的继承限定；
- `part_of` 生成组成、接口或配置关系，不能把组成部件自动变成父对象的下位权利要求类型；
- `implements` 生成结构/算法/机制与功能的实现关系，不能把实现机制自动写成系统或方法的上位/下位类型。

`object_type/object_label`、`PST_boundary`、`relation_type` 和 `DepPath` 分别回答保护客体、客体名称、技术概念关系和权利要求继承路径，必须分栏保存。方法、设备、系统或模块之间的功能对应只能记录为平行根主题或桥接关系；未经对象边界和实施主体审计，不得相互改写。

`delta_sem` 只能是已继承网络上的新增或细化单元。若一个所谓下位概念没有继承锚点、功能作用或效果路径，则不得作为有效从属增量；若它构成独立闭合技术链，应回到CHAIN/PU/PST审计，而不是伪装成从属概念。

## 四、节点语言转换

| 节点 | 权利要求转换 | 说明书转换 | 禁止事项 |
|---|---|---|---|
| `R_problem/R_context` | 确定对象、场景和必要触发边界 | 描述问题及语境 | 把目的性空话当技术特征 |
| F | 仅在获得支持且边界清楚时，表达系统边界、输入、技术变换、直接输出和必要触发 | 补充实现机制、输出去向和异常边界 | 只写功能名称，或预先绑定无依据的唯一实现 |
| S | 表达实体、模块、配置、接口和关系 | 解释协同及替代实现 | 仅平铺模块或写品牌/API |
| B/STATE | 表达条件、顺序、触发、迁移、分支和反馈 | 解释状态和作用路径 | 擅自增加时序或反馈 |
| E | 原则上不以目的性效果语句进入；必要且受支持的`F.Output/OutputState`可转为结果限定 | 记录受影响对象、属性、后果、条件、S/B/REL/CV因果路径、证据及效果类型 | 把E、F.Output和OutputState混同，或用无因果的优越性表述 |
| IF/CV | 仅保留完成PST或技术作用所必需者 | 披露接口、范围和替代 | 写入无来源参数 |

无论M/E/C领域，`F.Output`、B或STATE的输出状态与E均须分开记录。`F.Output`是功能规格，`STATE.OutputState`是行为实现记录；E是该状态进一步改变技术对象属性的后果。机械机构到达某位置是状态；该状态如何改善密封、释放、承载或可靠性才是效果因果链。E若重复F动作或OutputState，删除、移入F.Output或按Q控制。

## 五、聚合、组合与独立链

F/S/B可聚合为INT的前提是处理连续、共享必要输入输出或共同构成不可分割技术作用，并具有同一CTX支持。聚合不得隐去条件、顺序、接口和关键中间结果。

映射遵循：`main_chain`独立闭合后形成PU候选；列明补正条件的`open_candidate`只能形成conditional/paused预审对象；`strengthening_subchain`不得形成PU或独权，只可形成从权增量。准入PU的PST只有同时通过客体完整性门和权项消费策略门，并标记`claim_consumption_status=consumed_independent`，才形成独权候选。不同PU进入同一申请或同一权项时，还须通过CTX组合支持、组合消费和单一性审查。

排除对象只进入`workflow.exclusion_records`，不得出现在CHAIN、PU、PST、IU或权项映射中。每个未消费PST和允许但未采用的组合均须保留消费状态、理由和去向，不得依靠权项缺席隐式表达。

## 六、对象实现契约

当对象为内容片段、数据对象、多模态对象、局部工程对象或局部访问控制对象时，记录：

| 对象类型 | 定位锚点 | 属性标签 | 请求目标到对象的映射 | 处理后对象与返回对象关系 | CTX | 原始证据 | 状态 |
|---|---|---|---|---|---|---|---|

影响PST边界、实施方式或效果的缺项按Q控制。

## 七、变更回写

| 阶段3变化 | 必须更新 | 回退阶段1 | 回退阶段2 |
|---|---|---|---|
| 仅文字、语序或不改技术含义的术语 | 权项表述和映射状态 | 否 | 否 |
| 特征落位或回退层级变化 | PU落位、账本和母版分配 | 视是否影响PU/CTX | 影响IU/PST时 |
| PST、对象边界或必要特征变化 | PST完整性、PU和账本 | 是 | 是，按`IU(PU,PST)=SearchProjection(PU｜PST_boundary)`重建受影响IU并补检 |
| 新增/删除必要节点、关系、PU组合或CTX | CHAIN、PU、组合支持和账本 | 是 | 是 |

权利要求锁定后发现主创新点未进入独权或支持不足，只记录保护范围限制、可允许的说明书补强边界和待确认事项，不得以说明书反向扩大权利要求。

## 八、最低验收

1. 每项独权能反向定位至`main_chain`、准入PU、通过客体完整性及权项消费策略门的PST、CTX、节点/关系、证据和效果支撑；
2. 每个采用的CF/REL/CT/INT均在提交候选权项或经确认的其他去向落位；
3. 所有跨实施例组合有CTX支持记录；
4. 母版分配中的每项移除均有去向；
5. 依赖图和最终DOCX的编号、术语、路径与账本一致。
6. 每项从权的每条路径均有`DependentClaimTrace`和`ClaimTextAudit`，且继承、增量、锚点、桥接、支持和效果归因闭合。
7. 每条已使用的概念关系均有`ConceptRelationAudit`、来源短语、替换结果、效果依赖和权利要求落位；组成/实现关系不得被误写成类型上下位。

## 九、受控回归的权项类型和来源短语接口

在阶段1＋阶段3受控回归中，每个权利要求映射行增加以下字段：

| 字段 | 要求 |
|---|---|
| claim_kind | 只能为 independent 或 dependent |
| object_type | 使用通用对象枚举；车辆、处理器、固体分散体等具体名称放入 object_label |
| object_label | 说明书中的对象名称，不改变 type 枚举 |
| canonical_type | 与 type 一致的稳定枚举，不得出现 independent_vehicle、independent_solid_dispersion 等临时分类 |
| source_branch_id | 回指 source_claim_skeleton 中的根主题或分支 |
| source_phrase_spans | 说明书原文短语/段落定位，至少一项 |
| phrase_transformation | verbatim、minimal_normalization、subject_completion、candidate_rephrase 或 unsupported_addition |
| unsupported_additions | 未在说明书来源短语中出现或无法回指的新增内容，必须为空或明确标记 [Q] |
| `concept_relation_ids` | 涉及概念关系的权项或分支回指 `ConceptRelationAudit`；关系未确认时保持 [Q]/conditional |

映射顺序固定为：说明书来源短语 → R/F/S/B/E和CHAIN → PU/PST/CTX → CF/REL/CT/INT → 权利要求。不得从金标准文本反向补造 source_claim_skeleton，也不得使用相似度代替来源短语和支持关系。

每个 source_claim_skeleton 分支只能有一个当前候选去向；多个候选权项共享一个分支时，必须记录复用原因和各自对象边界。没有 source_branch_id、source_phrase_spans 或 unsupported_additions 未处置的权项，不得标记结构轴 pass。
