<!-- GenBI 项目：每数据源一条；同步 MDL 模型后可部署 -->
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
            :perm-create="['module_genbi:project:create']"
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
      v-model="modelsVisible"
      title="同步模型"
      width="860px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="create"
      :confirm-loading="modelsSaving"
      confirm-text="保存模型"
      @cancel="modelsVisible = false"
      @close="modelsVisible = false"
      @confirm="saveModels"
    >
      <div class="genbi-models">
        <p class="genbi-models__hint">
          整表替换项目下的 MDL 模型。JSON 数组，每项含 display_name / source_table_name / reference_name / columns。
        </p>
        <ElInput
          v-model="modelsJson"
          type="textarea"
          :rows="16"
          placeholder='[{"display_name":"订单","source_table_name":"orders","reference_name":"orders","columns":[{"display_name":"ID","source_column_name":"id","column_type":"integer"}]}]'
        />
      </div>
    </FaDialog>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import GenbiDatasourceAPI, { type GenbiDatasourceTable } from "@/api/module_genbi/datasource";
import GenbiProjectAPI, {
  type GenbiModelIn,
  type GenbiProjectForm,
  type GenbiProjectPageQuery,
  type GenbiProjectTable,
} from "@/api/module_genbi/project";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { renderTableOperationCell, type TableOperationAction } from "@utils";

defineOptions({
  name: "GenbiProject",
  inheritAttrs: false,
});

const datasources = ref<GenbiDatasourceTable[]>([]);
const datasourceOptions = computed(() =>
  datasources.value
    .filter((item) => item.id)
    .map((item) => ({ label: `${item.name} (#${item.id})`, value: item.id })),
);

async function loadDatasources() {
  const response = await GenbiDatasourceAPI.listDatasource({ page_no: 1, page_size: 200 });
  datasources.value = response.data.data?.items ?? [];
}

function datasourceLabel(id?: number) {
  const row = datasources.value.find((item) => item.id === id);
  return row?.name || (id ? String(id) : "");
}

const showSearch = ref(true);
const searchForm = ref<GenbiProjectPageQuery>({
  display_name: undefined,
  datasource_id: undefined,
  onboarding_status: undefined,
});
const searchBarRef = ref();
const searchItems = computed<SearchFormItem[]>(() => [
  { label: "名称", key: "display_name", type: "input", placeholder: "请输入名称", clearable: true, span: 6 },
  {
    label: "数据源",
    key: "datasource_id",
    type: "select",
    props: { placeholder: "请选择", options: datasourceOptions.value, clearable: true, filterable: true },
    span: 6,
  },
  {
    label: "状态",
    key: "onboarding_status",
    type: "input",
    placeholder: "如 not_started / deployed",
    clearable: true,
    span: 6,
  },
]);

const createLoading = ref(false);

function rowActions(row: GenbiProjectTable): TableOperationAction[] {
  return [
    {
      key: "models",
      label: "模型",
      artType: "edit",
      icon: "ri:table-line",
      iconColor: "var(--el-color-primary)",
      perm: "module_genbi:project:update",
      run: () => void openModels(row),
    },
    {
      key: "deploy",
      label: "部署",
      artType: "view",
      icon: "ri:rocket-line",
      iconColor: "var(--el-color-success)",
      perm: "module_genbi:project:update",
      run: () => void deployProject(row),
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
} = useTable({
  core: {
    apiFn: GenbiProjectAPI.listProject,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "display_name", label: "名称", minWidth: 160, showOverflowTooltip: true },
      {
        prop: "datasource_id",
        label: "数据源",
        minWidth: 140,
        showOverflowTooltip: true,
        formatter: (row: GenbiProjectTable) => datasourceLabel(row.datasource_id),
      },
      { prop: "onboarding_status", label: "状态", minWidth: 120, showOverflowTooltip: true },
      { prop: "language", label: "语言", width: 90 },
      { prop: "created_time", label: "创建时间", width: 168, showOverflowTooltip: true },
      {
        prop: "operation",
        label: "操作",
        width: 140,
        fixed: "right",
        align: "center",
        formatter: (row: GenbiProjectTable) =>
          renderTableOperationCell(rowActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

function createInitialForm(): GenbiProjectForm {
  return {
    id: undefined,
    datasource_id: undefined,
    display_name: "",
    onboarding_status: "not_started",
    language: "zh-CN",
    agent_profile: {},
  };
}

const formData = ref<GenbiProjectForm>(createInitialForm());
const initialFormData = createInitialForm();
const { dialogVisible } = useCrudDialog();
const formRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);
const rules = reactive({
  datasource_id: [{ required: true, message: "请选择数据源", trigger: "change" }],
  display_name: [{ required: true, message: "请输入名称", trigger: "blur" }],
});
const dialogFormItems = computed<FormItem[]>(() => [
  {
    label: "数据源",
    key: "datasource_id",
    type: "select",
    span: 24,
    props: { placeholder: "请选择数据源", options: datasourceOptions.value, filterable: true },
  },
  {
    label: "显示名称",
    key: "display_name",
    type: "input",
    span: 24,
    props: { placeholder: "请输入显示名称", maxlength: 255 },
  },
  {
    label: "语言",
    key: "language",
    type: "input",
    span: 24,
    props: { placeholder: "zh-CN", maxlength: 16 },
  },
]);

const { submitLoading, handleCloseDialog, handleOpenDialog, handleSubmit } = useCrudForm<GenbiProjectForm>({
  formData,
  initialFormData,
  dialogVisible,
  dataFormRef: formRef,
  formRenderKey,
  createApi: GenbiProjectAPI.createProject,
  titles: { create: "新增项目" },
  onCreateSuccess: async () => {
    await refreshCreate();
  },
});

async function handleAdd() {
  createLoading.value = true;
  try {
    await loadDatasources();
    await handleOpenDialog("create");
  } finally {
    createLoading.value = false;
  }
}

async function handleSearch(params: GenbiProjectPageQuery) {
  replaceSearchParams({
    display_name: params.display_name,
    datasource_id: params.datasource_id,
    onboarding_status: params.onboarding_status,
  });
  await getData();
}

async function onResetSearch() {
  searchForm.value = { display_name: undefined, datasource_id: undefined, onboarding_status: undefined };
  await resetSearchParams();
}

const modelsVisible = ref(false);
const modelsSaving = ref(false);
const modelsJson = ref("[]");
const activeProject = ref<GenbiProjectTable>();

function modelsToSyncPayload(models: Awaited<ReturnType<typeof GenbiProjectAPI.listModels>>["data"]["data"]): GenbiModelIn[] {
  return (models ?? []).map((model) => ({
    display_name: model.display_name || "",
    source_table_name: model.source_table_name || "",
    reference_name: model.reference_name || "",
    ref_sql: model.ref_sql ?? null,
    cached: model.cached === true,
    refresh_time: model.refresh_time ?? null,
    properties: model.properties ?? null,
    columns: (model.columns ?? []).map((col) => ({
      display_name: col.display_name || "",
      source_column_name: col.source_column_name || "",
      column_type: col.column_type || "varchar",
      is_calculated: col.is_calculated === true,
      expression: col.expression ?? null,
      properties: col.properties ?? null,
    })),
  }));
}

async function openModels(row: GenbiProjectTable) {
  if (!row.id) return;
  activeProject.value = row;
  const response = await GenbiProjectAPI.listModels(row.id);
  const payload = modelsToSyncPayload(response.data.data);
  modelsJson.value = JSON.stringify(payload.length ? payload : [], null, 2);
  modelsVisible.value = true;
}

async function saveModels() {
  const projectId = activeProject.value?.id;
  if (!projectId) return;
  let models: GenbiModelIn[];
  try {
    const parsed = JSON.parse(modelsJson.value) as unknown;
    if (!Array.isArray(parsed) || parsed.length < 1) {
      ElMessage.error("模型须为非空 JSON 数组");
      return;
    }
    models = parsed as GenbiModelIn[];
  } catch {
    ElMessage.error("模型 JSON 无法解析");
    return;
  }
  modelsSaving.value = true;
  try {
    await GenbiProjectAPI.syncModels(projectId, models);
    modelsVisible.value = false;
    ElMessage.success("已保存模型");
    await refreshData();
  } finally {
    modelsSaving.value = false;
  }
}

async function deployProject(row: GenbiProjectTable) {
  if (!row.id) return;
  try {
    await ElMessageBox.confirm(`确认部署项目「${row.display_name || row.id}」？`, "部署", {
      type: "warning",
      confirmButtonText: "部署",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  const response = await GenbiProjectAPI.deploy(row.id, false);
  const result = response.data.data;
  if (result?.error) {
    ElMessage.error(result.error);
  } else {
    ElMessage.success(`部署完成：${result?.status || "ok"}`);
  }
  await refreshData();
}

onMounted(() => {
  void loadDatasources();
});
</script>

<style scoped>
.genbi-models {
  padding: 0 16px 12px;
}

.genbi-models__hint {
  margin: 0 0 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}
</style>
