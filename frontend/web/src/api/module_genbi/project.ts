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

  updateProject(id: number, body: GenbiProjectUpdateForm) {
    return request<ApiResponse<GenbiProjectTable>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data: body,
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

  listRelationships(projectId: number) {
    return request<ApiResponse<GenbiRelationshipTable[]>>({
      url: `${API_PATH}/${projectId}/relationships`,
      method: "get",
    });
  },

  syncRelationships(projectId: number, relationships: GenbiRelationshipIn[]) {
    return request<ApiResponse<GenbiRelationshipTable[]>>({
      url: `${API_PATH}/${projectId}/relationships`,
      method: "put",
      data: { relationships },
    });
  },

  getAgentProfile(projectId: number) {
    return request<ApiResponse<GenbiAgentProfile>>({
      url: `${API_PATH}/${projectId}/agent-profile`,
      method: "get",
    });
  },

  patchAgentProfile(projectId: number, body: GenbiAgentProfileUpdate) {
    return request<ApiResponse<GenbiAgentProfile>>({
      url: `${API_PATH}/${projectId}/agent-profile`,
      method: "patch",
      data: body,
    });
  },

  listInstructions(projectId: number) {
    return request<ApiResponse<GenbiInstructionTable[]>>({
      url: `${API_PATH}/${projectId}/instructions`,
      method: "get",
    });
  },

  createInstruction(projectId: number, body: GenbiInstructionForm) {
    return request<ApiResponse<GenbiInstructionTable>>({
      url: `${API_PATH}/${projectId}/instructions`,
      method: "post",
      data: body,
    });
  },

  updateInstruction(projectId: number, instructionId: number, body: Partial<GenbiInstructionForm>) {
    return request<ApiResponse<GenbiInstructionTable>>({
      url: `${API_PATH}/${projectId}/instructions/${instructionId}`,
      method: "patch",
      data: body,
    });
  },

  deleteInstruction(projectId: number, instructionId: number) {
    return request<ApiResponse<null>>({
      url: `${API_PATH}/${projectId}/instructions/${instructionId}`,
      method: "delete",
    });
  },

  listMetricDocs(projectId: number) {
    return request<ApiResponse<GenbiMetricDocTable[]>>({
      url: `${API_PATH}/${projectId}/metric-docs`,
      method: "get",
    });
  },

  createMetricDoc(projectId: number, body: GenbiMetricDocForm) {
    return request<ApiResponse<GenbiMetricDocTable>>({
      url: `${API_PATH}/${projectId}/metric-docs`,
      method: "post",
      data: body,
    });
  },

  updateMetricDoc(projectId: number, docId: number, body: Partial<GenbiMetricDocForm>) {
    return request<ApiResponse<GenbiMetricDocTable>>({
      url: `${API_PATH}/${projectId}/metric-docs/${docId}`,
      method: "patch",
      data: body,
    });
  },

  deleteMetricDoc(projectId: number, docId: number) {
    return request<ApiResponse<null>>({
      url: `${API_PATH}/${projectId}/metric-docs/${docId}`,
      method: "delete",
    });
  },

  listSqlPairs(projectId: number) {
    return request<ApiResponse<GenbiSqlPairTable[]>>({
      url: `${API_PATH}/${projectId}/sql-pairs`,
      method: "get",
    });
  },

  createSqlPair(projectId: number, body: GenbiSqlPairForm) {
    return request<ApiResponse<GenbiSqlPairTable>>({
      url: `${API_PATH}/${projectId}/sql-pairs`,
      method: "post",
      data: body,
    });
  },

  updateSqlPair(projectId: number, pairId: number, body: Partial<GenbiSqlPairForm>) {
    return request<ApiResponse<GenbiSqlPairTable>>({
      url: `${API_PATH}/${projectId}/sql-pairs/${pairId}`,
      method: "patch",
      data: body,
    });
  },

  deleteSqlPair(projectId: number, pairId: number) {
    return request<ApiResponse<null>>({
      url: `${API_PATH}/${projectId}/sql-pairs/${pairId}`,
      method: "delete",
    });
  },

  listDeployLogs(projectId: number, limit = 20) {
    return request<ApiResponse<GenbiDeployOut[]>>({
      url: `${API_PATH}/${projectId}/deploy-logs`,
      method: "get",
      params: { limit },
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

export interface GenbiProjectUpdateForm {
  display_name?: string;
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

export interface GenbiRelationshipIn {
  from_model_id: number;
  to_model_id: number;
  join_type?: string | null;
  condition?: string | null;
  properties?: Record<string, unknown> | null;
}

export interface GenbiRelationshipTable extends BaseType {
  project_id?: number;
  from_model_id?: number;
  to_model_id?: number;
  join_type?: string | null;
  condition?: string | null;
  properties?: Record<string, unknown> | null;
}

export interface GenbiAgentProfile {
  llm_model_id?: number | null;
  instructions: string[];
  tools_config: Array<string | { name: string }>;
  mcp_config: unknown[];
  skills_config: Record<string, unknown>;
  knowledge_config?: Record<string, unknown>;
  virtual_agent_id: string;
}

export interface GenbiAgentProfileUpdate {
  llm_model_id?: number | null;
  instructions?: string[];
  tools_config?: Array<string | { name: string }>;
  mcp_config?: unknown[];
  skills_config?: Record<string, unknown>;
  knowledge_config?: Record<string, unknown>;
  virtual_agent_id?: string;
}

export interface GenbiInstructionForm {
  instruction: string;
  questions?: string[];
  is_default?: boolean;
}

export interface GenbiInstructionTable extends BaseType {
  project_id?: number;
  instruction?: string;
  questions?: string[] | null;
  is_default?: boolean;
}

export interface GenbiMetricDocForm {
  name: string;
  content: string;
  enabled?: boolean;
}

export interface GenbiMetricDocTable extends BaseType {
  project_id?: number;
  name?: string;
  content?: string;
  enabled?: boolean;
}

export interface GenbiSqlPairForm {
  question: string;
  sql: string;
  enabled?: boolean;
}

export interface GenbiSqlPairTable extends BaseType {
  project_id?: number;
  question?: string;
  sql?: string;
  enabled?: boolean;
}

export interface GenbiDeployOut {
  project_id?: number;
  mdl_hash?: string | null;
  status?: string;
  stage?: string | null;
  error?: string | null;
  deployed_at?: string | null;
  smoke_report?: Record<string, unknown> | null;
}
