# phase_01 材料准入

本阶段只界定本轮无效答辩材料，不判断理由成立。必须先明文确认 transaction、view=invalidity、submode=defense、profile=v2.1-invalidity、phase=phase_01、response_round、domain、operation 和是否写回。若明文选择与 AI 判断、案件 control、revision 或材料状态不一致，先质疑并暂停。

case_json_only 和 export_from_json 只读 case.json 受控投影；只有明确 bootstrap_import 或 reimport_material 且列明外部文件、策略和旧批次处理方式时才可读外部材料。普通继续、刷新、重算不触发外部读取。source_path 仅 provenance。

材料角色至少区分 target_patent、invalidity_request、supplemental_reason、requester_evidence、prior_response、patentee_evidence、search_result、official_procedure_notice、legal_reference_candidate，并保存完整文本、表格、附图/OCR、来源片段、页/段/图定位、批次和核验状态。

准入逐项记录本轮答辩性质、请求人原文及顺序、涉案权项版本、证据及组合、专利权人证据、新增事项、修改/最终请求是否需用户决定、缺失原文/定位/日期/译文/期限。独权 N.1 是主题名称、N.2 起为技术特征；从权 N.1 是首个附加特征。产品与方法分开建模。结果只能是 ready、partial、blocked、need_reimport 或 challenge_required。