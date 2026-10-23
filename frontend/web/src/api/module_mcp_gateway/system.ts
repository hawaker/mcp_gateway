import { request } from "@utils";

const API_PATH = "/mcp-gateway/biz-system";

function parseObject(text: string | undefined, message: string): Record<string, unknown> {
  const raw = (text ?? "").trim();
  if (!raw) return {};
  const parsed = JSON.parse(raw) as unknown;
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(message);
  }
  return parsed as Record<string, unknown>;
}

function splitFields(text: string | undefined): string[] {
  const seen = new Set<string>();
  const fields: string[] = [];
  for (const part of (text ?? "").split(/[\n,，]/)) {
    const item = part.trim();
    if (!item || seen.has(item)) continue;
    seen.add(item);
    fields.push(item);
  }
  return fields;
}

function toPayload(body: BizSystemForm, includeCode: boolean) {
  const data: Record<string, unknown> = {
    name: body.name,
    base_url: body.base_url,
    enabled: body.enabled ?? true,
    params: parseObject(body.params_text, "扩展参数须为 JSON 对象"),
    uid_field: body.uid_field,
    attr_fields: splitFields(body.attr_fields_text),
  };
  if (includeCode) data.code = body.code;
  return data;
}

const BizSystemAPI = {
  listSystem(query?: BizSystemPageQuery) {
    return request<ApiResponse<PageResult<BizSystemTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  detailSystem(id: number) {
    return request<ApiResponse<BizSystemTable>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  createSystem(body: BizSystemForm) {
    return request<ApiResponse<BizSystemTable>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: toPayload(body, true),
    });
  },

  updateSystem(id: number, body: BizSystemForm) {
    return request<ApiResponse<BizSystemTable>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data: toPayload(body, false),
    });
  },
};

export default BizSystemAPI;

export interface BizSystemPageQuery extends PageQuery {
  name?: string;
  code?: string;
  enabled?: boolean;
}

export interface BizSystemTable extends BaseType {
  name?: string;
  code?: string;
  base_url?: string;
  enabled?: boolean;
  params?: Record<string, unknown>;
  uid_field?: string;
  attr_fields?: string[];
}

export interface BizSystemForm extends BaseFormType {
  name?: string;
  code?: string;
  base_url?: string;
  enabled?: boolean;
  params_text?: string;
  uid_field?: string;
  attr_fields_text?: string;
}
