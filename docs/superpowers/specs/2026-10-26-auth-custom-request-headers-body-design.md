# 鉴权「自定义请求」：可编辑 Header 与可选 Body 类型

日期：2026-10-26  
状态：已批准（对话确认）  
范围：仅鉴权方法 `custom`（自定义请求）的请求外形配置与登录拼装

## 背景

「自定义请求」目前主要配置 URL、HTTP 方法，以及一整段「取值规则」JSON。`query` / `json` / `form` 埋在 `rule` 里，没有独立的请求头编辑，也没有明确的 Body 类型选择。管理员难以直观配置登录报文；`json` 与 `form` 同时存在时运行时以 form 为准，行为不透明。

## 目标

自定义请求支持：

- 用键值对编辑 **请求头**
- 用键值对编辑 **Query 参数**
- 选择 **Body 类型**：`none` / `json` / `form`
- 按类型编辑 Body（无则隐藏；JSON 文本框；Form 键值对）
- **取值规则**只负责从响应取出 token / 有效期等，不再承载请求外形

### 做

- 表与 API 为 custom 增加独立字段：`headers`、`query`、`body_type`、`body`
- 前端 custom 表单增加上述编辑器（键值对对齐调试页 Header 行编辑）
- 登录拼装：custom 只读新字段；fixed / basic / interactive 行为不变（basic 仍从 `rule` 读 query/json/form）
- 迁移旧 `rule` 中的请求段到新字段，并从 `rule` 删除这些键
- 更新 custom 方法介绍文案与占位符说明中的适用位置

### 不做

- 不给 basic / fixed / interactive 加同样的 Header / Body UI（basic 可后续单独做）
- 不支持 `raw` / `multipart` Body
- 不做 Header 的 JSON 双模式编辑
- 不在鉴权登录请求中依赖 `{{token}}`
- 不改 token 响应取值规则的语义（`token_from` 等）

## 方案

采用 **独立字段存请求外形**（相对继续塞进 `rule`，或 API 独立、落库仍写回 `rule`）：

- `rule` 只表示「如何从响应取值」
- 请求外形有明确列与校验，避免 form/json 隐式互斥
- 迁移一次性把旧配置抬升到新列

## 数据模型

表 `mcp_biz_auth_config` 新增：

| 字段 | 类型 | 说明 |
|------|------|------|
| `headers` | JSON object `dict[str, str]`，可空 | 请求头；值可含占位符 |
| `query` | JSON object `dict[str, str]`，可空 | Query；值可含占位符 |
| `body_type` | String，可空 | custom 必填：`none` \| `json` \| `form`；非 custom 为 `null` |
| `body` | JSON，可空 | `none` → `null`；`json` → object；`form` → `dict[str, str]` |

`rule`：仅响应取值字段（如 `token_from`、`token_name`、`expires_seconds` 等），不再包含 `query` / `json` / `form` / `headers`。

### 校验（method === custom）

- `body_type` 必填，默认创建时为 `none`
- `body_type=none` → `body` 必须为空
- `body_type=json` → `body` 必须是 JSON object
- `body_type=form` → `body` 必须是 string→string 的 map
- `headers` / `query` 的 key 非空；空 key 行前端丢弃不提交
- 非 custom：提交的新字段忽略或存 `null`，登录不读

Create / Update / Out schema 同步暴露上述字段。Service 持久化这些列。

## 表单与占位符

方法为「自定义请求」时，在 URL / HTTP 方法下方展示：

1. **请求头** — 键值对行（添加 / 删除；对齐 `debug/index.vue` 的 `headerRows`）
2. **Query 参数** — 同上
3. **Body 类型** — 下拉：无 / JSON / Form
4. **Body** — 按类型：隐藏 / JSON textarea / Form 键值对
5. **取值规则** — JSON textarea；默认示例与说明只含响应取值，不含 `query`/`json`/`form`

编辑回填：API 对象拆成行；`body_type=json` 时 `JSON.stringify(body, null, 2)`。提交时再拼回对象。

方法切换：离开 custom 时清空四项（或提交时后端忽略）；进入 custom 时 `body_type` 默认 `none`。

### 占位符

- Header / Query / Form 的**值**、JSON body 的**字符串叶子**、URL：可用 `{{system.xxx}}`、`{{user.uid}}`、`{{user.attr.xxx}}`
- 鉴权请求中仍不要指望 `{{token}}`
- 更新 `placeholder-help` 鉴权适用位置：请求外形字段从「取值规则内的 query/json/form」改为独立 Header / Query / Body；取值规则仅说明响应取值
- custom 方法卡片：`fills` 写明 Header、Query、Body 类型与 Body；`when` 写参数可放在这些位置

## 登录拼装

`AuthClient._login_request`：

| 方法 | 行为 |
|------|------|
| `fixed` | 不变：`POST` + `{uid_field: uid}`，忽略新字段 |
| `basic` | 仍从 `rule.query` / `rule.json` / `rule.form` 拼装，加 Basic Auth（本次不改 UI） |
| `custom` | `headers` → httpx `headers`；`query` → `params`；按 `body_type` 设 `json=` 或 `data=`；`none` 不带 body |
| `interactive` | 不变 |

占位符渲染与现网登录一致（`token=None`）。不额外强制用户 `Content-Type`（httpx 对 `json=` / `data=` 自带）。

### 错误

- body 与 body_type 不符等 → 创建/更新 API 422
- 登录 HTTP 非 2xx 或取值失败 → 与现网相同，刷新失败冒泡

## 迁移

1. Alembic 增加可空列：`headers`、`query`、`body`（JSON），`body_type`（String）。
2. 数据迁移：对 `method=custom`：
   - `rule.query` → 列 `query`；若 `rule` 曾有 `headers` → 列 `headers`
   - 若有 `form` → `body_type=form`，`body=form`；否则若有 `json` → `body_type=json`，`body=json`；否则 `body_type=none`，`body=null`
   - 从 `rule` 删除 `query` / `json` / `form` / `headers`，保留取值字段
3. 读路径兜底：custom 且新列全空、但 `rule` 仍含旧键时，按上规则即时提升；不强制在读时写回 DB（写回留给迁移或下次保存）。
4. 非 custom：新列保持 `null`；basic 的 `rule` 请求段不动。

## 测试与验收

- 单元/集成：custom 带 headers + query + 各 `body_type` 的登录拼装（mock httpx）
- 迁移后旧 custom 仍能换 token；取值字段不丢
- basic / fixed 回归不变
- 手动：新建/编辑 custom 回显正确；方法介绍与占位符说明文案正确

## 非目标回顾

Basic 鉴权本次不拆请求外形 UI；raw/multipart、Header JSON 双模式均不做。
