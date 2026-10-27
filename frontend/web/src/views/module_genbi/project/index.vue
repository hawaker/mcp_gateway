<!-- GenBI 项目：列表 + tiga 对齐工作台（Setup → Modeling → Knowledge → Capabilities → Deploy） -->
<template>
  <div class="fa-full-height">
    <GenbiProjectWorkspace
      v-if="workspaceProjectId"
      :project-id="workspaceProjectId"
      :initial-tab="workspaceTab"
      @back="closeWorkspace"
    />

    <template v-else>
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
    </template>

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
  </div>
</template>

<script setup lang="ts">
import GenbiDatasourceAPI, { type GenbiDatasourceTable } from "@/api/module_genbi/datasource";
import GenbiProjectAPI, {
  type GenbiProjectForm,
  type GenbiProjectPageQuery,
  type GenbiProjectTable,
} from "@/api/module_genbi/project";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { renderTableOperationCell, type TableOperationAction } from "@utils";
import GenbiProjectWorkspace from "./workspace/index.vue";

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

const workspaceProjectId = ref<number>();
const workspaceTab = ref("setup");

function openWorkspace(row: GenbiProjectTable, tab = "setup") {
  if (!row.id) return;
  workspaceTab.value = tab;
  workspaceProjectId.value = row.id;
}

async function closeWorkspace() {
  workspaceProjectId.value = undefined;
  await refreshData();
}

function rowActions(row: GenbiProjectTable): TableOperationAction[] {
  return [
    {
      key: "workspace",
      label: "工作台",
      artType: "edit",
      icon: "ri:layout-grid-line",
      iconColor: "var(--el-color-primary)",
      perm: "module_genbi:project:query",
      run: () => openWorkspace(row, "setup"),
    },
    {
      key: "modeling",
      label: "建模",
      artType: "edit",
      icon: "ri:table-line",
      iconColor: "var(--el-color-primary)",
      perm: "module_genbi:project:update",
      run: () => openWorkspace(row, "modeling"),
    },
    {
      key: "deploy",
      label: "部署",
      artType: "view",
      icon: "ri:rocket-line",
      iconColor: "var(--el-color-success)",
      perm: "module_genbi:project:update",
      run: () => openWorkspace(row, "deploy"),
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
        width: 180,
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

onMounted(() => {
  void loadDatasources();
});
</script>
