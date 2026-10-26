<!-- MCP 组：工具与成员只追加或停用。连接信息里的 token 不出现在列表中。 -->
<template>
  <div class="fa-full-height">
    <FaSearchBar
      v-show="showSearch"
      ref="searchBarRef"
      v-model="searchForm"
      :items="searchItems"
      :is-expand="false"
      :show-expand="false"
      :show-reset="true"
      :show-search="true"
      @search="handleSearch"
      @reset="onResetSearch"
    />

    <ElCard class="fa-table-card" :style="{ 'margin-top': showSearch ? '12px' : '0' }">
      <FaTableHeader
        v-model:columns="columnChecks"
        v-model:showSearchBar="showSearch"
        :loading="loading"
        @refresh="refreshData"
      >
        <template #left>
          <FaTableHeaderLeft
            :perm-create="['module_mcp_gateway:mcp-group:create']"
            :create-loading="createLoading"
            @add="handleAdd"
          />
        </template>
      </FaTableHeader>

      <FaTable
        :loading="loading"
        :data="data"
        :columns="columns"
        :pagination="pagination"
        @pagination:size-change="handleSizeChange"
        @pagination:current-change="handleCurrentChange"
      />
    </ElCard>

    <FaDialog
      v-model="dialogVisible.visible"
      :title="dialogVisible.title"
      width="560px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      :form-mode="dialogVisible.type"
      :confirm-loading="submitLoading"
      @cancel="handleCloseDialog"
      @close="handleCloseDialog"
      @confirm="handleSubmit()"
    >
      <FaForm
        :key="formRenderKey"
        ref="formRef"
        v-model="formData"
        :items="dialogFormItems"
        :rules="rules"
        label-suffix=":"
        :label-width="90"
        label-position="right"
        :span="24"
        :gutter="16"
        :show-reset="false"
        :show-submit="false"
        class="crud-dialog-art-form"
      />
    </FaDialog>

    <FaDialog
      v-model="toolDialogVisible"
      title="组内工具"
      width="920px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="detail"
      confirm-text="关闭"
      @close="toolDialogVisible = false"
    >
      <div class="mcp-group-panel">
        <div class="mcp-group-panel__bar">
          <span>{{ activeGroupLabel }}</span>
          <ElButton
            v-hasPerm="['module_mcp_gateway:mcp-group:create']"
            type="primary"
            plain
            @click="openAddTool"
          >
            添加工具
          </ElButton>
        </div>
        <FaTable
          :loading="toolLoading"
          :data="toolData"
          :columns="toolColumns"
          :pagination="toolPagination"
          @pagination:size-change="handleToolSizeChange"
          @pagination:current-change="handleToolCurrentChange"
        />
      </div>
    </FaDialog>

    <FaDialog
      v-model="toolFormVisible"
      title="添加工具"
      width="560px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="create"
      :confirm-loading="toolSubmitLoading"
      @cancel="toolFormVisible = false"
      @close="toolFormVisible = false"
      @confirm="submitTool"
    >
      <FaForm
        ref="toolFormRef"
        v-model="toolForm"
        :items="toolFormItems"
        :rules="toolRules"
        label-suffix=":"
        :label-width="110"
        label-position="right"
        :span="24"
        :gutter="16"
        :show-reset="false"
        :show-submit="false"
        class="crud-dialog-art-form"
      />
    </FaDialog>

    <FaDialog
      v-model="memberDialogVisible"
      title="组成员"
      width="820px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="detail"
      confirm-text="关闭"
      @close="memberDialogVisible = false"
    >
      <div class="mcp-group-panel">
        <div class="mcp-group-panel__bar">
          <span>{{ activeGroupLabel }}</span>
          <ElButton
            v-hasPerm="['module_mcp_gateway:mcp-group:create']"
            type="primary"
            plain
            @click="openAddMember"
          >
            添加成员
          </ElButton>
        </div>
        <FaTable
          :loading="memberLoading"
          :data="memberData"
          :columns="memberColumns"
          :pagination="memberPagination"
          @pagination:size-change="handleMemberSizeChange"
          @pagination:current-change="handleMemberCurrentChange"
        />
      </div>
    </FaDialog>

    <FaDialog
      v-model="memberFormVisible"
      title="添加成员"
      width="560px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="create"
      :confirm-loading="memberSubmitLoading"
      @cancel="memberFormVisible = false"
      @close="memberFormVisible = false"
      @confirm="submitMember"
    >
      <FaForm
        ref="memberFormRef"
        v-model="memberForm"
        :items="memberFormItems"
        :rules="memberRules"
        label-suffix=":"
        :label-width="110"
        label-position="right"
        :span="24"
        :gutter="16"
        :show-reset="false"
        :show-submit="false"
        class="crud-dialog-art-form"
      />
    </FaDialog>

    <FaDialog
      v-model="connectionDialogVisible"
      title="连接信息"
      width="760px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="detail"
      confirm-text="关闭"
      @close="connectionDialogVisible = false"
    >
      <div class="mcp-group-panel">
        <p class="mcp-group-panel__hint">列表只显示谁有凭证。点「查看」后生成可复制的 MCP 配置，明文只出现在下方 JSON 的 headers 里。</p>
        <FaTable
          :loading="credentialLoading"
          :data="credentialData"
          :columns="credentialColumns"
          :pagination="credentialPagination"
          @pagination:size-change="handleCredentialSizeChange"
          @pagination:current-change="handleCredentialCurrentChange"
        />
        <div v-if="connectionInfo" class="mcp-connection-snippet">
          <ElTabs v-model="connectionTab" class="mcp-connection-snippet__tabs">
            <ElTabPane label="streamable-http" name="streamable-http" />
            <ElTabPane label="sse" name="sse" />
          </ElTabs>
          <div class="mcp-connection-snippet__bar">
            <span>MCP 客户端配置</span>
            <FaCopyButton :text="connectionSnippet" />
          </div>
          <pre class="mcp-connection-snippet__code">{{ connectionSnippet }}</pre>
        </div>
      </div>
    </FaDialog>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import McpGroupAPI, {
  type McpConnectionInfo,
  type McpCredentialTable,
  type McpGroupForm,
  type McpGroupMemberForm,
  type McpGroupMemberTable,
  type McpGroupPageQuery,
  type McpGroupTable,
  type McpGroupToolForm,
  type McpGroupToolTable,
} from "@/api/module_mcp_gateway/mcp_group";
import RestToolAPI, { type RestToolTable } from "@/api/module_mcp_gateway/rest_tool";
import UpstreamAPI, { type UpstreamToolTable } from "@/api/module_mcp_gateway/upstream";
import BizUserAPI, { type BizUserGroupTable, type BizUserTable } from "@/api/module_mcp_gateway/user";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaCopyButton from "@/components/actions/fa-copy-button/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { renderTableOperationCell, type TableOperationAction } from "@utils";

defineOptions({
  name: "McpGatewayMcpGroup",
  inheritAttrs: false,
});

const ENABLED_OPTIONS = [
  { label: "启用", value: true },
  { label: "停用", value: false },
] as const;

const SOURCE_OPTIONS = [
  { label: "REST 工具", value: "rest" },
  { label: "MCP 代理工具", value: "upstream" },
] as const;

const PRINCIPAL_OPTIONS = [
  { label: "业务用户", value: "user" },
  { label: "业务用户组", value: "group" },
] as const;

function enabledText(enabled?: boolean) {
  return enabled === false ? "停用" : "启用";
}

const showSearch = ref(true);
const searchForm = ref<McpGroupPageQuery>({ name: undefined, enabled: undefined });
const searchBarRef = ref();
const searchItems = computed<SearchFormItem[]>(() => [
  { label: "名称", key: "name", type: "input", placeholder: "请输入名称", clearable: true, span: 6 },
  {
    label: "启用",
    key: "enabled",
    type: "select",
    props: { placeholder: "请选择", options: ENABLED_OPTIONS, clearable: true },
    span: 6,
  },
]);

const createLoading = ref(false);
const activeGroup = ref<McpGroupTable>();
const activeGroupLabel = computed(() => activeGroup.value?.name || "");

function rowActions(row: McpGroupTable): TableOperationAction[] {
  return [
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_mcp_gateway:mcp-group:update",
      run: () => void openEdit(row),
    },
    {
      key: "tools",
      label: "工具",
      artType: "view",
      icon: "ri:tools-line",
      iconColor: "var(--el-color-primary)",
      perm: "module_mcp_gateway:mcp-group:query",
      run: () => void openTools(row),
    },
    {
      key: "members",
      label: "成员",
      artType: "view",
      icon: "ri:group-line",
      iconColor: "var(--el-color-warning)",
      perm: "module_mcp_gateway:mcp-group:query",
      run: () => void openMembers(row),
    },
    {
      key: "connection",
      label: "连接",
      artType: "view",
      icon: "ri:link",
      iconColor: "var(--el-color-info)",
      perm: "module_mcp_gateway:mcp-group:query",
      run: () => void openConnection(row),
    },
  ];
}

const {
  columns,
  columnChecks,
  data,
  loading,
  pagination,
  replaceSearchParams,
  resetSearchParams,
  getData,
  handleSizeChange,
  handleCurrentChange,
  refreshData,
  refreshCreate,
  refreshUpdate,
} = useTable({
  core: {
    apiFn: McpGroupAPI.listGroup,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "name", label: "名称", minWidth: 180, showOverflowTooltip: true },
      {
        prop: "enabled",
        label: "启用",
        width: 88,
        formatter: (row: McpGroupTable) => enabledText(row.enabled),
      },
      { prop: "created_time", label: "创建时间", width: 168, showOverflowTooltip: true },
      {
        prop: "operation",
        label: "操作",
        width: 240,
        fixed: "right",
        align: "center",
        formatter: (row: McpGroupTable) =>
          renderTableOperationCell(rowActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

function createInitialForm(): McpGroupForm {
  return { id: undefined, name: "", enabled: true };
}

const formData = ref<McpGroupForm>(createInitialForm());
const initialFormData = createInitialForm();
const { dialogVisible } = useCrudDialog();
const formRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);
const rules = reactive({
  name: [{ required: true, message: "请输入名称", trigger: "blur" }],
});
const dialogFormItems = computed<FormItem[]>(() => [
  { label: "名称", key: "name", type: "input", span: 24, props: { placeholder: "请输入名称", maxlength: 128 } },
  { label: "启用", key: "enabled", type: "switch", span: 24 },
]);

async function detailForForm(id: number) {
  const response = await McpGroupAPI.detailGroup(id);
  const row = response.data.data;
  const detail: McpGroupForm | undefined = row
    ? { id: row.id, name: row.name ?? "", enabled: row.enabled !== false }
    : undefined;
  return { data: { data: detail } };
}

const { submitLoading, handleCloseDialog, handleOpenDialog, handleSubmit } = useCrudForm<McpGroupForm>({
  formData,
  initialFormData,
  dialogVisible,
  dataFormRef: formRef,
  formRenderKey,
  detailApi: detailForForm,
  createApi: McpGroupAPI.createGroup,
  updateApi: McpGroupAPI.updateGroup,
  titles: { create: "新增 MCP 组", update: "修改 MCP 组" },
  onCreateSuccess: async () => {
    await refreshCreate();
  },
  onUpdateSuccess: async () => {
    await refreshUpdate();
  },
});

async function handleAdd() {
  createLoading.value = true;
  try {
    await handleOpenDialog("create");
  } finally {
    createLoading.value = false;
  }
}

async function openEdit(row: McpGroupTable) {
  if (!row.id) return;
  await handleOpenDialog("update", row.id);
}

async function handleSearch(params: McpGroupPageQuery) {
  replaceSearchParams({ name: params.name, enabled: params.enabled });
  await getData();
}

async function onResetSearch() {
  searchForm.value = { name: undefined, enabled: undefined };
  await resetSearchParams();
}

const restTools = ref<RestToolTable[]>([]);
const upstreamTools = ref<UpstreamToolTable[]>([]);
const bizUsers = ref<BizUserTable[]>([]);
const bizGroups = ref<BizUserGroupTable[]>([]);

async function loadCatalogs() {
  const [restResponse, upstreamResponse, userResponse, groupResponse] = await Promise.all([
    RestToolAPI.listTool({ page_no: 1, page_size: 100 }),
    UpstreamAPI.listTool({ page_no: 1, page_size: 100, selected: true }),
    BizUserAPI.listUser({ page_no: 1, page_size: 100 }),
    BizUserAPI.listGroup({ page_no: 1, page_size: 100 }),
  ]);
  restTools.value = restResponse.data.data?.items ?? [];
  upstreamTools.value = upstreamResponse.data.data?.items ?? [];
  bizUsers.value = userResponse.data.data?.items ?? [];
  bizGroups.value = groupResponse.data.data?.items ?? [];
}

function userLabel(userId?: number) {
  const user = bizUsers.value.find((item) => item.id === userId);
  return user?.name || (userId ? String(userId) : "");
}

function groupLabel(groupId?: number) {
  const group = bizGroups.value.find((item) => item.id === groupId);
  return group?.name || (groupId ? String(groupId) : "");
}

const toolDialogVisible = ref(false);
const toolFormVisible = ref(false);
const toolSubmitLoading = ref(false);
const toolFormRef = ref<InstanceType<typeof FaForm> | null>(null);
const toolForm = ref<McpGroupToolForm>({ source: "rest", source_id: undefined, external_name: "", enabled: true });

function toolActions(row: McpGroupToolTable): TableOperationAction[] {
  return [
    {
      key: row.enabled === false ? "enable" : "disable",
      label: row.enabled === false ? "启用" : "停用",
      artType: "edit",
      perm: "module_mcp_gateway:mcp-group:update",
      run: () => void toggleTool(row),
    },
  ];
}

const {
  columns: toolColumns,
  data: toolData,
  loading: toolLoading,
  pagination: toolPagination,
  replaceSearchParams: replaceToolSearch,
  getData: getToolData,
  handleSizeChange: handleToolSizeChange,
  handleCurrentChange: handleToolCurrentChange,
} = useTable({
  core: {
    apiFn: McpGroupAPI.listTool,
    apiParams: { page_no: 1, page_size: 10, group_id: undefined },
    immediate: false,
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      {
        prop: "source",
        label: "来源",
        width: 100,
        formatter: (row: McpGroupToolTable) => (row.source === "upstream" ? "MCP 代理工具" : "REST 工具"),
      },
      { prop: "external_name", label: "外部名称", minWidth: 180, showOverflowTooltip: true },
      {
        prop: "enabled",
        label: "启用",
        width: 88,
        formatter: (row: McpGroupToolTable) => enabledText(row.enabled),
      },
      {
        prop: "operation",
        label: "操作",
        width: 90,
        fixed: "right",
        align: "center",
        formatter: (row: McpGroupToolTable) =>
          renderTableOperationCell(toolActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

const toolSourceOptions = computed(() => {
  if (toolForm.value.source === "upstream") {
    return upstreamTools.value
      .filter((item) => item.id)
      .map((item) => ({ label: item.external_name || item.remote_name || String(item.id), value: item.id }));
  }
  return restTools.value
    .filter((item) => item.id)
    .map((item) => ({ label: item.display_name || item.name || String(item.id), value: item.id }));
});

const toolFormItems = computed<FormItem[]>(() => [
  {
    label: "来源",
    key: "source",
    type: "select",
    span: 24,
    props: { placeholder: "请选择来源", options: SOURCE_OPTIONS },
  },
  {
    label: "工具",
    key: "source_id",
    type: "select",
    span: 24,
    props: { placeholder: "请选择工具", options: toolSourceOptions.value, filterable: true },
  },
  {
    label: "外部名称",
    key: "external_name",
    type: "input",
    span: 24,
    props: { placeholder: "留空则使用工具自身的名称", maxlength: 512 },
  },
  { label: "启用", key: "enabled", type: "switch", span: 24 },
]);

const toolRules = reactive({
  source: [{ required: true, message: "请选择来源", trigger: "change" }],
  source_id: [{ required: true, message: "请选择工具", trigger: "change" }],
});

async function openTools(row: McpGroupTable) {
  if (!row.id) return;
  activeGroup.value = row;
  toolDialogVisible.value = true;
  replaceToolSearch({ group_id: row.id });
  await getToolData();
}

async function openAddTool() {
  await loadCatalogs();
  toolForm.value = { source: "rest", source_id: undefined, external_name: "", enabled: true };
  toolFormVisible.value = true;
}

async function submitTool() {
  const groupId = activeGroup.value?.id;
  if (!groupId) return;
  const valid = await toolFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  toolSubmitLoading.value = true;
  try {
    await McpGroupAPI.createTool(groupId, toolForm.value);
    toolFormVisible.value = false;
    ElMessage.success("已添加工具");
    await getToolData();
  } finally {
    toolSubmitLoading.value = false;
  }
}

async function toggleTool(row: McpGroupToolTable) {
  if (!row.id) return;
  await McpGroupAPI.updateTool(row.id, { enabled: row.enabled === false });
  await getToolData();
}

const memberDialogVisible = ref(false);
const memberFormVisible = ref(false);
const memberSubmitLoading = ref(false);
const memberFormRef = ref<InstanceType<typeof FaForm> | null>(null);
const memberForm = ref<McpGroupMemberForm>({ principal_type: "user", principal_id: undefined, enabled: true });

function memberActions(row: McpGroupMemberTable): TableOperationAction[] {
  return [
    {
      key: row.enabled === false ? "enable" : "disable",
      label: row.enabled === false ? "启用" : "停用",
      artType: "edit",
      perm: "module_mcp_gateway:mcp-group:update",
      run: () => void toggleMember(row),
    },
  ];
}

const {
  columns: memberColumns,
  data: memberData,
  loading: memberLoading,
  pagination: memberPagination,
  replaceSearchParams: replaceMemberSearch,
  getData: getMemberData,
  handleSizeChange: handleMemberSizeChange,
  handleCurrentChange: handleMemberCurrentChange,
} = useTable({
  core: {
    apiFn: McpGroupAPI.listMember,
    apiParams: { page_no: 1, page_size: 10, group_id: undefined },
    immediate: false,
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      {
        prop: "principal_type",
        label: "类型",
        width: 120,
        formatter: (row: McpGroupMemberTable) => (row.principal_type === "group" ? "业务用户组" : "业务用户"),
      },
      {
        prop: "principal_id",
        label: "成员",
        minWidth: 180,
        showOverflowTooltip: true,
        formatter: (row: McpGroupMemberTable) =>
          row.principal_type === "group" ? groupLabel(row.principal_id) : userLabel(row.principal_id),
      },
      {
        prop: "enabled",
        label: "启用",
        width: 88,
        formatter: (row: McpGroupMemberTable) => enabledText(row.enabled),
      },
      {
        prop: "operation",
        label: "操作",
        width: 90,
        fixed: "right",
        align: "center",
        formatter: (row: McpGroupMemberTable) =>
          renderTableOperationCell(memberActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

const principalOptions = computed(() => {
  if (memberForm.value.principal_type === "group") {
    return bizGroups.value.filter((item) => item.id).map((item) => ({ label: item.name || String(item.id), value: item.id }));
  }
  return bizUsers.value.filter((item) => item.id).map((item) => ({ label: item.name || String(item.id), value: item.id }));
});

const memberFormItems = computed<FormItem[]>(() => [
  {
    label: "类型",
    key: "principal_type",
    type: "select",
    span: 24,
    props: { placeholder: "请选择类型", options: PRINCIPAL_OPTIONS },
  },
  {
    label: "成员",
    key: "principal_id",
    type: "select",
    span: 24,
    props: { placeholder: "请选择成员", options: principalOptions.value, filterable: true },
  },
  { label: "启用", key: "enabled", type: "switch", span: 24 },
]);

const memberRules = reactive({
  principal_type: [{ required: true, message: "请选择类型", trigger: "change" }],
  principal_id: [{ required: true, message: "请选择成员", trigger: "change" }],
});

async function openMembers(row: McpGroupTable) {
  if (!row.id) return;
  activeGroup.value = row;
  memberDialogVisible.value = true;
  await loadCatalogs();
  replaceMemberSearch({ group_id: row.id });
  await getMemberData();
}

async function openAddMember() {
  await loadCatalogs();
  memberForm.value = { principal_type: "user", principal_id: undefined, enabled: true };
  memberFormVisible.value = true;
}

async function submitMember() {
  const groupId = activeGroup.value?.id;
  if (!groupId) return;
  const valid = await memberFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  memberSubmitLoading.value = true;
  try {
    await McpGroupAPI.createMember(groupId, memberForm.value);
    memberFormVisible.value = false;
    ElMessage.success("已添加成员");
    await getMemberData();
  } finally {
    memberSubmitLoading.value = false;
  }
}

async function toggleMember(row: McpGroupMemberTable) {
  if (!row.id) return;
  await McpGroupAPI.updateMember(row.id, row.enabled === false);
  await getMemberData();
}

const connectionDialogVisible = ref(false);
const connectionInfo = ref<McpConnectionInfo | null>(null);
const connectionTab = ref<"streamable-http" | "sse">("streamable-http");

function mcpAbsoluteUrl(path: string): string {
  const base = String(import.meta.env.VITE_API_BASE_URL || window.location.origin).replace(/\/$/, "");
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

function bearerAuthorization(authorization: string): string {
  return authorization.replace(/^Authorization:\s*/i, "").trim();
}

function showConnection(info: McpConnectionInfo) {
  connectionInfo.value = info;
  connectionTab.value = "streamable-http";
}

const connectionSnippet = computed(() => {
  const info = connectionInfo.value;
  if (!info) return "";
  const headers = {
    Authorization: bearerAuthorization(info.authorization),
  };
  if (connectionTab.value === "sse") {
    return JSON.stringify(
      {
        type: "sse",
        url: mcpAbsoluteUrl(info.sse_url),
        headers,
      },
      null,
      2,
    );
  }
  return JSON.stringify(
    {
      type: "streamable-http",
      url: mcpAbsoluteUrl(info.streamable_http_url),
      headers,
    },
    null,
    2,
  );
});

function credentialActions(row: McpCredentialTable): TableOperationAction[] {
  return [
    {
      key: "view",
      label: "查看",
      artType: "view",
      perm: "module_mcp_gateway:mcp-group:query",
      run: () => void revealConnection(row),
    },
    {
      key: "reissue",
      label: "重新签发",
      artType: "edit",
      perm: "module_mcp_gateway:mcp-group:update",
      run: () => void renewConnection(row),
    },
  ];
}

const {
  columns: credentialColumns,
  data: credentialData,
  loading: credentialLoading,
  pagination: credentialPagination,
  replaceSearchParams: replaceCredentialSearch,
  getData: getCredentialData,
  handleSizeChange: handleCredentialSizeChange,
  handleCurrentChange: handleCredentialCurrentChange,
} = useTable({
  core: {
    apiFn: McpGroupAPI.listCredential,
    apiParams: { page_no: 1, page_size: 10, group_id: undefined },
    immediate: false,
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      {
        prop: "user_id",
        label: "业务用户",
        minWidth: 160,
        formatter: (row: McpCredentialTable) => userLabel(row.user_id),
      },
      {
        prop: "operation",
        label: "操作",
        width: 160,
        fixed: "right",
        align: "center",
        formatter: (row: McpCredentialTable) =>
          renderTableOperationCell(credentialActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

async function openConnection(row: McpGroupTable) {
  if (!row.id) return;
  activeGroup.value = row;
  connectionInfo.value = null;
  connectionDialogVisible.value = true;
  await loadCatalogs();
  replaceCredentialSearch({ group_id: row.id });
  await getCredentialData();
}

async function revealConnection(row: McpCredentialTable) {
  if (!row.user_id || !row.group_id) return;
  const response = await McpGroupAPI.connectionInfo(row.user_id, row.group_id);
  if (response.data.data) showConnection(response.data.data);
}

async function renewConnection(row: McpCredentialTable) {
  if (!row.user_id || !row.group_id) return;
  const response = await McpGroupAPI.reissue(row.user_id, row.group_id);
  if (response.data.data) {
    showConnection(response.data.data);
    ElMessage.success("已重新签发");
  }
  await getCredentialData();
}
</script>

<style scoped>
.mcp-group-panel {
  padding: 0 16px 16px;
}

.mcp-group-panel__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.mcp-group-panel__hint {
  margin: 0 0 12px;
  color: var(--el-text-color-secondary);
}

.mcp-connection-snippet {
  margin-top: 16px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 8px;
}

.mcp-connection-snippet__tabs {
  padding: 0 12px;
  background: var(--el-fill-color-light, #f5f7fa);
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}

.mcp-connection-snippet__tabs :deep(.el-tabs__header) {
  margin: 0;
}

.mcp-connection-snippet__tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.mcp-connection-snippet__tabs :deep(.el-tabs__item) {
  height: 40px;
  font-size: 13px;
}

.mcp-connection-snippet__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 500;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}

.mcp-connection-snippet__code {
  margin: 0;
  padding: 12px;
  overflow: auto;
  color: var(--el-text-color-primary);
  font-size: 12px;
  line-height: 1.55;
  white-space: pre;
  word-break: break-all;
}
</style>
