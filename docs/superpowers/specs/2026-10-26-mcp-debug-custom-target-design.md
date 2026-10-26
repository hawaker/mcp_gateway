# MCP 调试「自定义」目标设计

日期：2026-10-26  
状态：已批准（对话确认）  
范围：管理员 MCP 调试页增加自由 URL / Header 出站调试

## 背景

现有调试支持两种目标：

- `group`：经 `build_mcp_app` 连本网关 MCP 组（Streamable HTTP / SSE）
- `upstream`：用已保存上游凭证 `httpx` 出站（不写调用日志）

管理员需要连任意外部 MCP（未入库的 URL / Header）做 Inspector 式排查，而不新建上游记录。

## 目标

在调试页增加第三种目标 **「自定义」**：填 URL、Header、传输方式，由网关服务端出站完成 `initialize` / `tools/list` / `tools/call`。

### 做

- `target: "custom"` + `url` + `headers` + `transport`（`streamable_http` | `sse`）
- 复用现有三接口与 Protocol / Network / `reveal` 遮罩
- 不写调用日志（与上游一致）
- URL 仅允许 `http://` / `https://`（复用 `require_http_url`）

### 不做

- 不落库 URL / Header；不绑组 / 用户 / 上游
- 不做 IP / 内网黑名单（依赖现有调试权限；实现与文档注明服务端 SSRF 风险）
- 不改运行时 `/mcp/{group_id}` 行为
- 不新增权限码；不提供 stdio / prompts / resources

## 方案

采用 **服务端第三种 target**（相对「浏览器直连」与「临时扮上游」）：与现有 session / list / call、Protocol / Network、遮罩路径一致；自定义目标与上游一样不写调用日志。

## 请求模型

仍走：

- `POST /mcp-gateway/debug/session`
- `POST /mcp-gateway/debug/tools/list`
- `POST /mcp-gateway/debug/tools/call`

扩展 `DebugTargetSchema` / `DebugCallSchema`：

| 字段 | custom 要求 | 说明 |
|------|-------------|------|
| `target` | `"custom"` | 与 `group` / `upstream` 并列 |
| `url` | 必填 | `require_http_url` |
| `headers` | 可选，默认 `{}` | `dict[str, str]` |
| `transport` | 必填 | `streamable_http` \| `sse` |
| `reveal` | 可选 | 为真时不遮凭证 |
| `name` / `arguments` | 仅 tools/call | 同现有 |

`group` / `upstream` 校验不变。`custom` 不得要求 `group_id` / `user_id` / `upstream_id`。

## 后端流程

在 `DebugService._rpc` 增加 `custom` 分支 → `_custom_rpc(url, headers, transport, method, params)`。

### Header 合并

用户 Header 优先；缺省补：

- `Content-Type: application/json`（POST）
- `Accept: application/json, text/event-stream`（按传输需要）

### 传输

| 传输 | 行为 |
|------|------|
| `streamable_http` | `POST url`，JSON-RPC body；响应解码与现有一致（JSON / SSE 帧） |
| `sse` | `GET url` 开 SSE → 等 `endpoint` 事件 → `POST` 该 endpoint（相对路径相对原 URL 解析）→ 等 `message` |

超时约 30s（与上游调试一致）。可注入 `httpx` transport 便于单测。

### 遮罩与日志

- `secrets`：自定义 Header 中疑似凭证的值（名称为 `Authorization`，或名含 `token` / `secret` / `key` / `password` 的非空值）
- `reveal=false` 时 Protocol / Network 视图打 `***`
- **不写** MCP 调用日志
- 操作日志继续省略 debug 请求体（现有 `OperationLogRoute` 行为）

### 错误

- 缺字段 / 非法 URL / 非法传输 → 400，中文校验信息
- 出站超时 / 连接失败 → 业务异常
- 对方 HTTP 非预期或 JSON-RPC error → 仍返回 Protocol / Network，便于排障
- SSE 无 `endpoint` / 无 `message` → 与组调试相同文案

Controller 将 `url` / `headers` / `transport` 透传给 `DebugService`；权限码不变：

- `module_mcp_gateway:debug:session`
- `module_mcp_gateway:debug:tools-list`
- `module_mcp_gateway:debug:tools-call`

## 前端

文件：`frontend/web/src/views/module_mcp_gateway/debug/index.vue`、`api/module_mcp_gateway/debug.ts`。

- 目标 Radio 增加「自定义」
- 选中后显示：URL、传输（与组调试同一控件）、Header 键值行（可增删；空名丢弃）
- `buildBody()` 在 `custom` 时带 `url` / `headers` / `transport`
- 切换目标清空连接态（扩展现有 `watch`）
- 类型：`McpDebugTargetKind` 增加 `"custom"`
- Tools / Protocol / Network / reveal UI 不变

## 测试

- Schema：`custom` 缺 `url` / `transport` 失败；非法 scheme 失败；合法 body 通过
- Service：mock transport 覆盖 streamable 与 SSE 各一次 session；确认遮罩；确认不写 call log
- 前端：类型与 body 组装即可，不强制 E2E

## 验收标准

1. 调试页可选「自定义」，填 URL + Header + 传输后能连接并看到 serverInfo
2. tools/list、tools/call 可用；Protocol / Network 可见；默认遮 Header 凭证，「显示 token」可展开
3. 自定义调用不出现在调用日志
4. 组 / 上游调试行为不变
5. 上述后端测试通过

## 改动面

- `backend/app/modules/mcp_gateway/runtime/debug.py`（+ controller 透传）
- `frontend/web/src/views/module_mcp_gateway/debug/index.vue`
- `frontend/web/src/api/module_mcp_gateway/debug.ts`
- 对应单测
