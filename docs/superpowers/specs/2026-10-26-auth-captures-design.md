# 自定义鉴权多变量 captures 设计

日期：2026-10-26  
状态：已批准（对话确认）  
范围：custom 鉴权从响应抽取多个变量，缓存后供 REST 以 `{{auth.xxx}}` 使用；移除 `{{token}}`

## 背景

当前鉴权成功后 Redis 只存 `access_token` / `expires_at` / `token_type`，REST 仅能用 `{{token}}`。部分 OA 的自定义登录响应还会返回 `tenant_id`、`session` 等字段，需要一并保存并在后续 REST 调用中引用。

## 目标

- **仅 custom** 支持配置多条 `captures`，从登录响应取出多个命名变量  
- 变量统一以 `{{auth.键}}` 在 REST（及需渲染的业务请求模板）中使用  
- **删除** `{{token}}`，不做兼容别名  
- `access_token` **非强制**；整包用固定 TTL，响应过期字段可选覆盖  
- 其它鉴权方法仍单 token 抽取，写入 `vars.access_token`，以便统一占位符

### 做

- 扩展 TokenBundle / Redis 为变量包 `{ vars, expires_at }`  
- custom rule：`captures[]` + `expires_seconds`（及可选现有 expires_*）  
- 占位符引擎增加 `{{auth.xxx}}`，移除 `{{token}}`  
- REST「Token 位置」保留，增加「注入变量名」（默认 `access_token`）  
- 鉴权 UI：custom 下表单式多行 captures 编辑器  
- 更新变量说明文案；token 缓存管理展示适配 vars  
- 401：删整包 → 重登 → 重试一次

### 不做

- fixed / basic / interactive 不配多 captures  
- 每变量独立 TTL  
- `{{token}}` 兼容层  
- 不改 MCP 协议

## 方案

采用 **变量包 + captures 列表**（相对并行第二套 Redis 键）：一次缓存、一次过期、一次 401 刷新，与现有锁刷新路径一致。

## 缓存模型

Redis 键仍为 `mcp:biz-token:{user_id}:{system_id}`，值为：

```json
{
  "vars": {
    "access_token": "...",
    "tenant_id": "..."
  },
  "expires_at": "2026-10-26T12:00:00+00:00"
}
```

- `vars` 至少一个键；不要求含 `access_token`  
- TTL：管理员 `expires_seconds`；若配置了 `expires_from` / `expires_name` / `expires_unit` 等并从响应取到过期，则以其算出的 `expires_at` **覆盖**固定 TTL  
- 到期整包失效，下次调用重新登录

`TokenBundle`（或重命名后的等价结构）携带 `vars: dict[str, str]` 与 `expires_at`。旧缓存若只有 `access_token` 字段，读取时升为 `vars.access_token`（一次性读兼容，写入只写新格式）。

## custom `captures`

取值规则（`rule`）在保留 `query` / `json` / `form` 请求配置之外：

```json
{
  "captures": [
    { "name": "access_token", "from": "json", "path": "data.token" },
    { "name": "tenant_id", "from": "json", "path": "data.tenantId" },
    { "name": "session", "from": "header", "path": "X-Session-Id" }
  ],
  "expires_seconds": 3600
}
```

| 字段 | 说明 |
|------|------|
| `name` | 写入 `vars` 的键；`{{auth.name}}`；`[A-Za-z0-9_]+`；同规则内唯一 |
| `from` | `header` \| `json` \| `form` \| `text` \| `regex`（复用现有抽取） |
| `path` | 对应原 `token_name`；`text` 可空；header 的 Set-Cookie 仍可用现有 cookie 约定 |

- `captures` 至少 1 条  
- custom **不再使用** 顶层 `token_from` / `token_name` 作为主路径；若旧数据仍只有这两项，读取时视为单条 `captures[{ name: "access_token", from: token_from, path: token_name }]`（读兼容，保存后写成 `captures`）

## 其它鉴权方法

fixed / basic / interactive：仍按现有单 token 规则抽取，结果写入 `vars = { "access_token": <值> }`（`token_type` 可不进 vars，或写入 `vars.token_type`——实现取不进 vars，避免占位符噪音）。

## 占位符

| 语法 | 含义 |
|------|------|
| `{{auth.键}}` | 当前用户×系统缓存 `vars[键]` |
| `{{system.xxx}}` | 系统参数（不变） |
| `{{user.uid}}` / `{{user.attr.xxx}}` | 绑定（不变） |

- **删除** `{{token}}`（后端正则、前端说明、示例、字段 placeholder 全部去掉）  
- 缺失键：原文保留  
- custom **登录请求**渲染：仍只有 system / user，**没有** auth（尚未登录）  
- REST / 业务请求：先 `ensure` 缓存有效，再渲染含 `{{auth.*}}` 的模板

## REST Token 注入

保留「Token 位置」（header / query / body）：

- 新增「注入变量名」字段（如 `token_var`），默认 `access_token`  
- 注入值为 `vars[token_var]`；若键不存在则该次注入为空或跳过（实现选：跳过并记日志/调试可见，不抛成硬错误，与占位符「保留原文」策略区分——自动注入缺键时不写该 header）  
- Headers 中可继续手写 `{{auth.xxx}}`；勿与自动注入重复塞同一 header

现有 `token_name` 仍表示注入到的 **HTTP 字段名**（如 `Authorization`）；`token_var` 表示从哪个 auth 变量取值。Bearer 前缀策略：若位置为 header 且字段为 Authorization，可保持现有 Bearer 包装行为（若有），否则原文注入。

## 401 刷新

custom（及仍走同步登录的 fixed/basic）：业务接口 401 → 删整包缓存 → 重新登录 → 用新 `vars` 重试一次。不要求 `vars` 含 `access_token`。

interactive：行为不变（不自动重登，返回验证链接）。

## 前端

### 鉴权对话框（custom）

- **表单式多行** captures 编辑器：每行「变量名 / from / path」，可增删行  
- 另有 `expires_seconds`（及可选响应过期配置，可仍放在取值规则高级 JSON，或同表单字段）  
- `query` / `json` / `form` 请求体：可继续用现有 rule JSON 区，或拆字段；至少保证 captures 为表单，序列化进 `rule.captures`  
- 非 custom 方法：隐藏 captures 编辑器，沿用现有单 token 取值规则 UI

### REST 工具

- 增加「注入变量名」（默认 `access_token`）  
- 变量说明与 placeholder：去掉 `{{token}}`，增加 `{{auth.xxx}}`；注明 custom 多变量

### 变量说明组件

更新 `placeholderHelpContent.ts`：鉴权版说明 custom captures；REST 版以 `{{auth.*}}` 为主。

### Token 缓存管理

列表展示适配：显示 `vars` 键名摘要与 `expires_at`；值默认遮罩。

## 验收

- custom 配置 ≥2 条 captures → REST Headers 中 `{{auth.a}}`、`{{auth.b}}` 均被替换  
- 无 `access_token` 的 captures 可缓存并用于 REST / 注入变量名  
- 固定 TTL 与响应过期覆盖生效  
- 401 整包重登并重试一次  
- 代码与文案中无 `{{token}}` 占位符语法  
- custom 下可用表单增删 captures 行并成功保存、回显

## 实现提示

- 优先改：`auth/extract.py`、`auth/client.py`、`token_cache/store.py`、`rest_tool/render.py`、assemble/注入路径、鉴权与 REST 前端、placeholder 文案、相关 pytest  
- 旧 Redis JSON 读时升级；写入只写新格式  
- 测试覆盖：多 captures、缺 access_token、`{{auth.x}}` 渲染、401 重登、旧 rule 升 captures、拒绝 `{{token}}`
