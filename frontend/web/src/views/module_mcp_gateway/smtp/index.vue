<!-- SMTP 配置。密码只写不回显。测试信和三维发信都从这里发出。 -->
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
            :perm-create="['module_mcp_gateway:smtp:create']"
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
      v-model="testVisible"
      title="测试发信"
      width="480px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="create"
      :confirm-loading="testLoading"
      @cancel="testVisible = false"
      @close="testVisible = false"
      @confirm="submitTest"
    >
      <FaForm
        ref="testFormRef"
        v-model="testForm"
        :items="testItems"
        :rules="testRules"
        label-suffix=":"
        :label-width="100"
        label-position="right"
        :span="24"
        :show-reset="false"
        :show-submit="false"
        class="crud-dialog-art-form"
      />
    </FaDialog>

    <FaDialog
      v-model="sendVisible"
      title="发送连接信息"
      width="480px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="create"
      :confirm-loading="sendLoading"
      @cancel="sendVisible = false"
      @close="sendVisible = false"
      @confirm="submitSend"
    >
      <FaForm
        ref="sendFormRef"
        v-model="sendForm"
        :items="sendItems"
        :rules="sendRules"
        label-suffix=":"
        :label-width="120"
        label-position="right"
        :span="24"
        :show-reset="false"
        :show-submit="false"
        class="crud-dialog-art-form"
      />
    </FaDialog>
  </div>
</template>

<script setup lang="ts">
import MailAPI from "@/api/module_mcp_gateway/mail";
import SmtpAPI, { type SmtpForm, type SmtpPageQuery, type SmtpTable } from "@/api/module_mcp_gateway/smtp";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { renderTableOperationCell, type TableOperationAction } from "@utils";

defineOptions({
  name: "McpGatewaySmtp",
  inheritAttrs: false,
});

const ENABLED_OPTIONS = [
  { label: "启用", value: true },
  { label: "停用", value: false },
] as const;

const ENCRYPTION_OPTIONS = [
  { label: "无", value: "none" },
  { label: "STARTTLS", value: "starttls" },
  { label: "SSL", value: "ssl" },
] as const;

const CHANNEL_OPTIONS = [
  { label: "MCP 组", value: "group" },
  { label: "用户组", value: "user_group" },
  { label: "用户", value: "user" },
] as const;

function enabledText(enabled?: boolean) {
  return enabled ? "启用" : "停用";
}

function encryptionText(value?: string) {
  return ENCRYPTION_OPTIONS.find((item) => item.value === value)?.label ?? value ?? "";
}

const showSearch = ref(true);
const searchForm = ref<SmtpPageQuery>({ host: undefined, enabled: undefined });
const searchBarRef = ref();
const searchItems = computed<SearchFormItem[]>(() => [
  { label: "主机", key: "host", type: "input", placeholder: "请输入主机", clearable: true, span: 6 },
  {
    label: "启用",
    key: "enabled",
    type: "select",
    props: { placeholder: "请选择", options: ENABLED_OPTIONS, clearable: true },
    span: 6,
  },
]);

const createLoading = ref(false);

function rowActions(row: SmtpTable): TableOperationAction[] {
  return [
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_mcp_gateway:smtp:update",
      run: () => void openEdit(row),
    },
    {
      key: "test",
      label: "测试",
      artType: "view",
      perm: "module_mcp_gateway:smtp:test",
      run: () => openTest(),
    },
    {
      key: "send",
      label: "发信",
      artType: "view",
      perm: "module_mcp_gateway:smtp:update",
      run: () => openSend(),
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
    apiFn: SmtpAPI.listSmtp,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "host", label: "主机", minWidth: 160, showOverflowTooltip: true },
      { prop: "port", label: "端口", width: 80 },
      { prop: "username", label: "账号", minWidth: 120, showOverflowTooltip: true },
      { prop: "from_address", label: "发件人地址", minWidth: 180, showOverflowTooltip: true },
      { prop: "from_name", label: "发件人名称", minWidth: 120, showOverflowTooltip: true },
      {
        prop: "encryption",
        label: "加密",
        width: 110,
        formatter: (row: SmtpTable) => encryptionText(row.encryption),
      },
      {
        prop: "enabled",
        label: "启用",
        width: 88,
        formatter: (row: SmtpTable) => enabledText(row.enabled),
      },
      { prop: "created_time", label: "创建时间", width: 168, showOverflowTooltip: true },
      {
        prop: "operation",
        label: "操作",
        width: 180,
        fixed: "right",
        align: "center",
        formatter: (row: SmtpTable) =>
          renderTableOperationCell(rowActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

function createInitialForm(): SmtpForm {
  return {
    id: undefined,
    enabled: false,
    host: "",
    port: 587,
    username: "",
    password: "",
    from_address: "",
    from_name: "",
    encryption: "starttls",
  };
}

const formData = ref<SmtpForm>(createInitialForm());
const initialFormData = createInitialForm();
const { dialogVisible } = useCrudDialog();
const formRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);
const rules = reactive({
  host: [{ required: true, message: "请输入主机", trigger: "blur" }],
  port: [{ required: true, message: "请输入端口", trigger: "blur" }],
  from_address: [{ required: true, message: "请输入发件人地址", trigger: "blur" }],
  encryption: [{ required: true, message: "请选择加密方式", trigger: "change" }],
});
const dialogFormItems = computed<FormItem[]>(() => [
  { label: "启用", key: "enabled", type: "switch", span: 24 },
  { label: "主机", key: "host", type: "input", span: 24, props: { placeholder: "smtp.example.com", maxlength: 255 } },
  { label: "端口", key: "port", type: "number", span: 24, props: { min: 1, max: 65535, controlsPosition: "right" } },
  { label: "账号", key: "username", type: "input", span: 24, props: { placeholder: "可留空", maxlength: 128 } },
  {
    label: "密码",
    key: "password",
    type: "input",
    span: 24,
    props: {
      type: "password",
      showPassword: true,
      maxlength: 512,
      placeholder: dialogVisible.type === "update" ? "留空则不修改" : "只写入，保存后不再显示",
    },
  },
  { label: "发件人地址", key: "from_address", type: "input", span: 24, props: { placeholder: "mcp@example.com", maxlength: 255 } },
  { label: "发件人名称", key: "from_name", type: "input", span: 24, props: { placeholder: "可留空", maxlength: 128 } },
  {
    label: "加密方式",
    key: "encryption",
    type: "select",
    span: 24,
    props: { placeholder: "请选择", options: ENCRYPTION_OPTIONS },
  },
]);

async function detailForForm(id: number) {
  const response = await SmtpAPI.detailSmtp(id);
  const row = response.data.data;
  const data: SmtpForm | undefined = row
    ? {
        id: row.id,
        enabled: row.enabled === true,
        host: row.host ?? "",
        port: row.port,
        username: row.username ?? "",
        password: "",
        from_address: row.from_address ?? "",
        from_name: row.from_name ?? "",
        encryption: row.encryption ?? "starttls",
      }
    : undefined;
  return { data: { data } };
}

const { submitLoading, handleCloseDialog, handleOpenDialog, handleSubmit } = useCrudForm<SmtpForm>({
  formData,
  initialFormData,
  dialogVisible,
  dataFormRef: formRef,
  formRenderKey,
  detailApi: detailForForm,
  createApi: SmtpAPI.createSmtp,
  updateApi: SmtpAPI.updateSmtp,
  titles: { create: "新增 SMTP", update: "修改 SMTP" },
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

async function openEdit(row: SmtpTable) {
  if (!row.id) return;
  await handleOpenDialog("update", row.id);
}

async function handleSearch(params: SmtpPageQuery) {
  replaceSearchParams({ host: params.host, enabled: params.enabled });
  await getData();
}

async function onResetSearch() {
  searchForm.value = { host: undefined, enabled: undefined };
  await resetSearchParams();
}

const testVisible = ref(false);
const testLoading = ref(false);
const testFormRef = ref<InstanceType<typeof FaForm> | null>(null);
const testForm = ref({ to_address: "" });
const testRules = reactive({
  to_address: [{ required: true, message: "请输入收件人", trigger: "blur" }],
});
const testItems = computed<FormItem[]>(() => [
  { label: "收件人", key: "to_address", type: "input", span: 24, props: { placeholder: "admin@example.com", maxlength: 255 } },
]);

function openTest() {
  testForm.value = { to_address: "" };
  testVisible.value = true;
}

async function submitTest() {
  const valid = await testFormRef.value?.validate().then(() => true).catch(() => false);
  if (!valid) return;
  testLoading.value = true;
  try {
    await SmtpAPI.testSmtp(testForm.value.to_address);
    testVisible.value = false;
  } finally {
    testLoading.value = false;
  }
}

const sendVisible = ref(false);
const sendLoading = ref(false);
const sendFormRef = ref<InstanceType<typeof FaForm> | null>(null);
const sendForm = ref<{ channel: "group" | "user_group" | "user"; target_id?: number }>({
  channel: "group",
  target_id: undefined,
});
const sendRules = reactive({
  channel: [{ required: true, message: "请选择途径", trigger: "change" }],
  target_id: [{ required: true, message: "请输入编号", trigger: "blur" }],
});
function targetLabel(channel: "group" | "user_group" | "user") {
  if (channel === "user") return "用户编号";
  if (channel === "user_group") return "用户组编号";
  return "MCP 组编号";
}

const sendItems = computed<FormItem[]>(() => [
  {
    label: "途径",
    key: "channel",
    type: "select",
    span: 24,
    props: { placeholder: "请选择", options: CHANNEL_OPTIONS },
  },
  {
    label: targetLabel(sendForm.value.channel),
    key: "target_id",
    type: "number",
    span: 24,
    props: { min: 1, controlsPosition: "right" },
  },
]);

function openSend() {
  sendForm.value = { channel: "group", target_id: undefined };
  sendVisible.value = true;
}

async function submitSend() {
  const valid = await sendFormRef.value?.validate().then(() => true).catch(() => false);
  if (!valid || !sendForm.value.target_id) return;
  sendLoading.value = true;
  try {
    const targetId = sendForm.value.target_id;
    if (sendForm.value.channel === "user") {
      await MailAPI.sendForUser(targetId);
    } else if (sendForm.value.channel === "user_group") {
      await MailAPI.sendForUserGroup(targetId);
    } else {
      await MailAPI.sendForGroup(targetId);
    }
    sendVisible.value = false;
  } finally {
    sendLoading.value = false;
  }
}
</script>
