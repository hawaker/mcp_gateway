import { request } from "@utils";

const USER_PATH = "/mcp-gateway/biz-user";
const GROUP_PATH = "/mcp-gateway/biz-user-group";

const BizUserAPI = {
  listUser(query?: BizUserPageQuery) {
    return request<ApiResponse<PageResult<BizUserTable>>>({
      url: `${USER_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  createUser(body: BizUserForm) {
    return request<ApiResponse<BizUserTable>>({
      url: `${USER_PATH}/create`,
      method: "post",
      data: body,
    });
  },

  listGroup(query?: BizUserGroupPageQuery) {
    return request<ApiResponse<PageResult<BizUserGroupTable>>>({
      url: `${GROUP_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  createGroup(body: BizUserGroupForm) {
    return request<ApiResponse<BizUserGroupTable>>({
      url: `${GROUP_PATH}/create`,
      method: "post",
      data: body,
    });
  },

  addGroupMembers(groupId: number, userIds: number[]) {
    return request<ApiResponse<{ id: number; user_ids: number[] }>>({
      url: `${GROUP_PATH}/${groupId}/members`,
      method: "post",
      data: { user_ids: userIds },
    });
  },
};

export default BizUserAPI;

export interface BizUserPageQuery extends PageQuery {
  name?: string;
  enabled?: boolean;
}

export interface BizUserTable extends BaseType {
  name?: string;
  email?: string;
  mobile?: string;
  nickname?: string;
  enabled?: boolean;
}

export interface BizUserForm extends BaseFormType {
  name?: string;
  email?: string;
  mobile?: string;
  nickname?: string;
  enabled?: boolean;
}

export interface BizUserGroupPageQuery extends PageQuery {
  name?: string;
  enabled?: boolean;
}

export interface BizUserGroupTable extends BaseType {
  name?: string;
  enabled?: boolean;
}

export interface BizUserGroupForm extends BaseFormType {
  name?: string;
  enabled?: boolean;
}
