<!-- 业务系统：编码创建后不可改，编辑提交时不发送 code -->
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
            :perm-create="['module_mcp_gateway:biz-system:create']"
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
  </div>
</template>

<script setup lang="ts">
import BizSystemAPI, {
  type BizSystemForm,
  type BizSystemPageQuery,
  type BizSystemTable,
} from "@/api/module_mcp_gateway/system";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { renderTableOperationCell, type TableOperationAction } from "@utils";

defineOptions({
  name: "McpGatewayBizSystem",
  inheritAttrs: false,
});

const ENABLED_OPTIONS = [
  { label: "启用", value: true },
  { label: "停用", value: false },
] as const;

function enabledText(enabled?: boolean) {
  return enabled === false ? "停用" : "启用";
}

function jsonObjectRule(message: string) {
  return {
    validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
      const raw = (value ?? "").trim();
      if (!raw) {
        callback();
        return;
      }
      try {
        const parsed = JSON.parse(raw) as unknown;
        if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
          callback(new Error(message));
          return;
        }
        callback();
      } catch {
        callback(new Error(message));
      }
    },
    trigger: "blur",
  };
}

const showSearch = ref(true);
const searchForm = ref<BizSystemPageQuery>({ name: undefined, code: undefined, enabled: undefined });
const searchBarRef = ref();
const searchItems = computed<SearchFormItem[]>(() => [
  { label: "名称", key: "name", type: "input", placeholder: "请输入名称", clearable: true, span: 6 },
  { label: "编码", key: "code", type: "input", placeholder: "请输入编码", clearable: true, span: 6 },
  {
    label: "启用",
    key: "enabled",
    type: "select",
    props: { placeholder: "请选择", options: ENABLED_OPTIONS, clearable: true },
    span: 6,
  },
]);

const createLoading = ref(false);

function rowActions(row: BizSystemTable): TableOperationAction[] {
  return [
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_mcp_gateway:biz-system:update",
      run: () => void handleOpenDialog("update", row.id),
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
    apiFn: BizSystemAPI.listSystem,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "name", label: "名称", minWidth: 120, showOverflowTooltip: true },
      { prop: "code", label: "编码", minWidth: 100, showOverflowTooltip: true },
      { prop: "base_url", label: "基础地址", minWidth: 200, showOverflowTooltip: true },
      { prop: "uid_field", label: "用户标识字段", minWidth: 120, showOverflowTooltip: true },
      {
        prop: "attr_fields",
        label: "属性字段",
        minWidth: 140,
        showOverflowTooltip: true,
        formatter: (row: BizSystemTable) => (row.attr_fields ?? []).join(", "),
      },
      {
        prop: "enabled",
        label: "启用",
        width: 88,
        formatter: (row: BizSystemTable) => enabledText(row.enabled),
      },
      { prop: "created_time", label: "创建时间", width: 168, showOverflowTooltip: true },
      {
        prop: "operation",
        label: "操作",
        width: 100,
        fixed: "right",
        align: "center",
        formatter: (row: BizSystemTable) =>
          renderTableOperationCell(rowActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

function createInitialForm(): BizSystemForm {
  return {
    id: undefined,
    name: "",
    code: "",
    base_url: "",
    enabled: true,
    params_text: "{}",
    uid_field: "",
    attr_fields_text: "",
  };
}

const formData = ref<BizSystemForm>(createInitialForm());
const initialFormData = createInitialForm();
const { dialogVisible } = useCrudDialog();
const formRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);
const rules = reactive({
  name: [{ required: true, message: "请输入名称", trigger: "blur" }],
  code: [{ required: true, message: "请输入编码", trigger: "blur" }],
  base_url: [{ required: true, message: "请输入基础地址", trigger: "blur" }],
  uid_field: [{ required: true, message: "请输入用户标识字段", trigger: "blur" }],
  params_text: [jsonObjectRule("扩展参数须为 JSON 对象")],
});
const dialogFormItems = computed<FormItem[]>(() => [
  { label: "名称", key: "name", type: "input", span: 24, props: { placeholder: "请输入名称", maxlength: 64 } },
  {
    label: "编码",
    key: "code",
    type: "input",
    span: 24,
    props: {
      placeholder: "请输入编码",
      maxlength: 64,
      disabled: dialogVisible.type === "update",
    },
  },
  { label: "基础地址", key: "base_url", type: "input", span: 24, props: { placeholder: "https://oa.example.com", maxlength: 512 } },
  { label: "用户标识字段", key: "uid_field", type: "input", span: 24, props: { placeholder: "例如 user_id", maxlength: 64 } },
  {
    label: "属性字段",
    key: "attr_fields_text",
    type: "input",
    span: 24,
    props: { placeholder: "逗号分隔，例如 dept,title", maxlength: 255 },
  },
  {
    label: "扩展参数",
    key: "params_text",
    type: "input",
    span: 24,
    props: { type: "textarea", rows: 4, placeholder: "JSON 对象，例如 {}" },
  },
  { label: "启用", key: "enabled", type: "switch", span: 24 },
]);

async function detailForForm(id: number) {
  const response = await BizSystemAPI.detailSystem(id);
  const row = response.data.data;
  const data: BizSystemForm | undefined = row
    ? {
        id: row.id,
        name: row.name ?? "",
        code: row.code ?? "",
        base_url: row.base_url ?? "",
        enabled: row.enabled !== false,
        uid_field: row.uid_field ?? "",
        params_text: JSON.stringify(row.params ?? {}, null, 2),
        attr_fields_text: (row.attr_fields ?? []).join(","),
      }
    : undefined;
  return { data: { data } };
}

const { submitLoading, handleCloseDialog, handleOpenDialog, handleSubmit } = useCrudForm<BizSystemForm>({
  formData,
  initialFormData,
  dialogVisible,
  dataFormRef: formRef,
  formRenderKey,
  detailApi: detailForForm,
  createApi: BizSystemAPI.createSystem,
  updateApi: BizSystemAPI.updateSystem,
  titles: { create: "新增业务系统", update: "修改业务系统" },
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

async function handleSearch(params: BizSystemPageQuery) {
  replaceSearchParams({ name: params.name, code: params.code, enabled: params.enabled });
  await getData();
}

async function onResetSearch() {
  searchForm.value = { name: undefined, code: undefined, enabled: undefined };
  await resetSearchParams();
}
</script>
