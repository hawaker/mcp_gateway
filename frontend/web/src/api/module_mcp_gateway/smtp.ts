import { request } from "@utils";

const API_PATH = "/mcp-gateway/smtp";

function emptyToUndefined(value: string | undefined): string | undefined {
  const text = (value ?? "").trim();
  return text ? text : undefined;
}

export function toSmtpPayload(body: SmtpForm, mode: "create" | "update") {
  const password = emptyToUndefined(body.password);
  const data: Record<string, unknown> = {
    enabled: body.enabled ?? false,
    host: (body.host ?? "").trim(),
    port: body.port,
    username: emptyToUndefined(body.username) ?? null,
    from_address: (body.from_address ?? "").trim(),
    from_name: emptyToUndefined(body.from_name) ?? null,
    encryption: body.encryption,
  };
  if (mode === "create" || password) {
    data.password = password ?? "";
  }
  return data;
}

const SmtpAPI = {
  listSmtp(query?: SmtpPageQuery) {
    return request<ApiResponse<PageResult<SmtpTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  detailSmtp(id: number) {
    return request<ApiResponse<SmtpTable>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  createSmtp(body: SmtpForm) {
    return request<ApiResponse<SmtpTable>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: toSmtpPayload(body, "create"),
    });
  },

  updateSmtp(id: number, body: SmtpForm) {
    return request<ApiResponse<SmtpTable>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data: toSmtpPayload(body, "update"),
    });
  },

  testSmtp(toAddress: string) {
    return request<ApiResponse<{ to_address: string }>>({
      url: `${API_PATH}/test`,
      method: "post",
      data: { to_address: toAddress.trim() },
    });
  },
};

export default SmtpAPI;

export interface SmtpPageQuery extends PageQuery {
  host?: string;
  enabled?: boolean;
}

export interface SmtpTable extends BaseType {
  enabled?: boolean;
  host?: string;
  port?: number;
  username?: string;
  from_address?: string;
  from_name?: string;
  encryption?: "none" | "starttls" | "ssl";
}

export interface SmtpForm extends BaseFormType {
  enabled?: boolean;
  host?: string;
  port?: number;
  username?: string;
  password?: string;
  from_address?: string;
  from_name?: string;
  encryption?: "none" | "starttls" | "ssl";
}
