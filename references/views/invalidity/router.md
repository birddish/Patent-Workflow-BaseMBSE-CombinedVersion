# invalidity 无效答辩意见陈述视图路由

机器规范源为：4-技能指令源稿/cn-patent-case-workflow/references/routing/views/invalidity.json

## 冻结机器合同

- view=invalidity
- submode=defense
- profile=v2.1-invalidity
- phase=phase_01、phase_02、phase_03、phase_04、phase_05
- phase_05：交付前核对
- read_profile：invalidity.defense.{phase}
- write_prefix=/derived/invalidity
- response_round：首次、补充或后续答辩轮次，不新建 submode

这里的 invalidity/defense 是专利权人无效答辩，不是 search.invalidity。novelty、inventive_step、quick、standard、formal 只能作为其他检索或分析体系的值，不能出现在本视图的 canonical submode/profile 中。

## 明文模式门

使用前必须让用户逐项明文确认 transaction、view、submode、profile、phase、domain、operation 和是否允许写回。若用户选择与 AI 判断、案件 control、current_revision 或前置材料冲突，必须先列出用户选择、AI 判断、依据和后果，生成 challenge_id 并暂停，不得静默改选、加载规则或写回。

默认事务是 case_json_only。只有用户明确选择 bootstrap_import 或 reimport_material，并明确列出外部文件、导入策略和旧批次处理方式时才可读外部材料。普通继续、刷新、重算不触发外部读取；source_path、location 和 URL 只作 provenance。

## 五阶段和按需读取

phase_01 材料准入，加载 phase-1-intake.md；phase_02 事实核实，加载 phase-2-fact-verification.md；phase_03 MBSE 追溯与逐理由分析，加载 phase-3-mbse-traceability.md；phase_04 答辩意见起草，加载 phase-4-statement.md；phase_05 交付前核对，加载 phase-5-delivery-gate.md。证据控制只在对应阶段按需加载。

每阶段只读取 RoutePlan 的 JSON 投影、指定稳定 ID 和证据闭包。invalidity 只能写 /derived/invalidity，不得写其他业务视图。旧案件可以没有 derived.invalidity。

## 输出边界

支持、新颖性、创造性和其他理由按请求人已主张顺序分开回应。新颖性逐份证据、逐特征比对；创造性针对权利要求限定的整体技术方案，并以 R/F/S/B/E 对应贡献特征、技术问题、技术效果和证据。工程断点不自动等于法律结论。

对外文本不得出现内部 ID、status、revision、JSON Pointer、source_path 或规则名。法条、指南段号、修改规则、公开日、译文、公知常识、技术偏见和程序期限必须按案件时点逐案核验。