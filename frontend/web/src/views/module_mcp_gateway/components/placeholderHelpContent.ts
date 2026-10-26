export interface PlaceholderVariableRow {
  name: string;
  meaning: string;
  source: string;
}

export interface PlaceholderExample {
  caption: string;
  code: string;
}

export interface PlaceholderHelpContent {
  title: string;
  intro: string;
  variables: PlaceholderVariableRow[];
  usage: string[];
  examples: PlaceholderExample[];
}

const SHARED_INTRO =
  "语法使用双花括号，例如 {{user.uid}}。只认 {{system.键}}、{{user.uid}}、{{user.attr.键}}、{{auth.键}}。值只来自业务系统参数、绑定标识/属性、鉴权缓存变量；MCP 入参不能覆盖这些占位符。找不到对应值时，占位符原文保留，不报错清空。";

export const AUTH_PLACEHOLDER_HELP: PlaceholderHelpContent = {
  title: "变量使用说明",
  intro: SHARED_INTRO,
  variables: [
    {
      name: "{{system.xxx}}",
      meaning: "业务系统参数",
      source: "该系统配置里的 params",
    },
    {
      name: "{{user.uid}}",
      meaning: "当前调用用户在该系统的唯一标识",
      source: "绑定的 uid_value",
    },
    {
      name: "{{user.attr.xxx}}",
      meaning: "绑定上的可选属性",
      source: "系统声明的属性字段 + 绑定填值",
    },
    {
      name: "{{auth.xxx}}",
      meaning: "鉴权缓存变量",
      source: "登录请求里还没有；勿在换凭证请求里使用。custom 用「捕获变量」写入缓存后，供 REST 使用",
    },
  ],
  usage: [
    "地址：URL 可写 system / user 占位符。",
    "自定义请求：请求头、Query、Form 的值，以及 JSON Body 里的字符串，可写 system / user 占位符。",
    "custom：用「捕获变量」表单从登录响应取出多个字段，写入缓存后对应 {{auth.变量名}}。",
    "fixed：系统自动 POST {uid_field: uid}，不必手写 {{user.uid}}；结果写入 {{auth.access_token}}。",
    "interactive：主要配验证页 URL 与回调取值规则。",
  ],
  examples: [
    {
      caption: "custom 捕获变量 + 取值规则里的有效期",
      code: `捕获变量:
  access_token ← json ← data.token
  tenant_id    ← json ← data.tenantId

取值规则（高级）:
{
  "expires_seconds": 3600
}`,
    },
  ],
};

export const REST_PLACEHOLDER_HELP: PlaceholderHelpContent = {
  title: "变量使用说明",
  intro: SHARED_INTRO,
  variables: [
    {
      name: "{{system.xxx}}",
      meaning: "业务系统参数",
      source: "该系统配置里的 params",
    },
    {
      name: "{{user.uid}}",
      meaning: "当前调用用户在该系统的唯一标识",
      source: "绑定的 uid_value",
    },
    {
      name: "{{user.attr.xxx}}",
      meaning: "绑定上的可选属性",
      source: "系统声明的属性字段 + 绑定填值",
    },
    {
      name: "{{auth.xxx}}",
      meaning: "鉴权缓存变量",
      source: "该用户在该业务系统上的缓存 vars（如 access_token、tenant_id）",
    },
  ],
  usage: [
    "请求头：JSON 的值可写占位符，常见写法 Authorization: Bearer {{auth.access_token}}。",
    "也可配合「Token 位置 / Token 字段 / 注入变量名」由系统自动注入；勿与手写 {{auth.xxx}} 重复塞两遍。",
    "接口地址里的 {参数名}（单花括号）来自 MCP 入参，与 {{...}} 不是同一套：先替换路径 {id} 等，再渲染 {{...}}。",
  ],
  examples: [
    {
      caption: "URL 路径参数（MCP 入参）",
      code: `/todos/{id}  +  {"id": 12}  →  /todos/12`,
    },
    {
      caption: "请求头",
      code: `{"Authorization": "Bearer {{auth.access_token}}", "X-Tenant": "{{auth.tenant_id}}"}`,
    },
  ],
};
