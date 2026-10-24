import { request } from "@utils";

const API_PATH = "/mcp-gateway/biz-binding";

function parseObject(text: string | undefined): Record<string, unknown> {
  const raw = (text ?? "").trim();
  if (!raw) return {};
  const parsed = JSON.parse(raw) as unknown;
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("绑定属性须为 JSON 对象");
  }
  return parsed as Record<string, unknown>;
}

const BizBindingAPI = {
  listBinding(query?: BizBindingPageQuery) {
    return request<ApiResponse<PageResult<BizBindingTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  detailBinding(id: number) {
    return request<ApiResponse<BizBindingTable>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  createBinding(body: BizBindingForm) {
    return request<ApiResponse<BizBindingTable>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: {
        user_id: body.user_id,
        system_id: body.system_id,
        uid_value: body.uid_value,
        attrs: body.attrs ?? parseObject(body.attrs_text),
        enabled: body.enabled ?? true,
      },
    });
  },

  updateBinding(id: number, body: BizBindingForm) {
    const data: Record<string, unknown> = {};
    if (body.uid_value !== undefined) data.uid_value = body.uid_value;
    if (body.enabled !== undefined) data.enabled = body.enabled;
    if (body.attrs !== undefined) data.attrs = body.attrs;
    else if (body.attrs_text !== undefined) data.attrs = parseObject(body.attrs_text);
    return request<ApiResponse<BizBindingTable>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data,
    });
  },
};

export default BizBindingAPI;

export interface BizBindingPageQuery extends PageQuery {
  user_id?: number;
  system_id?: number;
  uid_value?: string;
  enabled?: boolean;
}

export interface BizBindingTable extends BaseType {
  user_id?: number;
  system_id?: number;
  uid_value?: string;
  attrs?: Record<string, unknown>;
  enabled?: boolean;
}

export interface BizBindingForm extends BaseFormType {
  user_id?: number;
  system_id?: number;
  uid_value?: string;
  attrs?: Record<string, unknown>;
  attrs_text?: string;
  enabled?: boolean;
}
