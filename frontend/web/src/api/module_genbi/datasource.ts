import { request } from "@utils";

const API_PATH = "/genbi/data-sources";

export const WREN_TYPE_OPTIONS = [
  { label: "PostgreSQL", value: "POSTGRES" },
  { label: "MySQL", value: "MYSQL" },
  { label: "Oracle", value: "ORACLE" },
  { label: "SQL Server", value: "MSSQL" },
  { label: "ClickHouse", value: "CLICK_HOUSE" },
  { label: "Trino", value: "TRINO" },
  { label: "Snowflake", value: "SNOWFLAKE" },
  { label: "Athena", value: "ATHENA" },
  { label: "Redshift", value: "REDSHIFT" },
  { label: "Databricks", value: "DATABRICKS" },
  { label: "BigQuery", value: "BIG_QUERY" },
  { label: "DuckDB", value: "DUCKDB" },
] as const;

function emptyToUndefined(value: string | undefined | null): string | undefined {
  const text = (value ?? "").trim();
  return text ? text : undefined;
}

function toPayload(body: GenbiDatasourceForm, mode: "create" | "update" | "test") {
  const data: Record<string, unknown> = {
    wren_type: (body.wren_type ?? "").trim(),
    host: emptyToUndefined(body.host) ?? null,
    port: body.port ?? null,
    username: emptyToUndefined(body.username) ?? null,
    database: emptyToUndefined(body.database) ?? null,
    db_schema: emptyToUndefined(body.db_schema) ?? null,
    url: emptyToUndefined(body.url) ?? null,
    config: body.config ?? {},
  };
  const password = emptyToUndefined(body.password);
  const apiKey = emptyToUndefined(body.api_key);
  const privateKey = emptyToUndefined(body.private_key);
  const token = emptyToUndefined(body.token);
  if (mode === "create" || mode === "test" || password) data.password = password ?? null;
  if (mode === "create" || mode === "test" || apiKey) data.api_key = apiKey ?? null;
  if (mode === "create" || mode === "test" || privateKey) data.private_key = privateKey ?? null;
  if (mode === "create" || mode === "test" || token) data.token = token ?? null;
  if (mode !== "test") {
    data.system_id = body.system_id;
    data.name = (body.name ?? "").trim();
    data.description = emptyToUndefined(body.description) ?? null;
    data.enabled = body.enabled !== false;
  }
  if (mode === "update") {
    delete data.system_id;
  }
  return data;
}

const GenbiDatasourceAPI = {
  listDatasource(query?: GenbiDatasourcePageQuery) {
    return request<ApiResponse<PageResult<GenbiDatasourceTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  detailDatasource(id: number) {
    return request<ApiResponse<GenbiDatasourceTable>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  createDatasource(body: GenbiDatasourceForm) {
    return request<ApiResponse<GenbiDatasourceTable>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: toPayload(body, "create"),
    });
  },

  updateDatasource(id: number, body: GenbiDatasourceForm) {
    return request<ApiResponse<GenbiDatasourceTable>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data: toPayload(body, "update"),
    });
  },

  deleteDatasource(ids: number[]) {
    return request<ApiResponse<null>>({
      url: `${API_PATH}/delete`,
      method: "delete",
      data: ids,
    });
  },

  testConfig(body: GenbiDatasourceForm) {
    return request<ApiResponse<null>>({
      url: `${API_PATH}/test`,
      method: "post",
      data: toPayload(body, "test"),
    });
  },

  testById(id: number) {
    return request<ApiResponse<null>>({
      url: `${API_PATH}/${id}/test`,
      method: "post",
    });
  },
};

export default GenbiDatasourceAPI;

export interface GenbiDatasourcePageQuery extends PageQuery {
  system_id?: number;
  name?: string;
  wren_type?: string;
  enabled?: boolean;
}

export interface GenbiDatasourceTable extends BaseType {
  system_id?: number;
  name?: string;
  wren_type?: string;
  host?: string;
  port?: number;
  username?: string;
  database?: string;
  db_schema?: string;
  url?: string;
  config?: Record<string, unknown>;
  description?: string;
  enabled?: boolean;
}

export interface GenbiDatasourceForm extends BaseFormType {
  system_id?: number;
  name?: string;
  wren_type?: string;
  host?: string;
  port?: number;
  username?: string;
  password?: string;
  database?: string;
  db_schema?: string;
  url?: string;
  api_key?: string;
  private_key?: string;
  token?: string;
  config?: Record<string, unknown>;
  description?: string;
  enabled?: boolean;
}
