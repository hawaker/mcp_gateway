<!-- GenBI 数据源：外连配置，密钥只写不回显；支持测连 -->
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
            :perm-create="['module_genbi:datasource:create']"
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
      width="720px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      :form-mode="dialogVisible.type"
      :confirm-loading="submitLoading"
      @cancel="handleCloseDialog"
      @close="handleCloseDialog"
      @confirm="handleSubmit()"
    >
      <div class="genbi-ds-dialog">
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
        <div class="genbi-ds-dialog__actions">
          <ElButton
            v-hasPerm="['module_genbi:datasource:update']"
            :loading="testFormLoading"
            @click="testFromForm"
          >
            测试连接
          </ElButton>
        </div>
      </div>
    </FaDialog>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import GenbiDatasourceAPI, {
  WREN_TYPE_OPTIONS,
  type GenbiDatasourceForm,
  type GenbiDatasourcePageQuery,
  type GenbiDatasourceTable,
} from "@/api/module_genbi/datasource";
import BizSystemAPI, { type BizSystemTable } from "@/api/module_mcp_gateway/system";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { renderTableOperationCell, type TableOperationAction } from "@utils";

defineOptions({
  name: "GenbiDatasource",
  inheritAttrs: false,
});

const ENABLED_OPTIONS = [
  { label: "启用", value: true },
  { label: "停用", value: false },
] as const;

function enabledText(enabled?: boolean) {
  return enabled === false ? "停用" : "启用";
}

function wrenTypeLabel(value?: string) {
  return WREN_TYPE_OPTIONS.find((item) => item.value === value)?.label ?? value ?? "";
}

const systems = ref<BizSystemTable[]>([]);
const systemOptions = computed(() =>
  systems.value.filter((item) => item.id).map((item) => ({ label: `${item.name} (${item.code})`, value: item.id })),
);

async function loadSystems() {
  const response = await BizSystemAPI.listSystem({ page_no: 1, page_size: 200 });
  systems.value = response.data.data?.items ?? [];
}

function systemLabel(systemId?: number) {
  const row = systems.value.find((item) => item.id === systemId);
  return row ? `${row.name} (${row.code})` : systemId ? String(systemId) : "";
}

const showSearch = ref(true);
const searchForm = ref<GenbiDatasourcePageQuery>({
  name: undefined,
  system_id: undefined,
  wren_type: undefined,
  enabled: undefined,
});
const searchBarRef = ref();
const searchItems = computed<SearchFormItem[]>(() => [
  { label: "名称", key: "name", type: "input", placeholder: "请输入名称", clearable: true, span: 6 },
  {
    label: "业务系统",
    key: "system_id",
    type: "select",
    props: { placeholder: "请选择", options: systemOptions.value, clearable: true, filterable: true },
    span: 6,
  },
  {
    label: "类型",
    key: "wren_type",
    type: "select",
    props: { placeholder: "请选择", options: WREN_TYPE_OPTIONS, clearable: true },
    span: 6,
  },
  {
    label: "启用",
    key: "enabled",
    type: "select",
    props: { placeholder: "请选择", options: ENABLED_OPTIONS, clearable: true },
    span: 6,
  },
]);

const createLoading = ref(false);
const testFormLoading = ref(false);

function rowActions(row: GenbiDatasourceTable): TableOperationAction[] {
  return [
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_genbi:datasource:update",
      run: () => void openEdit(row),
    },
    {
      key: "test",
      label: "测连",
      artType: "view",
      icon: "ri:plug-line",
      iconColor: "var(--el-color-success)",
      perm: "module_genbi:datasource:query",
      run: () => void testSaved(row),
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
    apiFn: GenbiDatasourceAPI.listDatasource,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "name", label: "名称", minWidth: 140, showOverflowTooltip: true },
      {
        prop: "system_id",
        label: "业务系统",
        minWidth: 140,
        showOverflowTooltip: true,
        formatter: (row: GenbiDatasourceTable) => systemLabel(row.system_id),
      },
      {
        prop: "wren_type",
        label: "类型",
        width: 120,
        formatter: (row: GenbiDatasourceTable) => wrenTypeLabel(row.wren_type),
      },
      { prop: "host", label: "主机", minWidth: 140, showOverflowTooltip: true },
      { prop: "port", label: "端口", width: 80 },
      { prop: "database", label: "数据库", minWidth: 120, showOverflowTooltip: true },
      {
        prop: "enabled",
        label: "启用",
        width: 88,
        formatter: (row: GenbiDatasourceTable) => enabledText(row.enabled),
      },
      { prop: "created_time", label: "创建时间", width: 168, showOverflowTooltip: true },
      {
        prop: "operation",
        label: "操作",
        width: 140,
        fixed: "right",
        align: "center",
        formatter: (row: GenbiDatasourceTable) =>
          renderTableOperationCell(rowActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

function createInitialForm(): GenbiDatasourceForm {
  return {
    id: undefined,
    system_id: undefined,
    name: "",
    wren_type: "POSTGRES",
    host: "",
    port: 5432,
    username: "",
    password: "",
    database: "",
    db_schema: "public",
    url: "",
    api_key: "",
    private_key: "",
    token: "",
    config: {},
    description: "",
    enabled: true,
  };
}

const formData = ref<GenbiDatasourceForm>(createInitialForm());
const initialFormData = createInitialForm();
const { dialogVisible } = useCrudDialog();
const formRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);
const rules = reactive({
  system_id: [{ required: true, message: "请选择业务系统", trigger: "change" }],
  name: [{ required: true, message: "请输入名称", trigger: "blur" }],
  wren_type: [{ required: true, message: "请选择类型", trigger: "change" }],
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
  { label: "名称", key: "name", type: "input", span: 24, props: { placeholder: "请输入名称", maxlength: 128 } },
  {
    label: "类型",
    key: "wren_type",
    type: "select",
    span: 24,
    props: { placeholder: "请选择", options: WREN_TYPE_OPTIONS },
  },
  { label: "主机", key: "host", type: "input", span: 24, props: { placeholder: "host.example.com", maxlength: 255 } },
  { label: "端口", key: "port", type: "number", span: 24, props: { min: 0, max: 65535, controlsPosition: "right" } },
  { label: "用户名", key: "username", type: "input", span: 24, props: { placeholder: "可留空", maxlength: 128 } },
  {
    label: "密码",
    key: "password",
    type: "input",
    span: 24,
    props: {
      type: "password",
      showPassword: true,
      maxlength: 2048,
      placeholder: dialogVisible.type === "update" ? "留空则不修改" : "只写入，保存后不再显示",
    },
  },
  { label: "数据库", key: "database", type: "input", span: 24, props: { placeholder: "database", maxlength: 128 } },
  { label: "Schema", key: "db_schema", type: "input", span: 24, props: { placeholder: "public", maxlength: 128 } },
  { label: "连接 URL", key: "url", type: "input", span: 24, props: { placeholder: "可选；部分类型用 URL", maxlength: 1024 } },
  {
    label: "API Key",
    key: "api_key",
    type: "input",
    span: 24,
    props: {
      type: "password",
      showPassword: true,
      maxlength: 4096,
      placeholder: dialogVisible.type === "update" ? "留空则不修改" : "可选",
    },
  },
  {
    label: "Token",
    key: "token",
    type: "input",
    span: 24,
    props: {
      type: "password",
      showPassword: true,
      maxlength: 4096,
      placeholder: dialogVisible.type === "update" ? "留空则不修改" : "可选",
    },
  },
  { label: "描述", key: "description", type: "input", span: 24, props: { placeholder: "可留空", maxlength: 512 } },
  { label: "启用", key: "enabled", type: "switch", span: 24 },
]);

async function detailForForm(id: number) {
  const response = await GenbiDatasourceAPI.detailDatasource(id);
  const row = response.data.data;
  const detail: GenbiDatasourceForm | undefined = row
    ? {
        id: row.id,
        system_id: row.system_id,
        name: row.name ?? "",
        wren_type: row.wren_type ?? "POSTGRES",
        host: row.host ?? "",
        port: row.port,
        username: row.username ?? "",
        password: "",
        database: row.database ?? "",
        db_schema: row.db_schema ?? "",
        url: row.url ?? "",
        api_key: "",
        private_key: "",
        token: "",
        config: row.config ?? {},
        description: row.description ?? "",
        enabled: row.enabled !== false,
      }
    : undefined;
  return { data: { data: detail } };
}

const { submitLoading, handleCloseDialog, handleOpenDialog, handleSubmit } = useCrudForm<GenbiDatasourceForm>({
  formData,
  initialFormData,
  dialogVisible,
  dataFormRef: formRef,
  formRenderKey,
  detailApi: detailForForm,
  createApi: GenbiDatasourceAPI.createDatasource,
  updateApi: GenbiDatasourceAPI.updateDatasource,
  titles: { create: "新增数据源", update: "修改数据源" },
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

async function openEdit(row: GenbiDatasourceTable) {
  if (!row.id) return;
  await loadSystems();
  await handleOpenDialog("update", row.id);
}

async function testSaved(row: GenbiDatasourceTable) {
  if (!row.id) return;
  await GenbiDatasourceAPI.testById(row.id);
  ElMessage.success("连接成功");
}

async function testFromForm() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid && dialogVisible.type === "create") return;
  testFormLoading.value = true;
  try {
    await GenbiDatasourceAPI.testConfig(formData.value);
    ElMessage.success("连接成功");
  } finally {
    testFormLoading.value = false;
  }
}

async function handleSearch(params: GenbiDatasourcePageQuery) {
  replaceSearchParams({
    name: params.name,
    system_id: params.system_id,
    wren_type: params.wren_type,
    enabled: params.enabled,
  });
  await getData();
}

async function onResetSearch() {
  searchForm.value = { name: undefined, system_id: undefined, wren_type: undefined, enabled: undefined };
  await resetSearchParams();
}

onMounted(() => {
  void loadSystems();
});
</script>

<style scoped>
.genbi-ds-dialog__actions {
  display: flex;
  justify-content: flex-end;
  padding: 0 4px 8px;
}
</style>
