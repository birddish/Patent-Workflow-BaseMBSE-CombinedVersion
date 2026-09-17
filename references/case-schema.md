# 案件主 JSON 结构与读取协议

## 1. 权威边界与兼容原则

案件主文件固定为 <案件目录>/case.json。顶层继续保持四个权威层：

    source_materials  导入后的案件材料快照
    normalized        已提取并确认的规范化事实
    derived           MBSE、检索、撰写、答审、无效答辩意见陈述和审计的可重算结果
    control           路由、版本、依赖、确认、冲突、日志和治理状态

现有 schema_version 继续使用 case-json-1.0。本次索引和控制结构是可选扩展：

- 旧案件可以没有任何新索引、路由确认或日志摘要，仍按旧数组和四层结构读取；
- 新案件或发生过迁移的案件可以逐步增加新字段，不要求一次性重写全部集合；
- 新字段存在时，必须遵守本文件和 case-schema.json 的结构约束；
- 原始文件路径、URL、source_path 和 location 只保留 provenance，不授权任何后续事务回读外部文件。

## 2. 顶层最小形态

    {
      "schema_version": "case-json-1.0",
      "case": {
        "case_id": "CASE-001",
        "title": "",
        "technical_domain": "pending"
      },
      "runtime_policy": {
        "default_transaction": "case_json_only",
        "external_read_requires": "bootstrap_or_explicit_reimport"
      },
      "source_materials": {
        "import_batches": [],
        "documents": [],
        "evidence": [],
        "search_results": []
      },
      "normalized": {
        "technical_facts": [],
        "documents": [],
        "claims": [],
        "issues": [],
        "entities": []
      },
      "derived": {
        "mbse": {},
        "search": {},
        "drafting": {},
        "oa": {},
        "invalidity": {},
        "audit": {}
      },
      "control": {
        "current_revision": 0
      }
    }

control 的索引、路由和摘要字段均为可选；旧案件不因缺少这些字段而被强制迁移。

## 3. 业务集合的渐进索引形态

同一个业务集合允许两种形态。

### 旧数组形态

    "claims": [
      {"id": "CLM-001", "text": "..."}
    ]

### 新 by_id + order 形态

    "claims": {
      "by_id": {
        "CLM-001": {"id": "CLM-001", "text": "..."},
        "CLM-002": {"id": "CLM-002", "text": "..."}
      },
      "order": ["CLM-001", "CLM-002"]
    }

迁移规则：

- by_id 的键是稳定实体 ID；
- order 只保存展示或业务处理顺序，不是实体身份；
- order 中的 ID 必须能在 by_id 中找到；
- 已被替代、逻辑删除或仅保留历史的条目可以留在 by_id，是否进入 order 由当前有效集合决定；
- Patch 不得把数组下标当作稳定身份；旧数组只作为兼容读取形态；
- 不要求旧案件立即把所有数组转换为 by_id + order。

source_materials.import_batches/documents/evidence/search_results 和
normalized.technical_facts/documents/claims/issues/entities 已在 Schema 中正式声明这两种形态。derived 内的业务集合可以按同一约定逐步迁移。

## 4. source_materials 与模型投影边界

source_materials 保存后续 JSON-only 计算所需的材料快照，包括：

- 完整文本、段落、表格、页码、图号和 OCR/图形结构化信息；
- 用户确认的结构化内容；
- 文献全文、权利要求和可定位证据；
- 必要时由导入器写入 JSON 的原始二进制存档。

原始二进制可以保存在案件 JSON 的 raw_artifacts 或等价存档字段中，但它只属于存储层，不属于模型投影层。

任何发给模型的 L0/L1/L2/L3 投影、RoutePlan 输入或审计上下文：

- 不得包含 raw_artifacts；
- 不得包含 content_base64；
- 不得包含导入器使用的 raw_artifact_base64；
- 应返回来源 ID、JSON Pointer、文本摘录和必要 provenance，而不是二进制内容；
- source_path、location 和 URL 只能作为来源说明，不得被当作读取入口。

如案件暂存 control.model_projection 供审计，校验器会拒绝上述字段。control.projection_policy.forbidden_fields 应至少声明 raw_artifacts 和 content_base64。

## 5. control.object_index

object_index 是稳定实体 ID 到同一 case.json 内 JSON Pointer 的映射：

    "object_index": {
      "DOC-001": "/source_materials/documents/by_id/DOC-001",
      "CHAIN-002": "/derived/mbse/chains/by_id/CHAIN-002",
      "CLM-018": "/derived/drafting/claims/0"
    }

约束：

- 键必须是非空稳定实体 ID；
- 值必须是以 / 开头的 JSON Pointer；
- Pointer 必须能在当前案件 JSON 中解析到对象；
- 目标对象的 id 或明确的实体 *_id 必须与索引键一致；
- 同一 Pointer 不得映射给两个不同实体 ID；
- 旧数组可以暂时被索引，数组下标只表示当前存储位置，不得成为 Patch 的稳定身份；
- 对象移动或集合迁移后必须在同一事务中更新索引；
- object_index 缺失时，旧案件仍可使用遍历式读取，不强制补建。

## 6. control.reverse_dependency_index

该索引使用“被依赖实体 → 直接依赖它的实体列表”的方向：

    "reverse_dependency_index": {
      "CHAIN-002": ["PU-002", "CLM-018"],
      "PU-002": ["CLM-018"]
    }

它服务于局部失效传播和影响集计算，不替代派生对象自身的 dependency_ids/depends_on。

当该字段存在时：

- 每个值必须是无重复稳定 ID 数组；
- 列表中的依赖实体必须在案件中可识别；
- source_id <- dependent_id 必须能在依赖实体的 dependency_ids 或 depends_on 中找到正向关系；
- 每个派生对象已有的直接依赖都应能在反向索引中找到对应映射；
- 缺少整个反向索引的旧案件不触发这些新检查；
- 该索引是直接依赖索引，不要求把传递闭包重复写入每个条目。

## 7. 视图状态与局部读取

control.view_status 是轻量摘要，不承载完整业务结果：

    "view_status": {
      "mbse": {"status": "fresh", "active_ids": ["CHAIN-002"]},
      "search": {"status": "blocked", "reason_ids": ["GATE-007"]},
      "drafting": {"status": "working", "active_ids": ["CLM-018"]},
      "oa": {"status": "empty"},
      "invalidity": {"status": "empty"},
      "audit": {"status": "fresh"}
    }

允许的视图状态为：

    empty | fresh | working | stale | blocked | invalid

active_ids、reason_ids 只传 ID，不内嵌完整对象。详细 gate、问题、证据或业务实体通过 L1/L2 的指定 Pointer 或 ID 读取。

建议读取深度：

- L0：案件 ID、当前 revision、活动路由、各视图状态、数量和 ID 摘要；
- L1：当前操作的 JSON 投影，不读取其他视图的无关集合；
- L2：指定对象、直接依赖和有界证据摘录；
- L3：由脚本先输出异常、断裂引用、stale/invalid 对象和受影响路径，不把完整 case.json 原样送入模型。

## 8. active_route、确认和质疑解决

### 活动路由

`control.active_route` 保存已经规范化的完整路由；除纯导入外，六个字段均不得省略：

```json
{
  "active_route": {
    "route_id": "mbse.document",
    "transaction": "case_json_only",
    "view": "mbse",
    "submode": "document",
    "profile": "standard",
    "phase": "modeling",
    "domain": "electronics"
  }
}
```

`transaction` 只能是 `bootstrap_import`、`case_json_only`、`reimport_material` 或 `export_from_json`；`view` 只能是 `mbse`、`search`、`drafting`、`oa`、`invalidity` 或 `audit`。`submode`、`profile`、`phase` 和 `domain` 必须使用模式门输出的 canonical 值，不能把兼容别名写入控制区。

### 权威路由确认

`control.route_confirmation` 是已有案件业务执行的唯一权威确认，不得用 CLI 中的 `confirmed` 字样替代：

```json
{
  "route_confirmation": {
    "status": "confirmed",
    "confirmation_id": "CONF-001",
    "case_id": "CASE-INDEX-001",
    "base_revision": 2,
    "confirmed_revision": 3,
    "selected_route": {
      "transaction": "case_json_only",
      "view": "mbse",
      "submode": "document",
      "profile": "standard",
      "phase": "modeling",
      "domain": "electronics"
    },
    "confirmed_by": "user",
    "confirmed_at": "2026-09-15T00:00:00Z",
    "challenge_ids": ["CHALLENGE-001"]
  }
}
```

只有同时满足以下条件才可生成 `ready` RoutePlan 或执行导出、计算和 Patch：

- `status=confirmed` 且 `confirmation_id` 非空；
- `case_id` 与案件一致；
- `confirmed_revision` 与 `control.current_revision` 一致；
- `selected_route` 与本次 canonical 路由六个字段精确一致；
- 存在质疑时，对应 `challenge_id` 已记录在确认及解决记录中。

用户改选、案件 revision 变化或路由范围变化后，旧确认立即失效。advisory override 不是跳过确认；用户坚持后仍须生成新的 `confirmed` 记录。状态枚举为 `pending`、`confirmed`、`challenge_required`、`overridden`、`rejected` 或 `expired`，但只有满足上述完整绑定的 `confirmed` 可执行。

### 质疑解决

control.challenge_resolutions 是质疑记录数组，每个 challenge_id 只能出现一次：

    {
      "challenge_id": "CHALLENGE-001",
      "severity": "advisory",
      "status": "resolved",
      "user_selection": {
        "transaction": "case_json_only",
        "view": "mbse",
        "submode": "document"
      },
      "ai_recommendation": {
        "transaction": "case_json_only",
        "view": "drafting",
        "submode": "stage3"
      },
      "resolution": "keep_user_selection",
      "resolved_by": "user",
      "resolved_revision": 18,
      "override_reason": "用户只要求技术建模"
    }

severity：

    hard      硬冲突，必须改选、补材料或取消冲突请求，不能靠坚持绕过
    advisory 建议性冲突，用户再次明文坚持后可以保留原选择，但必须记录 override_reason

resolution：

    keep_user_selection | change_selection | cancel_transaction | supply_input

AI 判断只是候选建议，不得静默替换用户选择；用户选择与 AI 判断、案件状态、材料边界、阶段边界或 JSON-only 政策不一致时，必须先提出具体质疑并暂停。

## 9. 访问日志压缩摘要

逐事件 control.access_log 可以保留必要的审计证据；为避免每次读取都载入全部日志，增加可选的 control.access_log_summary：

    "access_log_summary": {
      "window_start": "2026-09-15T00:00:00Z",
      "window_end": "2026-09-15T01:00:00Z",
      "event_count": 436,
      "unique_path_count": 82,
      "by_level": {"L0": 32, "L1": 280, "L2": 124},
      "by_operation": {"read": 400, "write": 36},
      "by_root": {"case": 50, "normalized": 90, "derived": 260, "control": 36},
      "omitted_event_count": 400,
      "last_event_at": "2026-09-15T01:00:00Z"
    }

字段含义：

- event_count：摘要窗口内事件总数；
- unique_path_count：访问过的不同 JSON Pointer 数量；
- by_level、by_operation、by_root：紧凑计数映射；
- omitted_event_count：没有逐事件展开的事件数量，不能大于 event_count；
- window_start/window_end/last_event_at：摘要时间边界。

摘要不能伪造或替代需要留存的关键写入、冲突和用户确认事件。

## 10. 派生对象、版本和局部失效

所有可能影响结论的派生对象继续携带：

    status
    input_revision
    dependency_ids
    dependency_revisions
    rule_version
    computed_at

状态至少区分：

    fresh | stale | blocked | invalid

修改输入时，先通过 reverse_dependency_index 或兼容的遍历方式计算影响集，再只把相关对象标记为 stale/invalid。未受影响对象保持原状态。

## 11. 视图间最小接口

视图完成后只传递：

    {
      "completed_view": "mbse",
      "changed_paths": ["/derived/mbse/chains/CHAIN-002"],
      "created_ids": ["CHAIN-002"],
      "pending_ids": ["E-004"],
      "next_view": "drafting",
      "next_input_paths": ["/derived/mbse/chains/CHAIN-002"]
    }

下一视图必须从同一 case.json 按 Pointer/ID 重新读取，并核对输入 revision；不得将上一视图完整输出复制进对话作为事实源。

## 12. 无效答辩视图的兼容数据层

`invalidity` 是新增的可选派生视图。旧案件可以没有 `/derived/invalidity`，不因此被强制迁移；新建案件可由统一工具初始化为空对象。该视图的 Patch 所有权固定为 `/derived/invalidity`，不能写 `/derived/oa`、`/derived/drafting` 或 `/control`。

无效答辩使用固定路由：`view=invalidity`、`submode=defense`、`profile=v2.1-invalidity`，`phase=phase_01..phase_05`。`response_round` 表示首次答辩或补充答辩，作为派生对象的稳定数据字段/记录落点，不作为新的 submode。建议的业务集合包括 `invalidity_requests`、`invalidity_grounds`、`response_rounds`、`claim_feature_charts`、`evidence_assessments`、`argument_paths`、`defense_positions`、`statement_sections` 和 `response_statements`；每条可影响结论的派生记录仍必须携带 `status`、`input_revision`、`dependency_ids`、`dependency_revisions`、`rule_version` 和 `computed_at`。

MBSE 追溯记录以“无效理由/权项 → R/F/S/B/E 技术链 → 证据片段 → 单篇公开或组合路径 → 断点及证据状态 → 答辩位置”为最小闭环。工程链条断裂、证据不足或不能从材料确认只能标记为 `candidate`、`conditional`、`pending_review` 或 `blocked`，不得直接改写为法律结论。对外陈述不得暴露内部稳定 ID；应从同一 JSON 中按 ID 读取并生成。
