import { request } from "@utils";

const API_PATH = "/mcp-gateway/biz-auth";

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
}
