# 撰写视图索引

进入撰写视图时，必须先读取 drafting-deliverables-contract.md。

本视图的最小运行顺序为：

1. 要求用户明文确认事务模式和目标阶段；
2. 校验用户选择与 case.json 当前状态是否一致；
3. 仅读取当前阶段允许的 JSON 切片；
4. 通过版本化 Patch 写回 derived.drafting 和 control；
5. 从写回后的 case.json 生成当前阶段的 deliverables 文件；
6. 登记交付物的路径、来源 revision、状态和待人工确认状态；
7. 向用户返回 case.json 路径、revision、阶段文件路径和阻断项。

撰写视图不得把阶段 Markdown、DOCX 或其他导出文件当作默认事实来源。人工修改阶段文件后，必须由用户明确选择重新导入、仅作外部参考，或生成 Patch。

阶段文件生成脚本：

scripts/export_drafting_deliverable.py
