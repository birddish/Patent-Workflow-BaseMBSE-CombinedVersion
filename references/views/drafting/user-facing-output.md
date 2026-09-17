# 撰写视图用户界面规则

撰写视图默认面向用户输出 Markdown，不输出案件主 JSON 的原始内容。

## 默认规则

- case.json 只作为后台案件数据源、版本源和交付物登记源；
- 阶段成果必须以 deliverables 目录中的 Markdown 文件呈现；
- 自动化入口默认输出 Markdown 摘要、阶段状态和 Markdown 文件路径；
- 模式冲突、缺少字段和阶段阻断也必须用 Markdown 说明；
- 不得把 JSON 摘要、JSON 错误对象或完整 case.json 直接作为用户交付。

## 机器调用例外

只有内部编排、脚本管道或明确要求机器可读输出时，才允许使用 --machine-readable。
该参数不属于普通用户交互模式，不得由总 Skill 默认传递。

## 推荐入口

普通用户交互应调用：

scripts/run_drafting_stage_md.py

该入口内部可以调用 JSON 编排脚本，但对用户只返回 Markdown。
