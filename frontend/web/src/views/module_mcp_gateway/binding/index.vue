<!-- 业务绑定：选择用户和系统，提交 uid_value 与 attrs。停用只改当前这一行。 -->
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
            :perm-create="['module_mcp_gateway:biz-binding:create']"
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
      <p v-if="selectedAttrFields.length" class="px-4 pb-2 text-sm text-gray-500">
        该系统允许的属性：{{ selectedAttrFields.join("、") }}
      </p>
    </FaDialog>
  </div>
</template>

<script setup lang="ts">
import BizBindingAPI, {
  type BizBindingForm,
  type BizBindingPageQuery,
  type BizBindingTable,
} from "@/api/module_mcp_gateway/binding";
import BizSystemAPI, { type BizSystemTable } from "@/api/module_mcp_gateway/system";
import BizUserAPI, { type BizUserTable } from "@/api/module_mcp_gateway/user";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { renderTableOperationCell, type TableOperationAction } from "@utils";

defineOptions({
  name: "McpGatewayBizBinding",
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

const users = ref<BizUserTable[]>([]);
const systems = ref<BizSystemTable[]>([]);

const userOptions = computed(() =>
  users.value
    .filter((item) => item.id)
    .map((item) => ({ label: item.nickname ? `${item.name}（${item.nickname}）` : (item.name ?? String(item.id)), value: item.id })),
);
const systemOptions = computed(() =>
  systems.value.filter((item) => item.id).map((item) => ({ label: item.code ? `${item.name}（${item.code}）` : (item.name ?? String(item.id)), value: item.id })),
);

async function loadOptions() {
  const [userResp, systemResp] = await Promise.all([
    BizUserAPI.listUser({ page_no: 1, page_size: 100 }),
    BizSystemAPI.listSystem({ page_no: 1, page_size: 100 }),
  ]);
  users.value = userResp.data.data?.items ?? [];
  systems.value = systemResp.data.data?.items ?? [];
}

function userLabel(userId?: number) {
  return userOptions.value.find((item) => item.value === userId)?.label ?? (userId ? String(userId) : "");
}

function systemLabel(systemId?: number) {
  return systemOptions.value.find((item) => item.value === systemId)?.label ?? (systemId ? String(systemId) : "");
}

const showSearch = ref(true);
const searchForm = ref<BizBindingPageQuery>({ uid_value: undefined, enabled: undefined });
const searchBarRef = ref();
const searchItems = computed<SearchFormItem[]>(() => [
  { label: "用户标识", key: "uid_value", type: "input", placeholder: "请输入用户标识", clearable: true, span: 6 },
  {
    label: "启用",
    key: "enabled",
    type: "select",
    props: { placeholder: "请选择", options: ENABLED_OPTIONS, clearable: true },
    span: 6,
  },
]);

const createLoading = ref(false);

function rowActions(row: BizBindingTable): TableOperationAction[] {
  return [
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_mcp_gateway:biz-binding:update",
      run: () => void openEdit(row),
    },
    {
      key: "toggle",
      label: row.enabled === false ? "启用" : "停用",
      artType: "edit",
      perm: "module_mcp_gateway:biz-binding:update",
      run: () => void toggleEnabled(row),
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
    apiFn: BizBindingAPI.listBinding,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      {
        prop: "user_id",
        label: "业务用户",
        minWidth: 140,
        showOverflowTooltip: true,
        formatter: (row: BizBindingTable) => userLabel(row.user_id),
      },
      {
        prop: "system_id",
        label: "业务系统",
        minWidth: 160,
        showOverflowTooltip: true,
        formatter: (row: BizBindingTable) => systemLabel(row.system_id),
      },
      { prop: "uid_value", label: "用户标识", minWidth: 120, showOverflowTooltip: true },
      {
        prop: "attrs",
        label: "属性",
        minWidth: 160,
        showOverflowTooltip: true,
        formatter: (row: BizBindingTable) => JSON.stringify(row.attrs ?? {}),
      },
      {
        prop: "enabled",
        label: "启用",
        width: 88,
        formatter: (row: BizBindingTable) => enabledText(row.enabled),
      },
      { prop: "created_time", label: "创建时间", width: 168, showOverflowTooltip: true },
      {
        prop: "operation",
        label: "操作",
        width: 140,
        fixed: "right",
        align: "center",
        formatter: (row: BizBindingTable) =>
          renderTableOperationCell(rowActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

function createInitialForm(): BizBindingForm {
  return {
    id: undefined,
    user_id: undefined,
    system_id: undefined,
    uid_value: "",
    attrs_text: "{}",
    enabled: true,
  };
}

const formData = ref<BizBindingForm>(createInitialForm());
const initialFormData = createInitialForm();
const { dialogVisible } = useCrudDialog();
const formRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);
const rules = reactive({
  user_id: [{ required: true, message: "请选择业务用户", trigger: "change" }],
  system_id: [{ required: true, message: "请选择业务系统", trigger: "change" }],
  uid_value: [{ required: true, message: "请输入用户标识", trigger: "blur" }],
  attrs_text: [jsonObjectRule("绑定属性须为 JSON 对象")],
});

const selectedAttrFields = computed(() => {
  const system = systems.value.find((item) => item.id === formData.value.system_id);
  return system?.attr_fields ?? [];
});

const pairLocked = computed(() => dialogVisible.type === "update");
const dialogFormItems = computed<FormItem[]>(() => [
  {
    label: "业务用户",
    key: "user_id",
    type: "select",
    span: 24,
    props: { placeholder: "请选择业务用户", options: userOptions.value, filterable: true, disabled: pairLocked.value },
  },
  {
    label: "业务系统",
    key: "system_id",
    type: "select",
    span: 24,
    props: { placeholder: "请选择业务系统", options: systemOptions.value, filterable: true, disabled: pairLocked.value },
  },
  { label: "用户标识", key: "uid_value", type: "input", span: 24, props: { placeholder: "业务系统中的用户标识", maxlength: 128 } },
  {
    label: "绑定属性",
    key: "attrs_text",
    type: "input",
    span: 24,
    props: { type: "textarea", rows: 4, placeholder: "JSON 对象，键必须属于系统的属性字段" },
  },
  { label: "启用", key: "enabled", type: "switch", span: 24 },
]);

async function detailForForm(id: number) {
  const response = await BizBindingAPI.detailBinding(id);
  const row = response.data.data;
  const data: BizBindingForm | undefined = row
    ? {
        id: row.id,
        user_id: row.user_id,
        system_id: row.system_id,
        uid_value: row.uid_value ?? "",
        attrs_text: JSON.stringify(row.attrs ?? {}, null, 2),
        enabled: row.enabled !== false,
      }
    : undefined;
  return { data: { data } };
}

async function openEdit(row: BizBindingTable) {
  if (!row.id) return;
  await loadOptions();
  await handleOpenDialog("update", row.id);
}

const { submitLoading, handleCloseDialog, handleOpenDialog, handleSubmit } = useCrudForm<BizBindingForm>({
  formData,
  initialFormData,
  dialogVisible,
  dataFormRef: formRef,
  formRenderKey,
  detailApi: detailForForm,
  createApi: BizBindingAPI.createBinding,
  updateApi: BizBindingAPI.updateBinding,
  titles: { create: "新增绑定", update: "修改绑定" },
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
    await loadOptions();
    await handleOpenDialog("create");
  } finally {
    createLoading.value = false;
  }
}

async function handleSearch(params: BizBindingPageQuery) {
  replaceSearchParams({ uid_value: params.uid_value, enabled: params.enabled });
  await getData();
}

async function onResetSearch() {
  searchForm.value = { uid_value: undefined, enabled: undefined };
  await resetSearchParams();
}

async function toggleEnabled(row: BizBindingTable) {
  if (!row.id) return;
  await BizBindingAPI.updateBinding(row.id, { enabled: row.enabled === false });
  await refreshUpdate();
}

onMounted(() => {
  void loadOptions();
});
</script>
