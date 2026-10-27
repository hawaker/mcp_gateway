import { request } from "@utils";

const API_PATH = "/mcp-gateway/mcp-group/datasource";

function emptyToUndefined(value: string | undefined): string | undefined {
  const text = (value ?? "").trim();
  return text ? text : undefined;
}

const GenbiGroupDatasourceAPI = {
  list(query?: GenbiGroupDatasourcePageQuery) {
    return request<ApiResponse<PageResult<GenbiGroupDatasourceTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  attach(groupId: number, body: GenbiGroupDatasourceAttachForm) {
    const externalName = emptyToUndefined(body.external_name);
    return request<ApiResponse<GenbiGroupDatasourceTable>>({
      url: `${API_PATH}/attach`,
      method: "post",
      params: { group_id: groupId },
      data: {
        datasource_id: body.datasource_id,
        enabled: body.enabled !== false,
        ...(externalName ? { external_name: externalName } : {}),
      },
    });
  },

  update(id: number, body: { external_name?: string; enabled?: boolean }) {
    return request<ApiResponse<GenbiGroupDatasourceTable>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data: body,
    });
  },

  getAcl(linkId: number) {
    return request<ApiResponse<GenbiGroupDatasourceAcl>>({
      url: `${API_PATH}/acl/${linkId}`,
      method: "get",
    });
  },

  saveAcl(linkId: number, data: GenbiGroupDatasourceAclSave) {
    return request<ApiResponse<GenbiGroupDatasourceAcl>>({
      url: `${API_PATH}/acl/${linkId}`,
      method: "put",
      data,
    });
  },
};

export default GenbiGroupDatasourceAPI;

export interface GenbiGroupDatasourcePageQuery extends PageQuery {
  group_id?: number;
  datasource_id?: number;
  enabled?: boolean;
  external_name?: string;
}

export interface GenbiGroupDatasourceTable extends BaseType {
  group_id?: number;
  datasource_id?: number;
  external_name?: string;
  enabled?: boolean;
}

export interface GenbiGroupDatasourceAttachForm {
  datasource_id?: number;
  external_name?: string;
  enabled?: boolean;
}

export type GenbiAclOperator =
  | "eq"
  | "ne"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "in"
  | "not_in"
  | "contains"
  | "not_contains";

export type GenbiAclColumnAction = "mask" | "deny";
export type GenbiAclMaskTemplate = "all_stars" | "keep_first_1" | "keep_first_3";

export interface GenbiAclRowPolicy {
  model_id: number;
  column_id: number;
  operator: GenbiAclOperator;
  values: string[];
  propagate?: boolean;
  propagate_to_model_ids?: number[];
}

export interface GenbiAclColumnPolicy {
  model_id: number;
  column_id: number;
  action: GenbiAclColumnAction;
  mask_template?: GenbiAclMaskTemplate | null;
}

export interface GenbiGroupDatasourceAclSave {
  row_policies: GenbiAclRowPolicy[];
  column_policies: GenbiAclColumnPolicy[];
}

export interface GenbiGroupDatasourceAcl extends GenbiGroupDatasourceAclSave {
  group_datasource_id: number;
  group_id: number;
  datasource_id: number;
}
