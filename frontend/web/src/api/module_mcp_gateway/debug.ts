import { request } from "@utils";

const API_PATH = "/mcp-gateway/debug";

const McpDebugAPI = {
  session(body: McpDebugTarget) {
    return request<ApiResponse<McpDebugSessionResult>>({
      url: `${API_PATH}/session`,
      method: "post",
      data: body,
    });
  },

  toolsList(body: McpDebugTarget) {
    return request<ApiResponse<McpDebugToolsListResult>>({
      url: `${API_PATH}/tools/list`,
      method: "post",
      data: body,
    });
  },

  toolsCall(body: McpDebugCallRequest) {
    return request<ApiResponse<McpDebugToolsCallResult>>({
      url: `${API_PATH}/tools/call`,
      method: "post",
      data: body,
    });
  },
};

export default McpDebugAPI;

export type McpDebugTargetKind = "group" | "upstream" | "custom";
export type McpDebugTransport = "streamable_http" | "sse";

export interface McpDebugTarget {
  target: McpDebugTargetKind;
  group_id?: number;
  user_id?: number;
  transport?: McpDebugTransport;
  upstream_id?: number;
  url?: string;
  headers?: Record<string, string>;
  reveal?: boolean;
}

export interface McpDebugCallRequest extends McpDebugTarget {
  name: string;
  arguments?: Record<string, unknown>;
}

export interface McpDebugProtocol {
  request: string;
  response: string;
}

export interface McpDebugNetwork {
  status: number;
  request_headers: string;
  response_body: string;
}

export interface McpDebugSessionResult {
  server_info: Record<string, unknown>;
  protocol: McpDebugProtocol;
  network: McpDebugNetwork;
}

export interface McpDebugTool {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
}

export interface McpDebugToolsListResult {
  tools: McpDebugTool[];
  protocol: McpDebugProtocol;
  network: McpDebugNetwork;
}

export interface McpDebugToolsCallResult {
  result_text: string;
  protocol: McpDebugProtocol;
  network: McpDebugNetwork;
}
