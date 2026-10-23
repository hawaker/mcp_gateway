import { request } from "@utils";

const API_PATH = "/mcp-gateway/call-log/aggregate";

const CallLogAPI = {
  aggregate() {
    return request<ApiResponse<CallLogAggregate[]>>({
      url: API_PATH,
      method: "get",
    });
  },
};

export default CallLogAPI;

export interface CallLogAggregate {
  user_id: number;
  tool_name: string;
  count: number;
  elapsed_ms: number;
  created_at: string;
}
