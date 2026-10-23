import { request } from "@utils";

const API_PATH = "/mcp-gateway/mail";

const MailAPI = {
  listMailLog(query?: MailLogPageQuery) {
    return request<ApiResponse<PageResult<MailLogTable>>>({
      url: `${API_PATH}/log/list`,
      method: "get",
      params: query,
    });
  },

  sendForGroup(groupId: number) {
    return request<ApiResponse<MailLogTable[]>>({
      url: `${API_PATH}/group/${groupId}`,
      method: "post",
    });
  },

  sendForUserGroup(userGroupId: number) {
    return request<ApiResponse<MailLogTable[]>>({
      url: `${API_PATH}/user-group/${userGroupId}`,
      method: "post",
    });
  },

  sendForUser(userId: number) {
    return request<ApiResponse<MailLogTable[]>>({
      url: `${API_PATH}/user/${userId}`,
      method: "post",
    });
  },
};

export default MailAPI;

export interface MailLogPageQuery extends PageQuery {
  user_id?: number;
  group_id?: number;
  user_group_id?: number;
  channel?: "group" | "user_group" | "user";
  ok?: boolean;
  created_at_start?: string;
  created_at_end?: string;
}

export interface MailLogTable {
  id?: number;
  user_id?: number;
  group_id?: number;
  channel?: "group" | "user_group" | "user";
  ok?: boolean;
  reason?: string;
  created_at?: string;
}
