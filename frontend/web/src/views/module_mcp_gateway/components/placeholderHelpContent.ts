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
  "语法使用双花括号，例如 {{user.uid}}。只认 {{system.键}}、{{user.uid}}、{{user.attr.键}}、{{token}}。值只来自业务系统参数、绑定标识/属性、业务 token；MCP 入参不能覆盖这些占位符。找不到对应值时，占位符原文保留，不报错清空。";

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
      name: "{{token}}",
      meaning: "业务 token",
      source: "换 token 的登录请求里一般拿不到；勿指望在鉴权请求里使用",
    },
  ],
  usage: [
    "地址：URL 可写占位符。",
    "取值规则：JSON 里 query / json / form 对象的值可写占位符（custom / basic）。",
    "fixed：系统自动 POST {uid_field: uid}，不必手写 {{user.uid}}。",
    "interactive：主要配验证页 URL 与回调取值规则；登录请求本身不走这些占位符换 token。",
  ],
  examples: [
    {
      caption: "custom 的取值规则片段",
      code: `{
  "query": { "userId": "{{user.uid}}" },
  "json": { "dept": "{{user.attr.dept}}", "appKey": "{{system.app_key}}" },
  "token_from": "json",
  "token_name": "access_token",
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
      name: "{{token}}",
      meaning: "业务 token",
      source: "调用业务接口时可用（鉴权成功后缓存中的 token）",
    },
  ],
  usage: [
    "请求头：JSON 的值可写占位符，常见写法 Authorization: Bearer {{token}}。",
    "也可配合「Token 位置 / Token 字段」由系统自动注入；勿与手写 {{token}} 重复塞两遍。",
    "接口地址里的 {参数名}（单花括号）来自 MCP 入参，与 {{...}} 不是同一套：先替换路径 {id} 等，再渲染 {{...}}。",
  ],
  examples: [
    {
      caption: "URL 路径参数（MCP 入参）",
      code: `/todos/{id}  +  {"id": 12}  →  /todos/12`,
    },
    {
      caption: "请求头",
      code: `{"Authorization": "Bearer {{token}}", "X-User": "{{user.uid}}"}`,
    },
  ],
};
