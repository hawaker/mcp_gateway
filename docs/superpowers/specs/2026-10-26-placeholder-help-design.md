# 鉴权 / REST 工具对话框变量说明设计

日期：2026-10-26  
状态：已批准（对话确认）  
范围：新增/编辑鉴权、新增/编辑 REST 工具对话框内增加变量使用说明

## 背景

管理员在配置鉴权与 REST 工具时，需要在 URL、请求头、取值规则等处填写占位符。后端只认四种 `{{...}}` 变量，值来自业务系统参数、绑定与业务 token；MCP 入参不能覆盖它们。REST 工具 URL 另有单花括号 `{参数}`，来自 MCP 入参，与 `{{...}}` 不是同一套。

当前表单仅有字段 placeholder 短提示（如请求头里的 `{{user.uid}}`、`{{token}}`），缺少完整说明，容易写错或混用两种语法。

## 目标

在「新增鉴权 / 修改鉴权」与「新增 REST 工具 / 修改 REST 工具」对话框内，于表单上方增加**默认展开、可折叠**的变量使用说明，详细说明如何使用变量。

### 做

- 共享可折叠组件 + 鉴权 / REST 两套文案（props 传入）
- 覆盖四种 `{{...}}` 变量、来源、适用字段、示例
- REST 页额外说明 `{参数}` 与 `{{...}}` 的区别，以及 Token 位置与手写 `{{token}}` 的关系
- 新增与编辑共用同一对话框，挂一次即可

### 不做

- 不改后端占位符逻辑、不新增变量种类
- 不改取值规则 schema；不做「点选插入变量」
- 不做独立帮助页或路由
- 不写自动化 UI 测试

## 方案

采用 **共享组件 + 两套 props 文案**（相对各自写死与硬抽共享变量表）：折叠与样式一处维护；鉴权与 REST 字段差异大，文案分开更清晰。

## 组件

**路径：** `frontend/web/src/views/module_mcp_gateway/components/PlaceholderHelp.vue`

**交互：** `ElCollapse` / `ElCollapseItem`，默认展开；标题固定为「变量使用说明」（可由 prop 覆盖）。

**Props：**

| Prop | 类型 | 说明 |
|------|------|------|
| `title` | `string` | 折叠项标题，默认「变量使用说明」 |
| `intro` | `string` | 一段总述（语法、不覆盖规则、找不到则保留原文） |
| `variables` | `{ name, meaning, source }[]` | 变量表 |
| `usage` | `string[]` | 适用位置 / 写法要点 |
| `examples` | `{ caption, code }[]` | 示例（`code` 为纯文本，预格式化展示） |

样式贴近现有鉴权对话框的 `auth-note`，不另搞一套视觉主题。

## 挂载位置

| 页面 | 文件 | 位置 |
|------|------|------|
| 鉴权 | `frontend/web/src/views/module_mcp_gateway/auth/index.vue` | 现有「同一业务系统同时只启用一条…」提示**下方**、`FaForm` **上方** |
| REST 工具 | `frontend/web/src/views/module_mcp_gateway/rest_tool/index.vue` | `FaForm` **上方**、调试区**上方** |

文案常量可与页面同文件，或放在同目录的 `placeholderHelpContent.ts`；以不重复、易改文案为准。

## 文案：共同规则

两套 intro 均须写清：

- 语法：双花括号，如 `{{user.uid}}`
- 只认：`{{system.键}}`、`{{user.uid}}`、`{{user.attr.键}}`、`{{token}}`
- 值只来自业务系统参数、绑定标识/属性、业务 token；**MCP 入参不能覆盖这些占位符**
- 找不到对应值时，占位符**原文保留**，不报错清空

## 文案：鉴权页

### 变量表

| 变量 | 含义 | 来源 |
|------|------|------|
| `{{system.xxx}}` | 业务系统参数 | 该系统配置里的 `params` |
| `{{user.uid}}` | 当前调用用户在该系统的唯一标识 | 绑定的 `uid_value` |
| `{{user.attr.xxx}}` | 绑定上的可选属性 | 系统声明的属性字段 + 绑定填值 |
| `{{token}}` | 业务 token | 换 token 的登录请求里一般**拿不到**；勿指望在鉴权请求里使用 |

### 适用位置

- **地址** URL 可写占位符
- **取值规则** JSON 里的 `query` / `json` / `form` 对象的**值**可写占位符（custom / basic）
- **fixed**：系统自动 POST `{uid_field: uid}`，不必手写 `{{user.uid}}`
- **interactive**：主要配验证页 URL 与回调取值规则；登录请求本身不走这些占位符换 token

### 示例

custom 的 `rule` 片段：

```json
{
  "query": { "userId": "{{user.uid}}" },
  "json": { "dept": "{{user.attr.dept}}", "appKey": "{{system.app_key}}" },
  "token_from": "json",
  "token_name": "access_token",
  "expires_seconds": 3600
}
```

## 文案：REST 工具页

### 变量表

| 变量 | 含义 | 来源 |
|------|------|------|
| `{{system.xxx}}` | 业务系统参数 | 该系统配置里的 `params` |
| `{{user.uid}}` | 当前调用用户在该系统的唯一标识 | 绑定的 `uid_value` |
| `{{user.attr.xxx}}` | 绑定上的可选属性 | 系统声明的属性字段 + 绑定填值 |
| `{{token}}` | 业务 token | 调用业务接口时**可用**（鉴权成功后缓存中的 token） |

### 适用位置

- **请求头** JSON 的值（常见：`"Authorization": "Bearer {{token}}"`）
- 也可配合「Token 位置 / Token 字段」由系统自动注入；勿与手写 `{{token}}` 重复塞两遍
- **接口地址** 的 `{参数名}`（单花括号）来自 **MCP 入参**，与 `{{...}}` 不是同一套：先替换路径 `{id}` 等，再渲染 `{{...}}`

### 示例

- URL：`/todos/{id}` → 入参 `{"id": 12}` → `/todos/12`
- Headers：`{"Authorization": "Bearer {{token}}", "X-User": "{{user.uid}}"}`

## 验收

- 打开「新增鉴权 / 修改鉴权」：表单上方有默认展开的变量说明，内容为鉴权版
- 打开「新增 REST 工具 / 修改 REST 工具」：同上，内容为 REST 版
- 可折叠收起
- 文案覆盖四种变量、适用字段、示例，以及 REST 页 `{参数}` vs `{{...}}` 的区别

## 实现提示

- 仅改前端上述视图与新组件；无后端、无迁移
- 遵循现有 Vue / Element Plus 用法；中文文案与现有鉴权说明语气一致
