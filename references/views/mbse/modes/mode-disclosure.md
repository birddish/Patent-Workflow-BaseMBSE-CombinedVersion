# Mode: disclosure — 技术交底书可专利性建模

## 适用范围

以发明人提供的申请前技术交底书及可选背景材料为输入。不得在本 mode 中对正式申请文件、引用对比文件、审查意见或驳回决定进行建模——这些材料交给 mode=document 处理。

## 工作流程（四阶段）

### 阶段一：R/F/S/B/E 四视角模型

1. 提取技术问题、提出的解决方案、声称的效果、术语、实施例和附图。
2. 构建五层模型：
   - **R（需求）**：技术需求、工程约束或验收目标，以"如何……"开头
   - **F（功能）**：系统应完成的输入—技术变换—直接输出合同，必要时记录系统边界和触发
   - **S（结构）**：组件、模块、连接关系、空间布局
   - **B（行为）**：活动、顺序、状态、事件、条件分支
   - **E（效果）**：由具体S/B/关系及输出状态进一步造成的对象属性变化或技术后果
3. 将每个实质性节点链接到其来源段落或附图。
4. 构建追溯链 `R → F → S → B/STATE → OutputState → E`；OutputState只是F与E之间的链路字段，不是新增模型层。将缺失或模糊信息标注为 `Q`；不得虚构效果、参数或工作关系。
5. 对待确认问题执行“权利要求相关性过滤”：只有客户回答能够改变技术模型、候选权利要求特征、技术效果、说明书/附图支持或保护范围的问题才保留；与上述对象没有可说明影响关系的问题直接删除。
6. 输出节点表、追溯链表、待确认问题表、Mermaid 图。
7. 暂停等待用户确认。

#### 交付物规格

| 表格 | 列 |
|------|-----|
| R/F/S/B/E 节点表 | `id`、`view`、`node`、`source`、`evidence_level`、`notes` |
| F功能合同表 | `id`、`system_boundary`、`input`、`transformation`、`output`、`precondition_or_trigger`、`allocated_S`、`realizing_B` |
| E效果合同表 | `id`、`affected_object`、`affected_attribute`、`consequence`、`applicable_condition`、`causal_path`、`effect_type`、`comparison_baseline`、`evidence` |
| 追溯链表 | `chain_id`、`R`、`F`、`S`、`B`、`E`、`gap_or_question` |
| 待确认问题表 | `question_id`、`missing_dimension`、`why_it_matters`、`requested_confirmation` |

Mermaid 结构图、行为图和追溯链图，其节点 ID 与表格匹配。

### 客户问题相关性过滤规则

每个保留的问题必须能够回答以下两个问题：

1. 它对应技术方案中的什么内容：技术对象、结构、功能、行为/步骤、参数/条件、技术效果、候选权利要求限定或说明书/附图支持；
2. 客户回答后会改变什么：权利要求特征或关系、结构/功能关系、步骤顺序、参数范围、技术效果因果链、实施例或支持依据。

无法建立上述对应关系的问题不输出。问题生成前可使用内部判断字段 `claim_relevant=yes|no`；仅 `claim_relevant=yes` 的问题可以进入待确认问题表。

以下问题默认删除：

- 单纯询问数据或日志需要保存多长时间；
- 仅涉及法规、企业制度或运营安排的保存期限；
- 商业部署方式、用户数量、收费模式、运维制度或市场计划；
- 与技术结构、技术行为、技术效果和权利要求范围无关的隐私、合规或用户偏好问题。

“数据存放时间”只有在技术交底书已经表明其会改变技术机制时才可保留。例如，时间窗口用于缓存保留、超时删除、滚动缓冲、状态切换、同步、资源控制或安全控制。此时不得笼统询问“数据要保存多久”，而应询问具体的技术机制、触发条件、执行动作及技术效果，例如：

> 该时间窗口是否用于控制缓存数据的保留、删除或状态更新？超过时间窗口后系统执行何种技术操作，该操作产生什么技术效果？

如果没有现有技术机制可以建立上述联系，则不为确认“是否存在技术影响”而泛化提问，直接删除该问题。

删除无关问题不构成建模失败，也不改变 R/F/S/B/E 模型。若没有任何与权利要求相关的待确认事项，待确认问题表可以为空，并在交付说明中标记 `no_claim_relevant_questions`。

### 上位/下位概念与必要技术特征判定

在形成候选权利要求特征组前，先识别上位技术角色或功能，再展开具有技术意义的下位实现。下位技术方案按以下方式表示：

```text
Lᵢ = U + Iᵢ + Relᵢ + Cᵢ
```

其中 `U` 为共同的上位技术角色或功能，`Iᵢ` 为具体实现机制，`Relᵢ` 为结构、连接、信号流、时序或行为关系，`Cᵢ` 为参数、条件或适用边界。

必要性判断必须同时进行“删除/替换测试”和“技术效果依赖测试”：

1. 删除或替换 `Iᵢ` 后，`R→F→S→B→E` 追溯链仍闭合，且技术问题和核心效果仍成立的，`U` 标记为共同必要特征，`Iᵢ` 标记为 `alternative` 或 `optional`；
2. 替换 `Iᵢ` 后功能、关键行为、接口、约束或技术效果因果链断裂的，`Iᵢ` 标记为 `branch_necessary`；
3. 上位概念会覆盖未披露、不能实现效果或缺乏说明书支持的方案的，应下移至能够被支持的下位概念或增加必要关系/条件；
4. 多个下位实现能够互相替代时，使用“上位共同特征 + 下位替代分支”，不得把互相排斥的实现方式并列相加为共同必要特征。

必要性分析表可使用以下列，不改变 R/F/S/B/E 核心模型：

| 特征 | 上位角色/功能 | 下位实现 | 关系类型 | 删除/替换结果 | 效果是否依赖 | 必要性状态 | 来源/说明 |
|---|---|---|---|---|---|---|---|
| 示例 | 输出视觉信息 | 液晶调制 | `specializes`/`implements` | 替换为显像管后仍可显示 | 否 | `alternative` | 记录适用范围 |

例如，液晶屏幕和显像管屏幕应先抽象为共同的“视觉信息输出”功能或“显示模块”对象，再分别建模：

```text
显示模块
├── 液晶调制实现
│   └── 液晶层、电极控制、像素寻址等关系
└── 电子束—荧光屏实现
    └── 真空管、电子枪、电子束扫描等关系
```

如果本案解决的是显示模块与控制器的共同接口问题，上位的“显示模块”可以作为共同必要特征，液晶和显像管作为替代分支；如果本案效果依赖液晶分子取向、电极控制或特定光学调制，则相应液晶结构和控制关系应标记为该分支的必要下位特征。客户当前采用哪一种产品，不足以单独决定必要性。

“数据存放时间”本身通常是参数或约束，不是上位/下位概念。只有当时间窗口触发缓存删除、状态切换、同步、资源控制等技术行为，并且该行为影响追溯链或技术效果时，才作为具体约束继续询问；单纯的合规或运营保存期限不进入必要性分析。

### 阶段二：候选创新点

从结构新颖性、功能协同、操作时序或跨视角交互中识别候选创新点。将其描述为初步技术假设，而非授权结论。

使用包含列 `innovation_id`、`R`、`F`、`S`、`B`、`E`、`source_support`、`evidence_level`、`confidence`、`inventor_question` 的表格。

筛选标准：候选创新点至少有一条完整或明确标注了断点的追溯链，否则不得输出。

暂停等待用户确认。

### 阶段二A：面向权利要求的候选语义视图（用户确认创新点后可选）

在阶段二确认候选创新点后，可以将其转换为候选权利要求特征组，但本 mode 不生成最终权利要求文本。候选视图至少包括：

```text
candidate_claim_feature_groups
candidate_relations
candidate_conditions
candidate_sequence
source_refs
fact_status
inclusion_status
human_decision
```

候选特征必须保留对象、关系、条件、顺序、参数和组合语境，并可回指 `CHAIN/PU/PST/CTX`。AI 生成的候选从 `candidate/draft` 开始，记录输入版本、来源片段、工具或模型标识、生成时间、置信度和人工决定。需要正式撰写时，将该中间结果交接给 `撰写视图`，不得在本 mode 内直接形成提交文本或法律结论。

### 阶段三：检索要素

将已确认的创新点转换为检索要素。

仅对机器可读块输出有效的 JSON。不得在 JSON 内部包含注释。每个 JSON 对象必须包含：

- `innovation_id`、`innovation_name`
- `technical_problem`、`technical_solution`、`technical_effect`
- `evidence_level`、`search_priority`
- `search_elements`（核心术语、同义词、必要组合、可选排除词、初步 IPC 起点）
- `novelty_indicators`
- `related_patents_from_search`

暂停等待用户确认。

### 阶段四（可选）：公开资料初筛及 Google Patents 补充

仅当阶段三确认后且用户明确要求检索时才执行。

#### 4A：公开资料初筛

使用公开搜索引擎查找非专利文献、技术文档、标准、开源文档和权威技术综述。记录每条结果：

| 字段 | 说明 |
|------|------|
| `innovation_id` | 对应创新点编号 |
| `source_tier` | A(官方标准)/B(同行评审)/C(开源项目)/D(通用网络) |
| `engine_or_database` | 检索引擎或数据库 |
| `query` | 检索式 |
| `search_date` | 检索日期 |
| `title` | 文献标题 |
| `URL` | 链接 |
| `disclosed_features` | 公开的技术特征 |
| `relevance` | 相关性判断 |
| `limitation` | 局限说明 |

D 级结果不得作为技术结论的唯一依据。

输出：（1）术语和技术成熟度摘要；（2）每个创新点的风险观察；（3）正式专利检索交接文件。

#### 4B：Google Patents 补充检索

当 Google Patents 可访问时执行。记录：

| 字段 | 说明 |
|------|------|
| `innovation_id` | 对应创新点 |
| `engine_or_database` | 固定为 Google Patents |
| `query`、`filters` | 检索式及筛选条件 |
| `search_date` | 检索日期 |
| `publication_number`、`title` | 专利号及标题 |
| `applicant_or_assignee` | 申请人 |
| `earliest_priority_date`、`publication_date` | 日期 |
| `jurisdiction` | 法域 |
| `family_or_related_documents` | 同族 |
| `disclosed_features`、`feature_location` | 公开特征及位置 |
| `relevance`、`limitation` | 相关性及局限 |
| `source_URL` | 来源链接 |

对于实质性中国文献，在依赖之前应在 CNIPA 或其他权威专利数据库中核实公开号、法律状态和家族信息。

#### 4C：初步新颖性评估

对每个创新点产出评估表：

| 列 | 说明 |
|-----|------|
| `innovation_id`、`innovation_name` | 标识 |
| `public_source_evidence` | 公开资料证据摘要 |
| `Google_Patents_evidence` | Google Patents 证据摘要 |
| `same_or_corresponding_features` | 相同或对应特征 |
| `missing_or_distinguishing_features` | 缺失或区别特征 |
| `preliminary_novelty_risk` | 高/中/低/无法判断 |
| `assessment_reason` | 评估理由（文献特定的特征映射） |
| `evidence_boundary` | 证据边界声明 |
| `next_verification` | 下一步验证建议 |

**风险评级标准**：

- `高`：一篇可访问的专利文献似乎在同一技术方案中公开了所有实质性技术特征（有待权威验证）
- `中`：公开来源或专利文献公开了实质性基础或部分特征，但同一方案组合、特征位置或文献状态需进一步验证
- `低`：检索范围内未识别出公开了实质性组合的单一文献，且检索日志记录充分
- `无法判断`：Google Patents 不可访问、查询覆盖不充分或创新点缺乏稳定的特征定义

不得使用多篇文献组合来断言某创新点不具备新颖性；仅记录为需要单独分析的创造性或组合风险线索。

每条评估理由必须说明：所比较的实质性特征、支持性公开来源或专利公开号、特征位置（如有）及关键差异或缺失证据。声明该评估仅限于所记录的检索引擎、查询式、筛选条件、日期和可访问文献。

## 领域特定规则

根据交底书技术领域，读取对应的域参考文件：
- 机械/结构 → `references/domains/mechanical.md`
- 电子通信/AI/软件 → `references/domains/electronics-communication.md`
- 软件/算法 → `references/domains/software-algorithm.md`
- 化学/材料 → `references/domains/chemistry-material.md`

## 质量门禁

在提交每个阶段之前验证：

- 每个 `R` 都有下游的 `F/S/B/E` 路径或明确的 `Q`
- 每个 `S` 都有功能目的和出处引用
- 每个F具有输入、技术变换和直接输出，并能分配到S、由B核验
- 每个E具有受影响对象、属性、后果、条件、因果路径和证据，不重复F或OutputState
- 没有商业目标在缺乏技术框架的情况下被改写为技术问题
- 没有检索前的假设被写成新颖性或可专利性结论
- Mermaid 节点 ID 与 R/F/S/B/E 表格匹配
- 检索要素 JSON 可解析且不包含 Markdown 注释
- 已适用领域特定的证据规则（如相关）
- 每条实际检索发现标识其来源层级、查询式、日期和 URL
- 没有公开资料初筛结果被描述为专利数据库检索结果或最终的新颖性/创造性结论
- 每条 Google Patents 结果记录其查询式、筛选条件、公开号、日期、特征位置和来源 URL
- 每个创新点都有初步新颖性评估、文献特定的理由、证据边界和下一步验证步骤
- 候选权利要求视图（如生成）保留完整组合、来源片段、状态和人工决定
- AI 候选具有输入版本、工具/模型标识、生成时间和审核留痕

## 补充规则：AI 候选与来源性质

当使用语言模型或其他自动化工具抽取 R/F/S/B/E、CHAIN、CF 或关系时，输出必须记录：

```text
input_document_id / input_version_id / source_span
tool_or_model_id / prompt_or_template_id / generated_at
candidate_status / confidence / human_reviewer
human_decision / decision_time / review_note
```

自动生成节点的初始状态只能是 `draft`、`[I]` 或 `[Q]`；只有技术人员确认原始内容、代理师完成适用性审核后，才可进入正式 `PU/PST/CLM` 交接。

申请前交底中的 `N/G` 仍只表示发明人确认新增或其概括，不表示现有技术公开。AI 的置信度只用于候选排序，不得自动改变事实状态、撰写采用状态或法律判断。若引用官方手册、官方演示、预印本或数据集作为方法来源，应另记 `source_status` 和 `research_role`，不得将其混作案件证据。
