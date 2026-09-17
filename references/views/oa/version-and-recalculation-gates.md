# OA活动版本、分析快照与重算门

本文件是阶段零、三、四、五共用的执行规范；对象字段以 `oa-evidence-pack-schema.md` 为准。

## 1. 阶段零冻结前清单

1. 建立完整OA问题注册表，为每项问题生成稳定指纹；
2. 将文献事实状态与新颖性/创造性法律资格分轴登记；
3. 列出原始、候选、活动、废止权利要求集合；
4. 只有集合身份和修改支持均确定时，才写唯一 `active_claim_set_id`；
5. 材料冲突或缺失使用 `Q`，不以“较高/较低风险”代替未知。
6. 为每个 `OAIssue` 预先登记 `response_mode`（`ArgumentOnly`、`AmendmentBased`、`Interview` 或 `Appeal`），并绑定当前 `ClaimVersion`。

## 2. 阶段三快照协议

阶段三开始前必须冻结活动集合、全部引用路径、文献双轴资格和唯一主策略。冻结后才生成TA、NB、IS、`CombinationPath`及核心区别链。冻结采用 `snapshot_id + freeze_revision`，其中 `freeze_revision` 为单调递增或人工明确的版本号，不承担内容指纹功能；不得为新任务生成或比较Hash。事实或策略改变时，不修改旧快照内容；新建快照、写入新的 `freeze_revision` 并使旧快照失效。每条路径必须同时登记正向闭合状态和反向断裂点；`EffectEvidenceCard` 的来源、比较基准、日期和范围覆盖也属于快照输入。旧包的 `frozen_hash` 仅可只读保留，不能成为新快照的必需字段。

## 3. 修改影响闭包

对任一修改项 `c`，影响闭包为：

```text
Closure(c) = {c}
             ∪ 全部直接和间接引用后代
             ∪ 因编号、引用路径或保护主题改变而变化的权项
```

闭包内每项权利要求按每条有效引用路径重新展开，并重新生成TA。不能只给修改独立项重算而把从属项视为自然继承。

## 4. NBComplete与ISComplete执行检查

- `NBComplete(V)`：活动集合V中每个权利要求、每条有效引用路径都有一份针对完整展开对象的NB记录，且每份记录只使用一篇具相应资格的文献；不适用时也要有结构化 `no_separate_issue` 记录。
- `ISComplete(V)`：同一覆盖集合中每条路径都有 `full/inherited/no_separate_issue` 之一，且明确文献资格、区别链、技术启示状态与结论确定性。

二者缺一，`recalculation_gate.passed=false`。

## 5. 原子事务回滚条件

出现以下任一情况即停止定稿：

- `supersedes` 或修改事件缺失；
- 支持依据为 `Q`；
- 活动集合、快照或主策略不是唯一；
- 闭包内NB/IS覆盖不全；
- 仍存在旧快照的活动NB/IS/RT；
- 活动答复追溯没有全部切换至新快照；
- `CombinationPath` 未能回放到目标 `TA`，或 `fusion_feasible` 仍为 `Q` 却被当作闭合；
- 效果缺少 `EffectEvidenceCard`、比较基准、来源日期或范围覆盖说明；
- `ArgumentOnly` 事件改变了活动权利要求集合，或 `AmendmentBased` 未新建版本并重算；
- `DecisionTrail` 无法从 OA 争点正向到达结果，或无法从结果理由反向追溯到证据段落；
- 决定性Q进入确定风险、覆盖结论或闭合组合路径。

停止后保留内部条件性草稿，列明具体缺口；不输出“定稿”“可提交”或无条件肯定结论。

## 6. 阶段五五方一致性

从同一 `active_snapshot_id` 出发逐项核对：

```text
活动权利要求集合
↔ 问题注册表
↔ NB/IS与核心区别链
↔ response_trace和对外答复段落
↔ content/submission就绪状态
```

任何一方对象、文献资格、处理动作或状态不一致，均不得通过审计。

此外必须执行双向闭包：

```text
正向：OA → OAIssue → 证据 → 区别/效果 → CombinationPath
      → ResponseEvent/AmendmentEvent → DecisionTrail
反向：DecisionTrail/结果理由 → 答复事件 → 申请人行动
      → OAIssue → CombinationPath → 文献证据
```

### 7. 版本冻结字段与无Hash约束

新建或切换快照时至少写入：

```text
snapshot_id
freeze_revision
frozen_at（未知可为 null）
freeze_status = active | superseded | invalidated
```

重算门只检查对象引用、活动集合、版本号和生命周期状态，不读取、生成或比较文件Hash。旧证据包中的 `frozen_hash` 可以原样保留为只读历史字段，但不得成为新任务的必需字段。

正向和反向闭包的每一跳都必须有对象ID及来源位置；缺少任一跳时只允许 `conditional/blocked`，不得以相似度、模型置信度或数据集任务标签补齐链条。
