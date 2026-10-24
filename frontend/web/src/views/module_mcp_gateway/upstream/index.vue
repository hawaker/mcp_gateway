<!-- 上游 MCP：凭证只写不回显。拉取工具后默认未选用，管理员再勾选。 -->
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
            :perm-create="['module_mcp_gateway:upstream:create']"
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
      width="640px"
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
        :label-width="120"
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
      title="上游工具"
      width="920px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="detail"
      confirm-text="关闭"
      @close="toolDialogVisible = false"
    >
      <div class="upstream-tools">
        <div class="upstream-tools__bar">
          <span>{{ toolUpstreamLabel }}</span>
          <ElButton
            v-hasPerm="['module_mcp_gateway:upstream:update']"
            type="primary"
            plain
            :loading="refreshLoading"
            :disabled="refreshLoading"
            @click="handleRefreshTools"
          >
            拉取工具
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
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import BizSystemAPI, { type BizSystemTable } from "@/api/module_mcp_gateway/system";
import UpstreamAPI, {
  type UpstreamForm,
  type UpstreamPageQuery,
  type UpstreamTable,
  type UpstreamToolTable,
} from "@/api/module_mcp_gateway/upstream";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { renderTableOperationCell, type TableOperationAction } from "@utils";

defineOptions({
  name: "McpGatewayUpstream",
  inheritAttrs: false,
});

function selectedText(selected?: boolean) {
  return selected ? "已选用" : "未选用";
}

const systems = ref<BizSystemTable[]>([]);
const systemOptions = computed(() =>
  systems.value
    .filter((item) => item.id)
    .map((item) => ({
      label: item.code ? `${item.name}（${item.code}）` : (item.name ?? String(item.id)),
      value: item.id,
    })),
);

function systemLabel(systemId?: number) {
  return systemOptions.value.find((item) => item.value === systemId)?.label ?? (systemId ? String(systemId) : "");
}

async function loadSystems() {
  const response = await BizSystemAPI.listSystem({ page_no: 1, page_size: 100 });
  systems.value = response.data.data?.items ?? [];
}

const showSearch = ref(true);
const searchForm = ref<UpstreamPageQuery>({ system_id: undefined, url: undefined, credential_header: undefined });
const searchBarRef = ref();
const searchItems = computed<SearchFormItem[]>(() => [
  {
    label: "业务系统",
    key: "system_id",
    type: "select",
    props: { placeholder: "请选择", options: systemOptions.value, clearable: true, filterable: true },
    span: 6,
  },
  { label: "上游地址", key: "url", type: "input", placeholder: "请输入上游地址", clearable: true, span: 6 },
  { label: "凭证请求头", key: "credential_header", type: "input", placeholder: "请输入请求头名称", clearable: true, span: 6 },
]);

const createLoading = ref(false);

function rowActions(row: UpstreamTable): TableOperationAction[] {
  return [
    {
      key: "tools",
      label: "工具",
      artType: "view",
      perm: "module_mcp_gateway:upstream:query",
      run: () => void openTools(row),
    },
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_mcp_gateway:upstream:update",
      run: () => void openEdit(row),
    },
    {
      key: "delete",
      label: "删除",
      artType: "delete",
      perm: "module_mcp_gateway:upstream:delete",
      run: () => void removeUpstream(row),
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
  refreshRemove,
} = useTable({
  core: {
    apiFn: UpstreamAPI.listUpstream,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      {
        prop: "system_id",
        label: "业务系统",
        minWidth: 160,
        showOverflowTooltip: true,
        formatter: (row: UpstreamTable) => systemLabel(row.system_id),
      },
      { prop: "url", label: "上游地址", minWidth: 240, showOverflowTooltip: true },
      { prop: "credential_header", label: "凭证请求头", minWidth: 140, showOverflowTooltip: true },
      { prop: "created_time", label: "创建时间", width: 168, showOverflowTooltip: true },
      {
        prop: "operation",
        label: "操作",
        width: 180,
        fixed: "right",
        align: "center",
        formatter: (row: UpstreamTable) =>
          renderTableOperationCell(rowActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

function createInitialForm(): UpstreamForm {
  return {
    id: undefined,
    system_id: undefined,
    url: "",
    credential_header: "",
    credential_value: "",
  };
}

const formData = ref<UpstreamForm>(createInitialForm());
const initialFormData = createInitialForm();
const { dialogVisible } = useCrudDialog();
const formRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);
const rules = reactive({
  system_id: [{ required: true, message: "请选择业务系统", trigger: "change" }],
  url: [
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        const text = (value ?? "").trim();
        if (!text) {
          callback(new Error("请输入上游地址"));
          return;
        }
        if (!/^https?:\/\//i.test(text)) {
          callback(new Error("上游地址必须以 http:// 或 https:// 开头"));
          return;
        }
        callback();
      },
      trigger: "blur",
    },
  ],
  credential_header: [{ required: true, message: "请输入凭证请求头", trigger: "blur" }],
  credential_value: [
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (dialogVisible.type === "create" && !(value ?? "").trim()) {
          callback(new Error("请输入凭证"));
          return;
        }
        callback();
      },
      trigger: "blur",
    },
  ],
});

const dialogFormItems = computed<FormItem[]>(() => [
  {
    label: "业务系统",
    key: "system_id",
    type: "select",
    span: 24,
    props: {
      placeholder: "请选择业务系统",
      options: systemOptions.value,
      filterable: true,
      disabled: dialogVisible.type === "update",
    },
  },
  {
    label: "上游地址",
    key: "url",
    type: "input",
    span: 24,
    props: { placeholder: "https://mcp.example.com/rpc", maxlength: 2048 },
  },
  {
    label: "凭证请求头",
    key: "credential_header",
    type: "input",
    span: 24,
    props: { placeholder: "例如 X-Api-Key", maxlength: 128 },
  },
  {
    label: "凭证",
    key: "credential_value",
    type: "input",
    span: 24,
    props: {
      type: "password",
      showPassword: true,
      maxlength: 8192,
      placeholder: dialogVisible.type === "update" ? "留空则不修改" : "只写入，保存后不再显示",
    },
  },
]);

async function detailForForm(id: number) {
  const response = await UpstreamAPI.detailUpstream(id);
  const row = response.data.data;
  const data: UpstreamForm | undefined = row
    ? {
        id: row.id,
        system_id: row.system_id,
        url: row.url ?? "",
        credential_header: row.credential_header ?? "",
        credential_value: "",
      }
    : undefined;
  return { data: { data } };
}

const { submitLoading, handleCloseDialog, handleOpenDialog, handleSubmit } = useCrudForm<UpstreamForm>({
  formData,
  initialFormData,
  dialogVisible,
  dataFormRef: formRef,
  formRenderKey,
  detailApi: detailForForm,
  createApi: UpstreamAPI.createUpstream,
  updateApi: UpstreamAPI.updateUpstream,
  titles: { create: "新增上游 MCP", update: "修改上游 MCP" },
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
    await loadSystems();
    await handleOpenDialog("create");
  } finally {
    createLoading.value = false;
  }
}

async function openEdit(row: UpstreamTable) {
  if (!row.id) return;
  await loadSystems();
  await handleOpenDialog("update", row.id);
}

async function removeUpstream(row: UpstreamTable) {
  if (!row.id) return;
  try {
    await confirmDelete(`确定删除「${row.url ?? row.id}」吗？`);
    await UpstreamAPI.deleteUpstream([row.id]);
    await refreshRemove();
  } catch {
    // 用户取消
  }
}

async function handleSearch(params: UpstreamPageQuery) {
  replaceSearchParams({
    system_id: params.system_id,
    url: params.url,
    credential_header: params.credential_header,
  });
  await getData();
}

async function onResetSearch() {
  searchForm.value = { system_id: undefined, url: undefined, credential_header: undefined };
  await resetSearchParams();
}

const toolDialogVisible = ref(false);
const toolUpstreamId = ref<number | undefined>();
const toolUpstreamLabel = ref("");
const refreshLoading = ref(false);

function toolActions(row: UpstreamToolTable): TableOperationAction[] {
  return [
    {
      key: row.selected ? "unselect" : "select",
      label: row.selected ? "取消选用" : "选用",
      artType: "edit",
      perm: "module_mcp_gateway:upstream:update",
      run: () => void setSelected(row, !row.selected),
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
    apiFn: UpstreamAPI.listTool,
    apiParams: { page_no: 1, page_size: 10, upstream_id: undefined },
    immediate: false,
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "remote_name", label: "远端名称", minWidth: 140, showOverflowTooltip: true },
      { prop: "external_name", label: "外部名称", minWidth: 180, showOverflowTooltip: true },
      {
        prop: "selected",
        label: "选用",
        width: 88,
        formatter: (row: UpstreamToolTable) => selectedText(row.selected),
      },
      {
        prop: "input_schema",
        label: "入参结构",
        minWidth: 180,
        showOverflowTooltip: true,
        formatter: (row: UpstreamToolTable) => JSON.stringify(row.input_schema ?? {}),
      },
      {
        prop: "operation",
        label: "操作",
        width: 110,
        fixed: "right",
        align: "center",
        formatter: (row: UpstreamToolTable) =>
          renderTableOperationCell(toolActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

async function openTools(row: UpstreamTable) {
  if (!row.id) return;
  toolUpstreamId.value = row.id;
  toolUpstreamLabel.value = row.url ?? systemLabel(row.system_id);
  toolDialogVisible.value = true;
  replaceToolSearch({ upstream_id: row.id, remote_name: undefined, external_name: undefined, selected: undefined });
  await getToolData();
}

async function handleRefreshTools() {
  if (!toolUpstreamId.value) return;
  refreshLoading.value = true;
  try {
    await UpstreamAPI.refreshTools(toolUpstreamId.value);
    await getToolData();
    ElMessage.success("已拉取上游工具");
  } finally {
    refreshLoading.value = false;
  }
}

async function setSelected(row: UpstreamToolTable, selected: boolean) {
  if (!row.id) return;
  await UpstreamAPI.updateTool(row.id, selected);
  await getToolData();
}

onMounted(() => {
  void loadSystems();
});
</script>

<style scoped>
.upstream-tools {
  padding: 0 16px 16px;
}

.upstream-tools__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
</style>
