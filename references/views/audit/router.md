# 审计视图渐进路由

规范源为 `references/routing/views/audit.json`。本文件只用于人工核对，不替代机器路由。

| submode | profile | phase | read_profile | 用途 |
|---|---|---|---|---|
| `status` | `l0` / `l1` / `l2` / `l3` | `audit` | `audit.{profile}` | 案件状态与阻断项 |
| `consistency` | `l0` / `l1` / `l2` / `l3` | `audit` | `audit.{profile}` | 版本、依赖和跨视图一致性 |
| `ownership` | `l0` / `l1` / `l2` / `l3` | `audit` | `audit.{profile}` | 字段所有权与越权 Patch |
| `dependencies` | `l0` / `l1` / `l2` / `l3` | `audit` | `audit.{profile}` | 依赖闭合、反向索引和失效传播 |

`D. 仅查看案件状态` 固定规范化为 `audit/status/l0/audit + domain=all`。

读取边界：L0 只返回数量、ID 和轻量状态；L1 返回当前审计 profile；L2 只返回指定对象及有界闭包；L3 只返回异常摘要、受影响 ID 和脱敏路径，不返回完整 `case.json`。

写入只允许 `/derived/audit`。审计只能报告问题；不得直接改写其他视图、`normalized` 或 `source_materials`。所有业务视图规则组均为禁止加载组。

