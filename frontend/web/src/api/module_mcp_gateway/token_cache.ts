import { request } from "@utils";

const API_PATH = "/mcp-gateway/biz-token-cache";

function optionalId(value: unknown): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value)) return undefined;
  return value;
}

const BizTokenCacheAPI = {
  listCache(query?: BizTokenCacheQuery) {
    return request<ApiResponse<BizTokenCacheRow[]>>({
      url: API_PATH,
      method: "get",
      params: {
        page_no: query?.page_no,
        page_size: query?.page_size,
        user_id: optionalId(query?.user_id),
        system_id: optionalId(query?.system_id),
      },
    });
  },
};

export default BizTokenCacheAPI;

export interface BizTokenCacheQuery extends PageQuery {
  user_id?: number;
  system_id?: number;
}

export interface BizTokenCacheRow {
  user_id: number;
  system_id: number;
  vars?: Record<string, string>;
  var_keys?: string[];
  access_token: string;
  expires_at: string;
  token_type: string;
  expired: boolean;
}
