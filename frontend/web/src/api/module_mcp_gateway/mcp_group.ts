import { request } from "@utils";

const API_PATH = "/mcp-gateway/mcp-group";

function emptyToUndefined(value: string | undefined): string | undefined {
  const text = (value ?? "").trim();
  return text ? text : undefined;
}

const McpGroupAPI = {
  listGroup(query?: McpGroupPageQuery) {
    return request<ApiResponse<PageResult<McpGroupTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  detailGroup(id: number) {
    return request<ApiResponse<McpGroupTable>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  createGroup(body: McpGroupForm) {
    return request<ApiResponse<McpGroupTable>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: {
        name: (body.name ?? "").trim(),
        enabled: body.enabled !== false,
      },
    });
  },

  updateGroup(id: number, body: McpGroupForm) {
    return request<ApiResponse<McpGroupTable>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data: {
        name: (body.name ?? "").trim(),
        enabled: body.enabled !== false,
      },
    });
  },

  listTool(query?: McpGroupToolPageQuery) {
    return request<ApiResponse<PageResult<McpGroupToolTable>>>({
      url: `${API_PATH}/tool/list`,
      method: "get",
      params: query,
    });
  },

  createTool(groupId: number, body: McpGroupToolForm) {
    const externalName = emptyToUndefined(body.external_name);
    return request<ApiResponse<McpGroupToolTable>>({
      url: `${API_PATH}/tool/create`,
      method: "post",
      params: { group_id: groupId },
      data: {
        source: body.source,
        source_id: body.source_id,
        enabled: body.enabled !== false,
        ...(externalName ? { external_name: externalName } : {}),
      },
    });
  },

  updateTool(id: number, body: { external_name?: string; enabled?: boolean }) {
    return request<ApiResponse<McpGroupToolTable>>({
      url: `${API_PATH}/tool/update/${id}`,
      method: "put",
      data: body,
    });
  },

  listMember(query?: McpGroupMemberPageQuery) {
    return request<ApiResponse<PageResult<McpGroupMemberTable>>>({
      url: `${API_PATH}/member/list`,
      method: "get",
      params: query,
    });
  },

  createMember(groupId: number, body: McpGroupMemberForm) {
    return request<ApiResponse<McpGroupMemberTable>>({
      url: `${API_PATH}/member/create`,
      method: "post",
      params: { group_id: groupId },
      data: {
        principal_type: body.principal_type,
        principal_id: body.principal_id,
        enabled: body.enabled !== false,
      },
    });
  },

  updateMember(id: number, enabled: boolean) {
    return request<ApiResponse<McpGroupMemberTable>>({
      url: `${API_PATH}/member/update/${id}`,
      method: "put",
      data: { enabled },
    });
  },

  listCredential(query?: McpCredentialPageQuery) {
    return request<ApiResponse<PageResult<McpCredentialTable>>>({
      url: `${API_PATH}/credential/list`,
      method: "get",
      params: query,
    });
  },

  connectionInfo(userId: number, groupId: number) {
    return request<ApiResponse<McpConnectionInfo>>({
      url: `${API_PATH}/connection/${userId}/${groupId}`,
      method: "get",
    });
  },

  reissue(userId: number, groupId: number) {
    return request<ApiResponse<McpConnectionInfo>>({
      url: `${API_PATH}/credential/reissue`,
      method: "post",
      data: { user_id: userId, group_id: groupId },
    });
  },
};

export default McpGroupAPI;

export interface McpGroupPageQuery extends PageQuery {
  name?: string;
  enabled?: boolean;
}

export interface McpGroupTable extends BaseType {
  name?: string;
  enabled?: boolean;
}

export interface McpGroupForm extends BaseFormType {
  name?: string;
  enabled?: boolean;
}

export interface McpGroupToolPageQuery extends PageQuery {
  group_id?: number;
  source?: string;
  external_name?: string;
  enabled?: boolean;
}

export interface McpGroupToolTable extends BaseType {
  group_id?: number;
  source?: "rest" | "upstream";
  source_id?: number;
  external_name?: string;
  enabled?: boolean;
}

export interface McpGroupToolForm {
  source?: "rest" | "upstream";
  source_id?: number;
  external_name?: string;
  enabled?: boolean;
}

export interface McpGroupMemberPageQuery extends PageQuery {
  group_id?: number;
  principal_type?: string;
  principal_id?: number;
  enabled?: boolean;
}

export interface McpGroupMemberTable extends BaseType {
  group_id?: number;
  principal_type?: "user" | "group";
  principal_id?: number;
  enabled?: boolean;
}

export interface McpGroupMemberForm {
  principal_type?: "user" | "group";
  principal_id?: number;
  enabled?: boolean;
}

export interface McpCredentialPageQuery extends PageQuery {
  user_id?: number;
  group_id?: number;
}

export interface McpCredentialTable extends BaseType {
  user_id?: number;
  group_id?: number;
}

export interface McpConnectionInfo {
  streamable_http_url: string;
  sse_url: string;
  messages_url: string;
  authorization: string;
}
