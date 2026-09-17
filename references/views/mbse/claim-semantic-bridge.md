# 权利要求语义—证据桥接视图

## 定位

本视图是 R/F/S/B/E 五层模型的条件性派生视图，不是新的 MBSE 模型层，也不直接生成可提交的权利要求文本或法律结论。其作用是把技术模型转换为可审计的权利要求特征、从属路径和证据定位。

适用条件：

- `document` 模式输入包含权利要求文本时，为必选输出；
- 进入审查意见答复交接、权利要求覆盖或支持审计时，为必选输出；
- `disclosure` 模式只输出候选桥接，不输出正式权利要求文本；
- `search` 模式可在检索后输出特征—文献—段落映射，但不输出法律结论。

## 主链

```text
R/F/S/B/E
  → CHAIN
  → PU/PST/CTX
  → ClaimVersion
  → ClaimPath/DepPath
  → ClaimSpan
  → CF/REL/CT/INT
  → SupportLink
  → DOC/EV/审计结果
```

桥接对象只描述语义和来源关系。最终文字表达、权利要求布局和答复策略分别由相应 内部视图 负责。

## 最小权利要求特征单元

每个 `ClaimSpan` 或 `CF` 至少记录：

| 字段 | 含义 |
|---|---|
| `object` | 对象、部件、数据或步骤主体 |
| `property` | 属性、参数、状态或材料限定 |
| `relation` | 连接、包含、映射、约束或作用关系 |
| `action` | 处理、控制、检测、转换等动作 |
| `condition` | 触发、守卫、范围或适用条件 |
| `sequence` | 先后、循环、并行或依赖顺序 |
| `parameter` | 数值、范围、阈值、配比或时序参数 |
| `source_span` | 权利要求原文位置 |
| `fact_status` | `D/I/Q/X` 或 disclosure 场景下的 `N/G` |
| `inclusion_status` | 继承、新增、替代、候选或排除 |

不得只保留关键词而删除关系、条件、顺序或组合语境。

## 从属权利要求路径

对每条从属权利要求枚举完整合法的 `ClaimPath`。每条路径必须同时记录：

- 被引用的全部上位权利要求；
- 从每个上位项继承的限定；
- 本项新增的限定；
- 新增限定与继承基线的对象、关系、条件或功能锚点；
- 多项从属的每条替代路径，不得把不同路径的限定取并集。

单独匹配新增特征不能替代完整继承网络，也不能自动产生新的创造性贡献。

## 支持和证据矩阵

有权利要求文本时，至少形成下列矩阵：

| 字段 | 说明 |
|---|---|
| `claim_id` / `claim_version_id` | 权利要求及其版本 |
| `claim_path_id` | 完整引用路径 |
| `claim_span` | 片段或限定编号 |
| `feature_group_id` / `relation_id` | 特征组和关系 |
| `source_document_id` / `source_location` | 来源文件及段落、页码、附图或实验位置 |
| `relation_type` | `itself`、`description` 或 `example` |
| `combination_context` | 该片段在完整组合中的语境 |
| `matching_basis` | `exact`、`structural`、`semantic`、`partial`、`not_found` |
| `confidence` | 候选排序指标，不是确认结论 |
| `human_decision` | `pending`、`accepted`、`rejected` |
| `review_note` | 人工复核理由 |

只有相似度或关键词重合而没有原文位置、组合语境和人工决定时，状态必须保持 `Q` 或待审核。

## 组合语义和新颖性边界

不同文献分别公开的特征不得在 `NB` 中拼接为单一文献覆盖。只有同一文件对全部必要特征、关系、条件和顺序具有明确或直接且无歧义的披露时，才可能进入单文献覆盖评价。检索排名、相似度、ROUGE、BERTScore 和模型置信度均只能发现候选证据。

## AI 来源与人工确认

AI 产生的候选桥接对象必须记录：

```text
input_document_id
input_version_id
source_span
tool_or_model_id
prompt_or_template_id
generated_at
candidate_status
confidence
human_reviewer
human_decision
decision_time
review_note
```

状态只能按 `candidate/draft → human_reviewed → agreed` 递进。AI 不得自动确认原始事实、升级证据状态、批准 SupportLink 或产生法律结论。

## 与 SysML 的操作性映射

`satisfy`、`allocate`、`flow`、`refine`、`verify` 和 `trace` 可用于表达模型对象之间的操作性关系，并映射到 `R/F/S/B/E`、`CF/REL/CT/INT` 和 `SupportLink`。该映射是工作流语义对应，不主张 SysML 关系与中国专利法概念在法律上完全等价。

## 回归增量：桥接完整性和多项从属路径

### 1. 最小完整桥接记录

只要输入含有权利要求，`claim_mappings` 不得退化为只有权利要求编号和摘要。每一条可评价的权利要求尽量保留：

```text
claim_id
claim_version_id
claim_type
claim_path_id
chain_ids
pu_id
pst_id
ctx_ids
feature_group_ids
relation_ids
support_link_ids
source_refs
status
human_decision
```

缺失字段不得用另一个对象的值替代；无法核验时填写 `Q`，并在待核实问题表中说明缺口。

### 2. 从属项的完整继承网络

每个 `ClaimPath/DepPath` 必须能够回答：

```text
引用了哪些上位权利要求？
完整继承了哪些限定？
新增了哪些限定？
新增限定锚定到哪一个对象、关系、条件或功能？
该路径的支持证据在哪里？
修改后是否需要重新计算？
```

多项从属的替代路径必须分别建模。不得把不同上位项的限定取并集，也不得只分析新增限定而丢失继承基线。

### 3. SupportLink 的状态门

支持关系的可接受条件为：

```text
source_location 非空
combination_context 非空
relation_type 属于 itself/description/example
human_decision 已记录
```

只有上述条件均满足且人工决定为 `accepted` 时，才可将支持链接用于“已确认支持”表述。`confidence`、相似度或关键词重合只能作为候选排序依据。`matching_basis=semantic` 或 `partial` 不能单独使支持链接通过。

### 4. 代表性领域的桥接要求

机械案件应把结构、接口和行为限定分开；化学/材料案件应把组分、比例、工艺和效果证据分开；复审决定案件应把决定摘录、技术链和法律结论分开。任何一类案件都不得因模型节点合并而丢失权利要求组合语境。

## document-model-2026.2 结构合同

`claim_versions_and_paths` 必须是扁平数组。每个元素代表一个具体的权利要求版本和一条完整引用路径，不得包含 `null`、嵌套数组或无法回指的 ID：

```json
[
  {
    "claim_id": "CLM-01",
    "claim_version_id": "CLM-01-v1",
    "claim_path_id": "PATH-01",
    "chain_ids": ["CHAIN-01"],
    "pu_id": "PU-01",
    "pst_id": "PST-01",
    "ctx_ids": ["CTX-01"],
    "feature_group_ids": ["CF-01"],
    "relation_ids": ["REL-01"],
    "support_link_ids": ["SL-01"],
    "source_refs": ["..."],
    "status": "candidate",
    "human_decision": "pending"
  }
]
```

验证时必须确认：

- 每个 `claim_id` 能回指当前输入中的权利要求；
- 每个 `claim_version_id` 能回指当前版本；
- 每个 `claim_path_id` 能回指完整引用路径；
- 每个 `feature_group_id`、`relation_id` 和 `support_link_id` 均能回指当前运行对象；
- 多项从属路径分别记录，不取并集；
- 缺少来源或组合语境时保持 `Q` 或 `candidate`；
- 不以其他案件、历史运行或未声明来源补齐桥接对象。

`SupportLink` 的 `accepted` 仅在来源位置、完整组合语境、匹配依据和人工决定均存在时允许使用；相似度、关键词重合、置信度和任务标签只能作为候选排序依据。
