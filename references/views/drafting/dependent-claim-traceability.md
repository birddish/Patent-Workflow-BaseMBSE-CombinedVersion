# 从属权利要求技术追溯合同

本文件供阶段3、阶段4、阶段5、阶段8和阶段9调用。它只定义技术语义和证据闭合，不定义版本、责任、审批或生命周期；这些治理属性由论文第六章及治理接口承接。

## 一、核心对象

对以独立权利要求为根、终止于从属权利要求`C_{k,v}`的合法引用路径集合，定义：

```text
DepPath(C_{k,v}) = {p | p=(C_root, C_1, ..., C_k), p为合法引用路径}
```

从属权利要求相对于直接上位权项的新增或细化语义记为：

```text
ΔSem(C_{k,v}) = <ΔCF, ΔREL, ΔCT, ΔINT>
```

沿路径`p`累计继承后的完整语义为：

```text
Sem_eff(C_{k,v};p)
= Sem(C_root,v) ⊕ ΔSem(C_1,v) ⊕ … ⊕ ΔSem(C_k,v)
```

`⊕`是保持对象身份、关系方向、条件、顺序和相互作用语境的限制性组合，不是集合并集；不得删除、替换或冲突于上位权项限定。

对直接上位权项`C_{j,v}`，增量追溯子网络和有效网络定义为：

```text
ΔT(C_{k,v}|C_{j,v}) = 增量限定 + 继承锚点 + 桥接关系 + F/E证据
TA(C_{k,v};p)
= Compose(TA(C_{j,v};p^-), ΔT(C_{k,v}|C_{j,v}), Bridge_k)
```

模型限定和保护范围具有相反方向：

```text
U_eff(C_{k,v};p) ⊇ U_eff(C_{j,v};p^-)
Scope(C_{k,v};p) ⊆ Scope(C_{j,v};p^-)
```

## 二、四类增量关系

| 类型 | 允许的技术含义 | 最低锚定要求 |
|---|---|---|
| `refine` | 将既有结构、功能、参数、状态或条件具体化 | 指向被细化的继承节点/链路 |
| 关系/参数收缩 | 缩小关系方向、连接方式、阈值、范围、时序或适用条件 | 指向被收缩的`REL/CT/STATE` |
| `INT`协同 | 新增特征与继承特征共同形成不可任意拆分的作用或效果 | 继承成员、共同作用和组合证据 |
| 主链耦合分支 | 与主链保持接口、状态或功能耦合的替代/异常路径 | 主链接口、触发条件和不冲突证明 |

无继承锚点、功能作用或效果路径的独立技术链不得包装为从属增量。

## 三、路径和依赖规则

1. 线性引用必须逐级累计全部上位限定，不能只保留最近一级文本。
2. 兄弟从属权利要求分别从共同上位网络派生，不得互相串入新增特征。
3. 多项从属权利要求按每一条择一引用路径分别生成`Sem_eff`、`U_eff`、`TA`、`NB`和`IC`；不得将多个上位权项取并集，也不得把一条路径的效果带入另一条路径。
4. 增量子网可以复用上位`R/F/E`，不要求自身独立具备完整R/F/S/B/E五层；但组合后的有效网络必须语义闭合、因果闭合且有证据支持。
5. 下位限定不得静默删除、替换或冲突于上位限定；发现冲突时回到引用、术语或实施分支核验。
6. 每个已消费分支只形成一项从权；未消费分支必须明确记为`reserved/paused/excluded/Q`并说明去向。

## 四、DependentClaimTrace接口

```text
DependentClaimTrace {
  claim_id
  direct_parent
  reference_target_claim_id
  root_object_name
  reference_object_name
  reference_text
  reference_name_match
  reference_name_status
  DepPath[]
  inherited_units[]
  delta_sem
  anchor_ids[]
  bridge_relations[]
  reuse_or_new_FE
  path_support[]
  effective_network_id
  scope_relation
  audit_status
}
```

`audit_status`仅表示技术审计状态，采用`pass/[Q]/fail/blocked`，不表示授权、侵权或创造性结论。

## 四A、从属权利要求引用客体名称合同

1. 独立权利要求先登记规范化的 root_object_name；该名称保留完整主题限定和客体类型，通常不含开头的“一种”。
2. 每个从属项登记 reference_target_claim_id、reference_object_name 和 reference_text；reference_object_name 必须来自直接上位权利要求所属根主题。
3. reference_text 必须实际包含完整 reference_object_name。仅出现“方法”“设备”“系统”“装置”或“模块”的引用文本视为名称不完整。
4. 多项从属必须对每一条 DepPath 独立核对 reference_name_match；不同根主题不能被一个通用客体名称掩盖。
5. 名称缺失、不一致或无法由上位权利要求确定时，reference_name_status 只能为 conditional、fail 或 blocked，不得生成正式提交候选版。
## 五、最小验收

- 每条路径能列出全部继承单元和本项增量；
- 每条路径具有完整客体名称引用、引用目标和名称一致性结果；
- 每个增量特征都有继承锚点、关系/条件语义和说明书/附图/实施例支持；
- `TA`由上位有效网络、增量子网和`Bridge`组合得到，不能由附加特征单独生成；
- 多项从属不存在路径合并、兄弟泄漏或另一多项从属引用；
- 无锚点、无作用或无证据的附加特征不得进入提交候选版；
- 变更后的路径重算由阶段9交给第六章治理接口记录影响范围。

本内容仅为执业辅助参考，最终需专利代理师本人审核确认。
