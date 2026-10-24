import { request } from "@utils";

const API_PATH = "/mcp-gateway/rest-tool";

function parseObject(text: string | undefined, message: string): Record<string, unknown> {
  const raw = (text ?? "").trim();
  if (!raw) return {};
  const parsed = JSON.parse(raw) as unknown;
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(message);
  }
  return parsed as Record<string, unknown>;
}

function emptyToNull(value: string | undefined): string | null {
  const text = (value ?? "").trim();
  return text ? text : null;
}

export function toRestToolPayload(body: RestToolForm) {
  const timeout = body.timeout_ms;
  return {
    name: body.name,
    display_name: body.display_name,
    url: body.url,
    description: emptyToNull(body.description),
    request_type: body.request_type || "GET",
    headers: parseObject(body.headers_text, "请求头须为 JSON 对象"),
    input_schema: parseObject(body.input_schema_text, "入参结构须为 JSON 对象"),
    output_schema: parseObject(body.output_schema_text, "出参结构须为 JSON 对象"),
    jsonpath_filter: emptyToNull(body.jsonpath_filter),
    query_mapping: parseObject(body.query_mapping_text, "Query 映射须为 JSON 对象"),
    header_mapping: parseObject(body.header_mapping_text, "Header 映射须为 JSON 对象"),
    timeout_ms: timeout === undefined || timeout === null || Number.isNaN(Number(timeout)) ? null : Number(timeout),
    token_in: body.token_in || "header",
    token_name: emptyToNull(body.token_name),
    enabled: body.enabled ?? true,
    system_id: body.system_id,
  };
}

const RestToolAPI = {
  listTool(query?: RestToolPageQuery) {
    return request<ApiResponse<PageResult<RestToolTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  detailTool(id: number) {
    return request<ApiResponse<RestToolTable>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  createTool(body: RestToolForm) {
    return request<ApiResponse<RestToolTable>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: toRestToolPayload(body),
    });
  },

  updateTool(id: number, body: RestToolForm) {
    return request<ApiResponse<RestToolTable>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data: toRestToolPayload(body),
    });
  },

  debugTool(body: RestToolDebugRequest) {
    return request<ApiResponse<RestToolDebugResult>>({
      url: `${API_PATH}/debug`,
      method: "post",
      data: {
        draft: toRestToolPayload(body),
        user_id: body.user_id,
        arguments: body.arguments ?? {},
        reveal: body.reveal ?? false,
      },
    });
  },
};

export default RestToolAPI;

export interface RestToolPageQuery extends PageQuery {
  name?: string;
  system_id?: number;
  request_type?: string;
  enabled?: boolean;
}

export interface RestToolTable extends BaseType {
  name?: string;
  display_name?: string;
  url?: string;
  description?: string | null;
  request_type?: string;
  headers?: Record<string, unknown>;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  jsonpath_filter?: string | null;
  query_mapping?: Record<string, unknown>;
  header_mapping?: Record<string, unknown>;
  timeout_ms?: number | null;
  token_in?: string;
  token_name?: string | null;
  enabled?: boolean;
  system_id?: number;
}

export interface RestToolForm extends BaseFormType {
  name?: string;
  display_name?: string;
  url?: string;
  description?: string;
  request_type?: string;
  headers_text?: string;
  input_schema_text?: string;
  output_schema_text?: string;
  jsonpath_filter?: string;
  query_mapping_text?: string;
  header_mapping_text?: string;
  timeout_ms?: number | null;
  token_in?: string;
  token_name?: string;
  enabled?: boolean;
  system_id?: number;
}

export interface RestToolDebugRequest extends RestToolForm {
  user_id: number;
  arguments?: Record<string, unknown>;
  reveal?: boolean;
}

export interface RestToolDebugResult {
  status?: number | null;
  request?: Record<string, unknown> | null;
  response?: unknown;
  link?: string | null;
}
