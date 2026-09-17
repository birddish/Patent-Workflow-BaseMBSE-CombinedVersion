# 撰写阶段自动化入口

自动编排脚本为 scripts/run_drafting_stage.py。

它执行以下顺序：

1. 读取案件主 JSON；
2. 检查用户是否明文提供或已登记撰写模式；
3. 检查该模式是否与 JSON 中的 AI 推荐模式一致；
4. 不一致时返回 blocked，不继续写入；
5. 读取当前撰写阶段所需 JSON；
6. 生成阶段 Markdown 文件；
7. 在 control.deliverables 中登记文件、来源 revision 和状态；
8. 更新 control.stage_status 和 control.last_drafting_delivery；
9. 原子写回 case.json；
10. 返回生成文件的相对路径和下一步人工确认要求。

## 调用边界

该入口只接受 case.json，不接受 DOCX、PDF、图片或其他外部材料作为阶段计算输入。
首次导入或明确重新导入必须在总控事务中先完成，之后再运行本入口。

## 示例

在已经由用户明文确认写作模式，且该模式与 JSON 中的推荐模式一致时，运行：

python scripts/run_drafting_stage.py --case-json <案件目录>/case.json --stage 03-claim-core --writing-mode <用户确认的模式>

结果会写入：

deliverables/03-claim-core/

并登记到：

case.json 的 control.deliverables。

如果用户没有明确选择模式，或选择与 AI 判断不一致，脚本返回 blocked，不生成阶段交付物。
