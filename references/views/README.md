# 视图目录说明

`mbse/`、`search/`、`drafting/`、`oa/`、`invalidity/` 和 `audit/` 都是同一总 Skill 对单一 `case.json` 的内部视图，不是独立运行入口。`search.invalidity` 是无效相关检索，`invalidity.defense` 是专利权人的无效答辩意见陈述；两者不得自动互换。

加载业务规则前必须通过 `references/core/mode-gate.md` 的明文确认和质疑门，并生成可执行 RoutePlan。实际只加载 RoutePlan 的 `rule_files`，以及在条件明确成立时才追加的 `conditional_rule_files`；不得遍历或批量加载整个视图目录。

每个视图的 `router.md` 仅供人工核对，机器规范源位于 `references/routing/views/*.json`。
