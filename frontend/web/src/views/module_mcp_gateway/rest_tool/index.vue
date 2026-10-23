<!-- REST 工具：创建时即可调试。调试发送当前表单，不保存，业务 token 默认遮住。 -->
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
            :perm-create="['module_mcp_gateway:rest-tool:create']"
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
      width="920px"
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
      <section class="rest-debug">
        <h3 class="rest-debug__title">调试当前表单</h3>
        <p class="rest-debug__note">不必先保存。选择一个已绑定该系统的用户，按当前表单请求业务接口。业务 token 默认遮住。</p>
        <div class="rest-debug__row">
          <span>调试用户</span>
          <ElSelect v-model="debugUserId" filterable clearable placeholder="选择已绑定该系统的用户" class="rest-debug__user">
            <ElOption v-for="item in boundUsers" :key="item.user_id" :label="item.label" :value="item.user_id" />
          </ElSelect>
        </div>
        <div class="rest-debug__row">
          <span>调用参数</span>
          <ElInput v-model="debugArguments" type="textarea" :rows="4" placeholder='JSON 对象，例如 {"page": 1}' />
        </div>
        <div class="rest-debug__actions">
          <ElCheckbox v-model="debugReveal">显示业务 token</ElCheckbox>
          <ElButton type="primary" plain :loading="debugLoading" @click="handleDebug">调试</ElButton>
        </div>
        <div v-if="debugResult" class="rest-debug__result">
          <p>HTTP 状态：{{ debugResult.status ?? "未请求" }}</p>
          <p v-if="debugResult.link">验证链接：{{ debugResult.link }}</p>
          <p>请求</p>
          <pre>{{ formatDebug(debugResult.request) }}</pre>
          <p>响应</p>
          <pre>{{ formatDebug(debugResult.response) }}</pre>
        </div>
      </section>
    </FaDialog>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import BizBindingAPI, { type BizBindingTable } from "@/api/module_mcp_gateway/binding";
import RestToolAPI, {
  type RestToolDebugResult,
  type RestToolForm,
  type RestToolPageQuery,
  type RestToolTable,
} from "@/api/module_mcp_gateway/rest_tool";
import BizSystemAPI, { type BizSystemTable } from "@/api/module_mcp_gateway/system";
import BizUserAPI, { type BizUserTable } from "@/api/module_mcp_gateway/user";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { renderTableOperationCell, type TableOperationAction } from "@utils";

defineOptions({
  name: "McpGatewayRestTool",
  inheritAttrs: false,
});

const ENABLED_OPTIONS = [
  { label: "启用", value: true },
  { label: "停用", value: false },
] as const;

const REQUEST_OPTIONS = ["GET", "POST", "PUT", "PATCH", "DELETE"].map((value) => ({ label: value, value }));
const TOKEN_IN_OPTIONS = [
  { label: "请求头", value: "header" },
  { label: "Query", value: "query" },
  { label: "Body", value: "body" },
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

function formatDebug(value: unknown) {
  if (value === undefined || value === null || value === "") return "无";
  return JSON.stringify(value, null, 2);
}

const users = ref<BizUserTable[]>([]);
const systems = ref<BizSystemTable[]>([]);
const boundUsers = ref<{ user_id: number; label: string }[]>([]);
const debugUserId = ref<number | undefined>();
const debugArguments = ref("{}");
const debugReveal = ref(false);
const debugLoading = ref(false);
const debugResult = ref<RestToolDebugResult | null>(null);

const userOptions = computed(() =>
  users.value
    .filter((item) => item.id)
    .map((item) => ({ label: item.nickname ? `${item.name}（${item.nickname}）` : (item.name ?? String(item.id)), value: item.id })),
);
const systemOptions = computed(() =>
  systems.value.filter((item) => item.id).map((item) => ({ label: item.code ? `${item.name}（${item.code}）` : (item.name ?? String(item.id)), value: item.id })),
);

function userLabel(userId?: number) {
  return userOptions.value.find((item) => item.value === userId)?.label ?? (userId ? String(userId) : "");
}

function systemLabel(systemId?: number) {
  return systemOptions.value.find((item) => item.value === systemId)?.label ?? (systemId ? String(systemId) : "");
}

async function loadOptions() {
  const [userResp, systemResp] = await Promise.all([
    BizUserAPI.listUser({ page_no: 1, page_size: 100 }),
    BizSystemAPI.listSystem({ page_no: 1, page_size: 100 }),
  ]);
  users.value = userResp.data.data?.items ?? [];
  systems.value = systemResp.data.data?.items ?? [];
}

async function loadBoundUsers(systemId?: number) {
  boundUsers.value = [];
  if (!systemId) return;
  const response = await BizBindingAPI.listBinding({ page_no: 1, page_size: 100, system_id: systemId, enabled: true });
  const rows = (response.data.data?.items ?? []).filter((row: BizBindingTable) => row.enabled !== false && row.user_id);
  boundUsers.value = rows.map((row) => ({
    user_id: row.user_id as number,
    label: `${userLabel(row.user_id)} / ${row.uid_value ?? ""}`,
  }));
}

const showSearch = ref(true);
const searchForm = ref<RestToolPageQuery>({ name: undefined, system_id: undefined, request_type: undefined, enabled: undefined });
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
    label: "方法",
    key: "request_type",
    type: "select",
    props: { placeholder: "请选择", options: REQUEST_OPTIONS, clearable: true },
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

function rowActions(row: RestToolTable): TableOperationAction[] {
  return [
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_mcp_gateway:rest-tool:update",
      run: () => void openEdit(row),
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
    apiFn: RestToolAPI.listTool,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "name", label: "名称", minWidth: 120, showOverflowTooltip: true },
      { prop: "display_name", label: "显示名", minWidth: 120, showOverflowTooltip: true },
      { prop: "request_type", label: "方法", width: 88 },
      { prop: "url", label: "地址", minWidth: 200, showOverflowTooltip: true },
      {
        prop: "system_id",
        label: "业务系统",
        minWidth: 140,
        showOverflowTooltip: true,
        formatter: (row: RestToolTable) => systemLabel(row.system_id),
      },
      {
        prop: "enabled",
        label: "启用",
        width: 88,
        formatter: (row: RestToolTable) => enabledText(row.enabled),
      },
      { prop: "created_time", label: "创建时间", width: 168, showOverflowTooltip: true },
      {
        prop: "operation",
        label: "操作",
        width: 100,
        fixed: "right",
        align: "center",
        formatter: (row: RestToolTable) =>
          renderTableOperationCell(rowActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

function createInitialForm(): RestToolForm {
  return {
    id: undefined,
    name: "",
    display_name: "",
    url: "",
    description: "",
    request_type: "GET",
    headers_text: "{}",
    input_schema_text: "{}",
    output_schema_text: "{}",
    jsonpath_filter: "",
    query_mapping_text: "{}",
    header_mapping_text: "{}",
    timeout_ms: undefined,
    token_in: "header",
    token_name: "Authorization",
    enabled: true,
    system_id: undefined,
  };
}

function resetDebug() {
  debugUserId.value = undefined;
  debugArguments.value = "{}";
  debugReveal.value = false;
  debugResult.value = null;
  boundUsers.value = [];
}

const formData = ref<RestToolForm>(createInitialForm());
const initialFormData = createInitialForm();
const { dialogVisible } = useCrudDialog();
const formRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);
const rules = reactive({
  system_id: [{ required: true, message: "请选择业务系统", trigger: "change" }],
  name: [{ required: true, message: "请输入名称", trigger: "blur" }],
  display_name: [{ required: true, message: "请输入显示名", trigger: "blur" }],
  url: [{ required: true, message: "请输入接口地址", trigger: "blur" }],
  request_type: [{ required: true, message: "请选择请求方法", trigger: "change" }],
  headers_text: [jsonObjectRule("请求头须为 JSON 对象")],
  input_schema_text: [jsonObjectRule("入参结构须为 JSON 对象")],
  output_schema_text: [jsonObjectRule("出参结构须为 JSON 对象")],
  query_mapping_text: [jsonObjectRule("Query 映射须为 JSON 对象")],
  header_mapping_text: [jsonObjectRule("Header 映射须为 JSON 对象")],
});

const dialogFormItems = computed<FormItem[]>(() => [
  {
    label: "业务系统",
    key: "system_id",
    type: "select",
    span: 24,
    props: { placeholder: "请选择业务系统", options: systemOptions.value, filterable: true },
  },
  { label: "名称", key: "name", type: "input", span: 24, props: { placeholder: "请输入名称", maxlength: 128 } },
  { label: "显示名", key: "display_name", type: "input", span: 24, props: { placeholder: "请输入显示名", maxlength: 128 } },
  { label: "接口地址", key: "url", type: "input", span: 24, props: { placeholder: "/todos/{id} 或完整 http(s) 地址", maxlength: 2048 } },
  { label: "描述", key: "description", type: "input", span: 24, props: { type: "textarea", rows: 2, maxlength: 1024 } },
  {
    label: "请求方法",
    key: "request_type",
    type: "select",
    span: 24,
    props: { placeholder: "请选择", options: REQUEST_OPTIONS },
  },
  { label: "请求头", key: "headers_text", type: "input", span: 24, props: { type: "textarea", rows: 3, placeholder: "JSON 对象，可用 {{user.uid}}、{{token}}" } },
  { label: "入参结构", key: "input_schema_text", type: "input", span: 24, props: { type: "textarea", rows: 3, placeholder: "JSON Schema 或 {}" } },
  { label: "出参结构", key: "output_schema_text", type: "input", span: 24, props: { type: "textarea", rows: 3, placeholder: "JSON 对象" } },
  { label: "Json Path", key: "jsonpath_filter", type: "input", span: 24, props: { placeholder: "例如 $.data.items", maxlength: 512 } },
  { label: "Query 映射", key: "query_mapping_text", type: "input", span: 24, props: { type: "textarea", rows: 2, placeholder: '{"参数名": "query 名"}' } },
  { label: "Header 映射", key: "header_mapping_text", type: "input", span: 24, props: { type: "textarea", rows: 2, placeholder: '{"参数名": "Header 名"}' } },
  { label: "超时(毫秒)", key: "timeout_ms", type: "number", span: 24, props: { min: 1, step: 1000, controlsPosition: "right" } },
  {
    label: "Token 位置",
    key: "token_in",
    type: "select",
    span: 24,
    props: { placeholder: "请选择", options: TOKEN_IN_OPTIONS },
  },
  { label: "Token 字段", key: "token_name", type: "input", span: 24, props: { placeholder: "默认 Authorization", maxlength: 128 } },
  { label: "启用", key: "enabled", type: "switch", span: 24 },
]);

watch(
  () => formData.value.system_id,
  (systemId) => {
    debugUserId.value = undefined;
    void loadBoundUsers(systemId);
  },
);

function rowToForm(row: RestToolTable): RestToolForm {
  return {
    id: row.id,
    name: row.name ?? "",
    display_name: row.display_name ?? "",
    url: row.url ?? "",
    description: row.description ?? "",
    request_type: row.request_type ?? "GET",
    headers_text: JSON.stringify(row.headers ?? {}, null, 2),
    input_schema_text: JSON.stringify(row.input_schema ?? {}, null, 2),
    output_schema_text: JSON.stringify(row.output_schema ?? {}, null, 2),
    jsonpath_filter: row.jsonpath_filter ?? "",
    query_mapping_text: JSON.stringify(row.query_mapping ?? {}, null, 2),
    header_mapping_text: JSON.stringify(row.header_mapping ?? {}, null, 2),
    timeout_ms: row.timeout_ms ?? undefined,
    token_in: row.token_in ?? "header",
    token_name: row.token_name ?? "",
    enabled: row.enabled !== false,
    system_id: row.system_id,
  };
}

async function detailForForm(id: number) {
  const response = await RestToolAPI.detailTool(id);
  const row = response.data.data;
  return { data: { data: row ? rowToForm(row) : undefined } };
}

const { submitLoading, handleCloseDialog, handleOpenDialog, handleSubmit } = useCrudForm<RestToolForm>({
  formData,
  initialFormData,
  dialogVisible,
  dataFormRef: formRef,
  formRenderKey,
  detailApi: detailForForm,
  createApi: RestToolAPI.createTool,
  updateApi: RestToolAPI.updateTool,
  titles: { create: "新增 REST 工具", update: "修改 REST 工具" },
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
    resetDebug();
    await loadOptions();
    await handleOpenDialog("create");
  } finally {
    createLoading.value = false;
  }
}

async function openEdit(row: RestToolTable) {
  if (!row.id) return;
  resetDebug();
  await loadOptions();
  await handleOpenDialog("update", row.id);
}

async function handleSearch(params: RestToolPageQuery) {
  replaceSearchParams({
    name: params.name,
    system_id: params.system_id,
    request_type: params.request_type,
    enabled: params.enabled,
  });
  await getData();
}

async function onResetSearch() {
  searchForm.value = { name: undefined, system_id: undefined, request_type: undefined, enabled: undefined };
  await resetSearchParams();
}

async function handleDebug() {
  if (!formData.value.system_id) {
    ElMessage.warning("请选择业务系统");
    return;
  }
  if (!debugUserId.value) {
    ElMessage.warning("请选择已绑定该系统的用户");
    return;
  }
  let args: Record<string, unknown> = {};
  try {
    const parsed = JSON.parse((debugArguments.value || "{}").trim()) as unknown;
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("调用参数须为 JSON 对象");
    }
    args = parsed as Record<string, unknown>;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "调用参数须为 JSON 对象");
    return;
  }
  debugLoading.value = true;
  debugResult.value = null;
  try {
    const response = await RestToolAPI.debugTool({
      ...formData.value,
      user_id: debugUserId.value,
      arguments: args,
      reveal: debugReveal.value,
    });
    debugResult.value = response.data.data ?? null;
  } finally {
    debugLoading.value = false;
  }
}

onMounted(() => {
  void loadOptions();
});
</script>

<style scoped>
.rest-debug {
  margin: 0 16px 16px;
  padding: 12px 16px 16px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
}

.rest-debug__title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}

.rest-debug__note {
  margin: 0 0 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.rest-debug__row {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 12px;
  align-items: start;
  margin-bottom: 12px;
}

.rest-debug__user {
  width: 100%;
}

.rest-debug__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.rest-debug__result pre {
  margin: 4px 0 12px;
  padding: 8px;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}
</style>
