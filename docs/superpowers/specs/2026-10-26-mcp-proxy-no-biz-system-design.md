# MCP 代理：去掉业务系统，自带编码

日期：2026-10-26  
状态：已批准（对话确认；用户要求直接实现）  
范围：原「上游 MCP」改名为「MCP 代理」；去掉对业务系统的挂靠；代理自有不可变 `code`；调用日志增加 `upstream_id`

## 背景

上游 MCP 配置时必选业务系统，但运行时不用绑定、不用业务 token、不用 `{{system}}` 占位符。`system_id` 只用于工具名前缀与日志归属，造成表单误解。

## 目标

- 文案「上游 MCP」→「MCP 代理」
- 去掉 `system_id`；代理必填不可变英文 `code` + 可改 `name`
- 工具对外名 `{code}_{remote}`
- 调用日志上游调用写 `upstream_id`，`system_id=null`
- 迁移时删除原有上游 MCP、其工具、MCP 组内已勾选的上游工具（组本身保留）

### 不做

- 不给代理加业务绑定 / 占位符
- 不改 REST 工具与业务系统关系
- 不回填历史日志的 `upstream_id`

## 数据模型

**`mcp_upstream_mcp`**：删 `system_id`；加唯一 `code`（String 64，创建后不可改）、`name`（String 128，可改）；保留 url / 凭证字段。

**`mcp_call_log`**：加可空索引列 `upstream_id`（不强 FK）。

**迁移**：先删 `mcp_group_tool` 中上游来源行 → 清空 `mcp_upstream_tool` / `mcp_upstream_mcp` → 改表。

## 运行时

- 前缀与加载只用代理 `code`；不加载业务系统
- 权限与凭证行为不变
- 日志：上游 → `upstream_id`；REST → `system_id`

## 界面

- 菜单、CRUD、调试、MCP 组「上游工具」等文案改为「MCP 代理」相关用语
- 表单：名称、编码（创建可填，编辑只读）、地址、凭证请求头、凭证；去掉业务系统
- 列表/搜索按 name、code、url；调试展示 `name · code` 或 `code · url`
