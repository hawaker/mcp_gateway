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
      v-model="datasourceDialogVisible"
      title="组内数据源"
      width="920px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="detail"
      confirm-text="关闭"
      @close="datasourceDialogVisible = false"
    >
      <div class="mcp-group-panel">
        <div class="mcp-group-panel__bar">
          <span>{{ activeGroupLabel }}</span>
          <ElButton
            v-hasPerm="['module_mcp_gateway:mcp-group:create']"
            type="primary"
            plain
            @click="openAttachDatasource"
          >
            关联数据源
          </ElButton>
        </div>
        <p class="mcp-group-panel__hint">组内调用者共用每源 ACL（行列规则）。停用后 ask_bi 不再暴露该源。</p>
        <FaTable
          :loading="dsLoading"
          :data="dsData"
          :columns="dsColumns"
          :pagination="dsPagination"
          @pagination:size-change="handleDsSizeChange"
          @pagination:current-change="handleDsCurrentChange"
        />
      </div>
    </FaDialog>

    <FaDialog
      v-model="dsFormVisible"
      title="关联数据源"
      width="560px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="create"
      :confirm-loading="dsSubmitLoading"
      @cancel="dsFormVisible = false"
      @close="dsFormVisible = false"
      @confirm="submitAttachDatasource"
    >
      <FaForm
        ref="dsFormRef"
        v-model="dsForm"
        :items="dsFormItems"
        :rules="dsRules"
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
      v-model="aclDialogVisible"
      title="编辑 ACL"
      width="900px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="create"
      :confirm-loading="aclSaving"
      confirm-text="保存 ACL"
      @cancel="aclDialogVisible = false"
      @close="aclDialogVisible = false"
      @confirm="saveAcl"
    >
      <div class="mcp-group-panel genbi-acl-panel">
        <p class="mcp-group-panel__hint">
          组 × 源共享规则。行规则过滤；列规则 mask/deny。model_id / column_id 来自该数据源项目的 MDL。
        </p>
        <div class="genbi-acl-section">
          <div class="mcp-group-panel__bar">
            <strong>行规则</strong>
            <ElButton type="primary" plain size="small" @click="addRowPolicy">添加</ElButton>
          </div>
          <div v-for="(row, index) in aclRowPolicies" :key="`row-${index}`" class="genbi-acl-row">
            <ElSelect v-model="row.model_id" placeholder="模型" filterable style="width: 160px" @change="() => onAclModelChange(row)">
              <ElOption v-for="m in aclModels" :key="m.id" :label="m.display_name || m.reference_name" :value="m.id!" />
            </ElSelect>
            <ElSelect v-model="row.column_id" placeholder="列" filterable style="width: 140px">
              <ElOption
                v-for="c in columnsForModel(row.model_id)"
                :key="c.id"
                :label="c.display_name || c.source_column_name"
                :value="c.id!"
              />
            </ElSelect>
            <ElSelect v-model="row.operator" placeholder="运算符" style="width: 120px">
              <ElOption v-for="op in ACL_OPERATORS" :key="op" :label="op" :value="op" />
            </ElSelect>
            <ElInput v-model="row.valuesText" placeholder="值，逗号分隔" style="flex: 1" />
            <ElButton type="danger" link @click="aclRowPolicies.splice(index, 1)">删除</ElButton>
          </div>
        </div>
        <div class="genbi-acl-section">
          <div class="mcp-group-panel__bar">
            <strong>列规则</strong>
            <ElButton type="primary" plain size="small" @click="addColumnPolicy">添加</ElButton>
          </div>
          <div v-for="(col, index) in aclColumnPolicies" :key="`col-${index}`" class="genbi-acl-row">
            <ElSelect v-model="col.model_id" placeholder="模型" filterable style="width: 160px" @change="() => onAclModelChange(col)">
              <ElOption v-for="m in aclModels" :key="m.id" :label="m.display_name || m.reference_name" :value="m.id!" />
            </ElSelect>
            <ElSelect v-model="col.column_id" placeholder="列" filterable style="width: 140px">
              <ElOption
                v-for="c in columnsForModel(col.model_id)"
                :key="c.id"
                :label="c.display_name || c.source_column_name"
                :value="c.id!"
              />
            </ElSelect>
            <ElSelect v-model="col.action" placeholder="动作" style="width: 110px">
              <ElOption label="mask" value="mask" />
              <ElOption label="deny" value="deny" />
            </ElSelect>
            <ElSelect
              v-model="col.mask_template"
              placeholder="掩码模板"
              clearable
              :disabled="col.action !== 'mask'"
              style="width: 140px"
            >
              <ElOption label="all_stars" value="all_stars" />
              <ElOption label="keep_first_1" value="keep_first_1" />
              <ElOption label="keep_first_3" value="keep_first_3" />
            </ElSelect>
            <ElButton type="danger" link @click="aclColumnPolicies.splice(index, 1)">删除</ElButton>
          </div>
        </div>
      </div>
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
import GenbiDatasourceAPI, { type GenbiDatasourceTable } from "@/api/module_genbi/datasource";
import GenbiGroupDatasourceAPI, {
  type GenbiAclColumnAction,
  type GenbiAclMaskTemplate,
  type GenbiAclOperator,
  type GenbiGroupDatasourceAttachForm,
  type GenbiGroupDatasourceTable,
} from "@/api/module_genbi/group_datasource";
import GenbiProjectAPI, { type GenbiModelTable } from "@/api/module_genbi/project";
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
      key: "datasources",
      label: "数据源",
      artType: "view",
      icon: "ri:database-2-line",
      iconColor: "var(--el-color-success)",
      perm: "module_mcp_gateway:mcp-group:query",
      run: () => void openDatasources(row),
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
        width: 300,
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

const ACL_OPERATORS: GenbiAclOperator[] = [
  "eq",
  "ne",
  "gt",
  "gte",
  "lt",
  "lte",
  "in",
  "not_in",
  "contains",
  "not_contains",
];

interface AclRowDraft {
  model_id?: number;
  column_id?: number;
  operator: GenbiAclOperator;
  valuesText: string;
}

interface AclColumnDraft {
  model_id?: number;
  column_id?: number;
  action: GenbiAclColumnAction;
  mask_template?: GenbiAclMaskTemplate | null;
}

const genbiDatasources = ref<GenbiDatasourceTable[]>([]);
const genbiDatasourceOptions = computed(() =>
  genbiDatasources.value
    .filter((item) => item.id)
    .map((item) => ({ label: `${item.name} (#${item.id})`, value: item.id })),
);

async function loadGenbiDatasources() {
  const response = await GenbiDatasourceAPI.listDatasource({ page_no: 1, page_size: 200, enabled: true });
  genbiDatasources.value = response.data.data?.items ?? [];
}

function genbiDatasourceLabel(id?: number) {
  const row = genbiDatasources.value.find((item) => item.id === id);
  return row?.name || (id ? String(id) : "");
}

const datasourceDialogVisible = ref(false);
const dsFormVisible = ref(false);
const dsSubmitLoading = ref(false);
const dsFormRef = ref<InstanceType<typeof FaForm> | null>(null);
const dsForm = ref<GenbiGroupDatasourceAttachForm>({
  datasource_id: undefined,
  external_name: "",
  enabled: true,
});

function dsActions(row: GenbiGroupDatasourceTable): TableOperationAction[] {
  return [
    {
      key: "acl",
      label: "ACL",
      artType: "edit",
      perm: "module_mcp_gateway:mcp-group:update",
      run: () => void openAcl(row),
    },
    {
      key: row.enabled === false ? "enable" : "disable",
      label: row.enabled === false ? "启用" : "停用",
      artType: "edit",
      perm: "module_mcp_gateway:mcp-group:update",
      run: () => void toggleDatasource(row),
    },
  ];
}

const {
  columns: dsColumns,
  data: dsData,
  loading: dsLoading,
  pagination: dsPagination,
  replaceSearchParams: replaceDsSearch,
  getData: getDsData,
  handleSizeChange: handleDsSizeChange,
  handleCurrentChange: handleDsCurrentChange,
} = useTable({
  core: {
    apiFn: GenbiGroupDatasourceAPI.list,
    apiParams: { page_no: 1, page_size: 10, group_id: undefined },
    immediate: false,
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      {
        prop: "datasource_id",
        label: "数据源",
        minWidth: 160,
        showOverflowTooltip: true,
        formatter: (row: GenbiGroupDatasourceTable) => genbiDatasourceLabel(row.datasource_id),
      },
      { prop: "external_name", label: "外部名称", minWidth: 180, showOverflowTooltip: true },
      {
        prop: "enabled",
        label: "启用",
        width: 88,
        formatter: (row: GenbiGroupDatasourceTable) => enabledText(row.enabled),
      },
      {
        prop: "operation",
        label: "操作",
        width: 140,
        fixed: "right",
        align: "center",
        formatter: (row: GenbiGroupDatasourceTable) =>
          renderTableOperationCell(dsActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

const dsFormItems = computed<FormItem[]>(() => [
  {
    label: "数据源",
    key: "datasource_id",
    type: "select",
    span: 24,
    props: { placeholder: "请选择数据源", options: genbiDatasourceOptions.value, filterable: true },
  },
  {
    label: "外部名称",
    key: "external_name",
    type: "input",
    span: 24,
    props: { placeholder: "留空则用 {system.code}_ask_bi", maxlength: 512 },
  },
  { label: "启用", key: "enabled", type: "switch", span: 24 },
]);

const dsRules = reactive({
  datasource_id: [{ required: true, message: "请选择数据源", trigger: "change" }],
});

async function openDatasources(row: McpGroupTable) {
  if (!row.id) return;
  activeGroup.value = row;
  datasourceDialogVisible.value = true;
  await loadGenbiDatasources();
  replaceDsSearch({ group_id: row.id });
  await getDsData();
}

async function openAttachDatasource() {
  await loadGenbiDatasources();
  dsForm.value = { datasource_id: undefined, external_name: "", enabled: true };
  dsFormVisible.value = true;
}

async function submitAttachDatasource() {
  const groupId = activeGroup.value?.id;
  if (!groupId) return;
  const valid = await dsFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  dsSubmitLoading.value = true;
  try {
    await GenbiGroupDatasourceAPI.attach(groupId, dsForm.value);
    dsFormVisible.value = false;
    ElMessage.success("已关联数据源");
    await getDsData();
  } finally {
    dsSubmitLoading.value = false;
  }
}

async function toggleDatasource(row: GenbiGroupDatasourceTable) {
  if (!row.id) return;
  await GenbiGroupDatasourceAPI.update(row.id, { enabled: row.enabled === false });
  await getDsData();
}

const aclDialogVisible = ref(false);
const aclSaving = ref(false);
const aclLink = ref<GenbiGroupDatasourceTable>();
const aclModels = ref<GenbiModelTable[]>([]);
const aclRowPolicies = ref<AclRowDraft[]>([]);
const aclColumnPolicies = ref<AclColumnDraft[]>([]);

function columnsForModel(modelId?: number) {
  const model = aclModels.value.find((item) => item.id === modelId);
  return model?.columns ?? [];
}

function onAclModelChange(draft: { model_id?: number; column_id?: number }) {
  draft.column_id = undefined;
}

function addRowPolicy() {
  aclRowPolicies.value.push({
    model_id: undefined,
    column_id: undefined,
    operator: "eq",
    valuesText: "",
  });
}

function addColumnPolicy() {
  aclColumnPolicies.value.push({
    model_id: undefined,
    column_id: undefined,
    action: "mask",
    mask_template: "all_stars",
  });
}

async function loadAclModels(datasourceId?: number) {
  aclModels.value = [];
  if (!datasourceId) return;
  const projectResponse = await GenbiProjectAPI.listProject({
    page_no: 1,
    page_size: 1,
    datasource_id: datasourceId,
  });
  const project = projectResponse.data.data?.items?.[0];
  if (!project?.id) return;
  const modelsResponse = await GenbiProjectAPI.listModels(project.id);
  aclModels.value = modelsResponse.data.data ?? [];
}

async function openAcl(row: GenbiGroupDatasourceTable) {
  if (!row.id) return;
  aclLink.value = row;
  await loadGenbiDatasources();
  await loadAclModels(row.datasource_id);
  const response = await GenbiGroupDatasourceAPI.getAcl(row.id);
  const acl = response.data.data;
  aclRowPolicies.value = (acl?.row_policies ?? []).map((item) => ({
    model_id: item.model_id,
    column_id: item.column_id,
    operator: item.operator,
    valuesText: (item.values ?? []).join(","),
  }));
  aclColumnPolicies.value = (acl?.column_policies ?? []).map((item) => ({
    model_id: item.model_id,
    column_id: item.column_id,
    action: item.action,
    mask_template: item.mask_template ?? null,
  }));
  aclDialogVisible.value = true;
}

async function saveAcl() {
  const linkId = aclLink.value?.id;
  if (!linkId) return;
  for (const row of aclRowPolicies.value) {
    if (!row.model_id || !row.column_id) {
      ElMessage.error("行规则须选择模型与列");
      return;
    }
  }
  for (const col of aclColumnPolicies.value) {
    if (!col.model_id || !col.column_id) {
      ElMessage.error("列规则须选择模型与列");
      return;
    }
    if (col.action === "mask" && !col.mask_template) {
      ElMessage.error("mask 规则须选择掩码模板");
      return;
    }
  }
  aclSaving.value = true;
  try {
    await GenbiGroupDatasourceAPI.saveAcl(linkId, {
      row_policies: aclRowPolicies.value.map((row) => ({
        model_id: row.model_id!,
        column_id: row.column_id!,
        operator: row.operator,
        values: row.valuesText
          .split(/[,，]/)
          .map((part) => part.trim())
          .filter(Boolean),
        propagate: false,
        propagate_to_model_ids: [],
      })),
      column_policies: aclColumnPolicies.value.map((col) => ({
        model_id: col.model_id!,
        column_id: col.column_id!,
        action: col.action,
        mask_template: col.action === "mask" ? col.mask_template ?? null : null,
      })),
    });
    aclDialogVisible.value = false;
    ElMessage.success("已保存 ACL");
  } finally {
    aclSaving.value = false;
  }
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

.genbi-acl-section {
  margin-bottom: 16px;
}

.genbi-acl-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
</style>
