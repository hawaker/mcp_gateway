import { request } from "@utils";

const API_PATH = "/mcp-gateway/biz-auth";

export type BizAuthBodyType = "none" | "json" | "form";

export function rowsToRecord(rows: { key: string; value: string }[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const row of rows) {
    const k = row.key.trim();
    if (!k) continue;
    out[k] = row.value;
  }
  return out;
}

export function recordToRows(record?: Record<string, string> | null): { key: string; value: string }[] {
  const entries = Object.entries(record ?? {});
  if (!entries.length) return [{ key: "", value: "" }];
  return entries.map(([key, value]) => ({ key, value: String(value ?? "") }));
}

function parseObject(text: string | undefined): Record<string, unknown> {
  const raw = (text ?? "").trim();
  if (!raw) return {};
  const parsed = JSON.parse(raw) as unknown;
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("取值规则须为 JSON 对象");
  }
  return parsed as Record<string, unknown>;
}

function toPayload(body: BizAuthForm): Record<string, unknown> {
  const data: Record<string, unknown> = {
    system_id: body.system_id,
    method: body.method,
    url: body.url,
    enabled: body.enabled ?? true,
    rule: parseObject(body.rule_text),
  };
  if (body.method === "custom" || body.method === "basic") {
    data.http_method = body.http_method;
  }
  if (body.method === "basic") {
    data.username = body.username;
    data.password = body.password;
  }
  if (body.method === "custom") {
    data.headers = body.headers ?? {};
    data.query = body.query ?? {};
    data.body_type = body.body_type ?? "none";
    data.body = body.body_type === "none" ? null : (body.body ?? null);
  }
  return data;
}

const BizAuthAPI = {
  listAuth(query?: BizAuthPageQuery) {
    return request<ApiResponse<PageResult<BizAuthTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  detailAuth(id: number) {
    return request<ApiResponse<BizAuthTable>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  createAuth(body: BizAuthForm) {
    return request<ApiResponse<BizAuthTable>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: toPayload(body),
    });
  },

  updateAuth(id: number, body: BizAuthForm) {
    return request<ApiResponse<BizAuthTable>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data: toPayload(body),
    });
  },
};

export default BizAuthAPI;

export type BizAuthMethod = "fixed" | "custom" | "basic" | "interactive";

export interface BizAuthPageQuery extends PageQuery {
  system_id?: number;
  method?: BizAuthMethod;
  enabled?: boolean;
}

export interface BizAuthTable extends BaseType {
  system_id?: number;
  method?: BizAuthMethod;
  enabled?: boolean;
  url?: string;
  rule?: Record<string, unknown>;
  http_method?: string;
  username?: string;
  password?: string;
  headers?: Record<string, string> | null;
  query?: Record<string, string> | null;
  body_type?: BizAuthBodyType | null;
  body?: Record<string, unknown> | null;
}

export interface BizAuthForm extends BaseFormType {
  system_id?: number;
  method?: BizAuthMethod;
  enabled?: boolean;
  url?: string;
  rule_text?: string;
  http_method?: string;
  username?: string;
  password?: string;
  headers?: Record<string, string> | null;
  query?: Record<string, string> | null;
  body_type?: BizAuthBodyType | null;
  body?: Record<string, unknown> | null;
  body_text?: string;
}
