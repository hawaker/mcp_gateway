import { request } from "@utils";

const API_PATH = "/mcp-gateway/upstream";

function emptyToUndefined(value: string | undefined): string | undefined {
  const text = (value ?? "").trim();
  return text ? text : undefined;
}

export function toUpstreamPayload(body: UpstreamForm, mode: "create" | "update") {
  const credential = emptyToUndefined(body.credential_value);
  const payload: Record<string, unknown> = {
    name: (body.name ?? "").trim(),
    url: (body.url ?? "").trim(),
    credential_header: (body.credential_header ?? "").trim(),
  };
  if (mode === "create") {
    payload.code = (body.code ?? "").trim();
    payload.credential_value = credential ?? "";
  } else if (credential) {
    // 编辑时留空表示不改密文
    payload.credential_value = credential;
  }
  return payload;
}

const UpstreamAPI = {
  listUpstream(query?: UpstreamPageQuery) {
    return request<ApiResponse<PageResult<UpstreamTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  detailUpstream(id: number) {
    return request<ApiResponse<UpstreamTable>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  createUpstream(body: UpstreamForm) {
    return request<ApiResponse<UpstreamTable>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: toUpstreamPayload(body, "create"),
    });
  },

  updateUpstream(id: number, body: UpstreamForm) {
    return request<ApiResponse<UpstreamTable>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data: toUpstreamPayload(body, "update"),
    });
  },

  deleteUpstream(ids: number[]) {
    return request<ApiResponse>({
      url: `${API_PATH}/delete`,
      method: "delete",
      data: ids,
    });
  },

  listTool(query?: UpstreamToolPageQuery) {
    return request<ApiResponse<PageResult<UpstreamToolTable>>>({
      url: `${API_PATH}/tool/list`,
      method: "get",
      params: query,
    });
  },

  updateTool(id: number, selected: boolean) {
    return request<ApiResponse<UpstreamToolTable>>({
      url: `${API_PATH}/tool/update/${id}`,
      method: "put",
      data: { selected },
    });
  },

  refreshTools(id: number) {
    return request<ApiResponse<UpstreamToolSnapshot[]>>({
      url: `${API_PATH}/tool/refresh/${id}`,
      method: "post",
    });
  },
};

export default UpstreamAPI;

export interface UpstreamPageQuery extends PageQuery {
  name?: string;
  code?: string;
  url?: string;
  credential_header?: string;
}

export interface UpstreamTable extends BaseType {
  name?: string;
  code?: string;
  url?: string;
  credential_header?: string;
}

export interface UpstreamForm extends BaseFormType {
  name?: string;
  code?: string;
  url?: string;
  credential_header?: string;
  credential_value?: string;
}

export interface UpstreamToolPageQuery extends PageQuery {
  upstream_id?: number;
  remote_name?: string;
  external_name?: string;
  selected?: boolean;
}

export interface UpstreamToolTable extends BaseType {
  upstream_id?: number;
  remote_name?: string;
  external_name?: string;
  input_schema?: Record<string, unknown>;
  selected?: boolean;
}

export interface UpstreamToolSnapshot {
  remote_name: string;
  external_name: string;
  input_schema?: Record<string, unknown>;
  selected: boolean;
}
