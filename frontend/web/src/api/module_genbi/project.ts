import { request } from "@utils";

const API_PATH = "/genbi/projects";

const GenbiProjectAPI = {
  listProject(query?: GenbiProjectPageQuery) {
    return request<ApiResponse<PageResult<GenbiProjectTable>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  detailProject(id: number) {
    return request<ApiResponse<GenbiProjectTable>>({
      url: `${API_PATH}/detail/${id}`,
      method: "get",
    });
  },

  createProject(body: GenbiProjectForm) {
    return request<ApiResponse<GenbiProjectTable>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: {
        datasource_id: body.datasource_id,
        display_name: (body.display_name ?? "").trim(),
        system_id: body.system_id,
        onboarding_status: body.onboarding_status || "not_started",
        language: body.language || "zh-CN",
        agent_profile: body.agent_profile ?? {},
      },
    });
  },

  listModels(projectId: number) {
    return request<ApiResponse<GenbiModelTable[]>>({
      url: `${API_PATH}/${projectId}/models`,
      method: "get",
    });
  },

  syncModels(projectId: number, models: GenbiModelIn[]) {
    return request<ApiResponse<GenbiModelTable[]>>({
      url: `${API_PATH}/${projectId}/models`,
      method: "put",
      data: { models },
    });
  },

  deploy(projectId: number, force = false) {
    return request<ApiResponse<GenbiDeployOut>>({
      url: `${API_PATH}/${projectId}/deploy`,
      method: "post",
      params: { force },
    });
  },
};

export default GenbiProjectAPI;

export interface GenbiProjectPageQuery extends PageQuery {
  datasource_id?: number;
  system_id?: number;
  display_name?: string;
  onboarding_status?: string;
}

export interface GenbiProjectTable extends BaseType {
  datasource_id?: number;
  system_id?: number;
  display_name?: string;
  onboarding_status?: string;
  language?: string;
  agent_profile?: Record<string, unknown>;
}

export interface GenbiProjectForm extends BaseFormType {
  datasource_id?: number;
  display_name?: string;
  system_id?: number;
  onboarding_status?: string;
  language?: string;
  agent_profile?: Record<string, unknown>;
}

export interface GenbiModelColumnIn {
  display_name: string;
  source_column_name: string;
  column_type?: string;
  is_calculated?: boolean;
  expression?: string | null;
  properties?: Record<string, unknown> | null;
}

export interface GenbiModelIn {
  display_name: string;
  source_table_name: string;
  reference_name: string;
  ref_sql?: string | null;
  cached?: boolean;
  refresh_time?: string | null;
  properties?: Record<string, unknown> | null;
  columns?: GenbiModelColumnIn[];
}

export interface GenbiModelColumnTable extends BaseType {
  display_name?: string;
  source_column_name?: string;
  column_type?: string;
  is_calculated?: boolean;
  expression?: string | null;
  properties?: Record<string, unknown> | null;
}

export interface GenbiModelTable extends BaseType {
  project_id?: number;
  display_name?: string;
  source_table_name?: string;
  reference_name?: string;
  ref_sql?: string | null;
  cached?: boolean;
  refresh_time?: string | null;
  properties?: Record<string, unknown> | null;
  columns?: GenbiModelColumnTable[];
}

export interface GenbiDeployOut {
  project_id?: number;
  mdl_hash?: string | null;
  status?: string;
  stage?: string | null;
  error?: string | null;
  deployed_at?: string | null;
}
