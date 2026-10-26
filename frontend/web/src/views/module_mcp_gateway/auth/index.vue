<!-- 业务鉴权：一个系统同时只启用一条。选择方法后展示时序图和说明。 -->
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
            :perm-create="['module_mcp_gateway:biz-auth:create']"
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
      width="960px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      :form-mode="dialogVisible.type"
      :confirm-loading="submitLoading"
      @cancel="handleCloseDialog"
      @close="handleCloseDialog"
      @confirm="handleSubmit()"
    >
      <p class="auth-note">同一业务系统同时只启用一条鉴权。保存为启用时，该系统其余配置会改为未启用。</p>
      <PlaceholderHelp
        :title="AUTH_PLACEHOLDER_HELP.title"
        :intro="AUTH_PLACEHOLDER_HELP.intro"
        :variables="AUTH_PLACEHOLDER_HELP.variables"
        :usage="AUTH_PLACEHOLDER_HELP.usage"
        :examples="AUTH_PLACEHOLDER_HELP.examples"
      />
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
      >
        <template #headers_rows>
          <KeyValueRows v-model="headerRows" add-label="添加 Header" />
        </template>
        <template #query_rows>
          <KeyValueRows v-model="queryRows" add-label="添加 Query" />
        </template>
        <template #body_form_rows>
          <KeyValueRows v-model="formBodyRows" add-label="添加字段" />
        </template>
        <template #captures_rows>
          <CaptureRows v-model="captureRows" add-label="添加变量" />
        </template>
      </FaForm>
      <section v-if="guide" class="auth-guide">
        <h3 class="auth-guide__title">{{ guide.title }}</h3>
        <div class="auth-seq" :style="{ '--actors': String(guide.actors.length) }">
          <div class="auth-seq__head">
            <div v-for="actor in guide.actors" :key="actor" class="auth-seq__actor">{{ actor }}</div>
          </div>
          <div class="auth-seq__canvas">
            <div class="auth-seq__lifelines" aria-hidden="true">
              <span v-for="actor in guide.actors" :key="`${actor}-line`" />
            </div>
            <div v-for="(message, index) in guide.messages" :key="index" class="auth-seq__row">
              <div class="auth-seq__msg" :style="messageStyle(guide.actors, message)">
                <span class="auth-seq__label">{{ message.text }}</span>
                <i class="auth-seq__arrow" :class="{ 'is-back': isReturn(guide.actors, message) }" />
              </div>
            </div>
          </div>
        </div>
        <ul class="auth-guide__facts">
          <li><span>适用</span>{{ guide.when }}</li>
          <li><span>要填的项</span>{{ guide.fills }}</li>
          <li><span>何时拿到 token</span>{{ guide.tokenWhen }}</li>
          <li><span>用户是否打开页面</span>{{ guide.opensPage }}</li>
          <li><span>失败时用户看到</span>{{ guide.onFailure }}</li>
        </ul>
        <p class="auth-note">
          custom 用上方「捕获变量」从表单配置多字段；取值规则 JSON 还可写 expires_seconds，或
          expires_from / expires_name / expires_unit。其它方法仍用 token_from / token_name（header、json、form、text、regex）。
        </p>
      </section>
      <p v-else class="auth-note">选择鉴权方法后，这里显示该方法的时序图和说明。</p>
    </FaDialog>
  </div>
</template>

<script setup lang="ts">
import BizAuthAPI, {
  recordToRows,
  rowsToRecord,
  type BizAuthBodyType,
  type BizAuthForm,
  type BizAuthMethod,
  type BizAuthPageQuery,
  type BizAuthTable,
} from "@/api/module_mcp_gateway/auth";
import BizSystemAPI, { type BizSystemTable } from "@/api/module_mcp_gateway/system";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { renderTableOperationCell, type TableOperationAction } from "@utils";
import CaptureRows, { type CaptureRow } from "../components/CaptureRows.vue";
import KeyValueRows, { type KvRow } from "../components/KeyValueRows.vue";
import PlaceholderHelp from "../components/PlaceholderHelp.vue";
import { AUTH_PLACEHOLDER_HELP } from "../components/placeholderHelpContent";

defineOptions({
  name: "McpGatewayBizAuth",
  inheritAttrs: false,
});

const ENABLED_OPTIONS = [
  { label: "启用", value: true },
  { label: "停用", value: false },
] as const;

const METHOD_OPTIONS = [
  { label: "固定 POST 用户标识", value: "fixed" },
  { label: "自定义请求", value: "custom" },
  { label: "系统 Basic 认证", value: "basic" },
  { label: "交互式验证链接", value: "interactive" },
] as const;

const HTTP_METHOD_OPTIONS = ["GET", "POST", "PUT", "PATCH", "DELETE"].map((value) => ({ label: value, value }));

const RULE_PLACEHOLDER = `{
  "token_from": "json",
  "token_name": "access_token",
  "expires_from": "json",
  "expires_name": "expires_in",
  "expires_unit": "seconds",
  "expires_seconds": 3600
}`;

interface SequenceMessage {
  from: string;
  to: string;
  text: string;
}

interface AuthGuide {
  title: string;
  actors: string[];
  messages: SequenceMessage[];
  when: string;
  fills: string;
  tokenWhen: string;
  opensPage: string;
  onFailure: string;
}

const CACHED_ACTORS = ["MCP 客户端", "本系统", "Redis", "OA"];

const AUTH_GUIDES: Record<BizAuthMethod, AuthGuide> = {
  fixed: {
    title: "固定 POST 用户标识",
    actors: CACHED_ACTORS,
    messages: [
      { from: "MCP 客户端", to: "本系统", text: "调用工具" },
      { from: "本系统", to: "Redis", text: "查询 token" },
      { from: "Redis", to: "本系统", text: "未命中" },
      { from: "本系统", to: "OA", text: "POST 该用户的 uid" },
      { from: "OA", to: "本系统", text: "返回登录响应" },
      { from: "本系统", to: "Redis", text: "写入 token" },
      { from: "本系统", to: "MCP 客户端", text: "返回工具结果" },
    ],
    when: "OA 用固定接口登录。请求是 POST JSON，字段名等于业务系统的用户标识字段，值等于该用户在这个系统上的绑定标识。",
    fills: "业务系统、登录地址、取值规则。HTTP 方法固定为 POST，不用填账号。",
    tokenWhen: "MCP 客户端调用工具且 Redis 没有可用 token 时，本系统向 OA 发这次 POST，从响应取出 token 后写入 Redis。",
    opensPage: "不需要。用户不用打开页面。",
    onFailure: "MCP 客户端里这次调用失败，Redis 里没有新 token。",
  },
  custom: {
    title: "自定义请求",
    actors: CACHED_ACTORS,
    messages: [
      { from: "MCP 客户端", to: "本系统", text: "调用工具" },
      { from: "本系统", to: "Redis", text: "查询 token" },
      { from: "Redis", to: "本系统", text: "未命中" },
      { from: "本系统", to: "OA", text: "按配置发送自定义请求" },
      { from: "OA", to: "本系统", text: "返回登录响应" },
      { from: "本系统", to: "Redis", text: "写入 token" },
      { from: "本系统", to: "MCP 客户端", text: "返回工具结果" },
    ],
    when: "OA 登录不是固定的 uid POST，而是管理员配置的 HTTP 请求，参数可放在 Header、Query、JSON 或 Form。",
    fills: "业务系统、请求地址、HTTP 方法、请求头、Query、Body 类型与 Body、取值规则。",
    tokenWhen: "缓存未命中时，本系统按配置请求 OA，从响应取出 token 并写入 Redis。",
    opensPage: "不需要。用户不用打开页面。",
    onFailure: "MCP 客户端看到调用失败，没有写入 token。",
  },
  basic: {
    title: "系统 Basic 认证",
    actors: CACHED_ACTORS,
    messages: [
      { from: "MCP 客户端", to: "本系统", text: "调用工具" },
      { from: "本系统", to: "Redis", text: "查询 token" },
      { from: "Redis", to: "本系统", text: "未命中" },
      { from: "本系统", to: "OA", text: "使用系统账号做 Basic 认证" },
      { from: "OA", to: "本系统", text: "返回登录响应" },
      { from: "本系统", to: "Redis", text: "写入 token" },
      { from: "本系统", to: "MCP 客户端", text: "返回工具结果" },
    ],
    when: "OA 使用一套属于业务系统的账号密码做 Basic 认证，不按每个用户分别登录。",
    fills: "业务系统、请求地址、HTTP 方法、用户名、密码、取值规则。账号密码记在这条鉴权配置上，不记在业务用户上。",
    tokenWhen: "缓存未命中时，本系统带上这套账号密码请求 OA，从响应取出 token 并写入 Redis。",
    opensPage: "不需要。用户不用打开页面。",
    onFailure: "MCP 客户端看到调用失败，没有可用 token。",
  },
  interactive: {
    title: "交互式验证链接",
    actors: ["MCP 客户端", "浏览器", "本系统", "OA", "Redis"],
    messages: [
      { from: "MCP 客户端", to: "本系统", text: "调用工具" },
      { from: "本系统", to: "Redis", text: "查询 token" },
      { from: "Redis", to: "本系统", text: "未命中" },
      { from: "本系统", to: "MCP 客户端", text: "返回验证链接" },
      { from: "浏览器", to: "本系统", text: "打开验证链接" },
      { from: "浏览器", to: "OA", text: "用户完成验证" },
      { from: "OA", to: "本系统", text: "回调" },
      { from: "本系统", to: "Redis", text: "写入 token" },
      { from: "本系统", to: "浏览器", text: "显示验证结果" },
    ],
    when: "OA 必须由用户本人在页面上完成验证，本系统不能代替用户登录。",
    fills: "业务系统、OA 验证地址、取值规则。不填系统账号。",
    tokenWhen: "调用时如果 Redis 没有 token，本系统先返回验证链接，这时还没有 token。用户在浏览器完成验证且回调成功后，本系统按取值规则取出 token 并写入 Redis。",
    opensPage: "需要。用户要在浏览器打开验证链接。",
    onFailure: "浏览器里看到验证失败。MCP 客户端得到一条新的验证链接，响应里没有业务 token，也不会自动重试登录。",
  },
};

function enabledText(enabled?: boolean) {
  return enabled === false ? "停用" : "启用";
}

function methodText(method?: string) {
  return METHOD_OPTIONS.find((item) => item.value === method)?.label ?? method ?? "";
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

function messageStyle(actors: string[], message: SequenceMessage) {
  const from = actors.indexOf(message.from);
  const to = actors.indexOf(message.to);
  const start = Math.min(from, to);
  const end = Math.max(from, to);
  return {
    gridColumn: `${start + 1} / ${end + 2}`,
    "--span": String(end - start + 1),
  };
}

function isReturn(actors: string[], message: SequenceMessage) {
  return actors.indexOf(message.from) > actors.indexOf(message.to);
}

const systems = ref<BizSystemTable[]>([]);
const systemOptions = computed(() =>
  systems.value.filter((item) => item.id).map((item) => ({
    label: item.code ? `${item.name}（${item.code}）` : (item.name ?? String(item.id)),
    value: item.id,
  })),
);

async function loadSystems() {
  const response = await BizSystemAPI.listSystem({ page_no: 1, page_size: 100 });
  systems.value = response.data.data?.items ?? [];
}

function systemLabel(systemId?: number) {
  return systemOptions.value.find((item) => item.value === systemId)?.label ?? (systemId ? String(systemId) : "");
}

const showSearch = ref(true);
const searchForm = ref<BizAuthPageQuery>({ system_id: undefined, method: undefined, enabled: undefined });
const searchBarRef = ref();
const searchItems = computed<SearchFormItem[]>(() => [
  {
    label: "业务系统",
    key: "system_id",
    type: "select",
    props: { placeholder: "请选择", options: systemOptions.value, clearable: true, filterable: true },
    span: 6,
  },
  {
    label: "方法",
    key: "method",
    type: "select",
    props: { placeholder: "请选择", options: METHOD_OPTIONS, clearable: true },
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

function rowActions(row: BizAuthTable): TableOperationAction[] {
  return [
    {
      key: "edit",
      label: "编辑",
      artType: "edit",
      perm: "module_mcp_gateway:biz-auth:update",
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
    apiFn: BizAuthAPI.listAuth,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      {
        prop: "system_id",
        label: "业务系统",
        minWidth: 160,
        showOverflowTooltip: true,
        formatter: (row: BizAuthTable) => systemLabel(row.system_id),
      },
      {
        prop: "method",
        label: "方法",
        minWidth: 150,
        showOverflowTooltip: true,
        formatter: (row: BizAuthTable) => methodText(row.method),
      },
      { prop: "url", label: "地址", minWidth: 200, showOverflowTooltip: true },
      { prop: "http_method", label: "HTTP 方法", width: 110, showOverflowTooltip: true },
      {
        prop: "enabled",
        label: "启用",
        width: 88,
        formatter: (row: BizAuthTable) => enabledText(row.enabled),
      },
      { prop: "created_time", label: "创建时间", width: 168, showOverflowTooltip: true },
      {
        prop: "operation",
        label: "操作",
        width: 100,
        fixed: "right",
        align: "center",
        formatter: (row: BizAuthTable) =>
          renderTableOperationCell(rowActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

const BODY_TYPE_OPTIONS = [
  { label: "无", value: "none" },
  { label: "JSON", value: "json" },
  { label: "Form", value: "form" },
] as const;

function createInitialForm(): BizAuthForm {
  return {
    id: undefined,
    system_id: undefined,
    method: undefined,
    url: "",
    http_method: undefined,
    username: "",
    password: "",
    rule_text: RULE_PLACEHOLDER,
    enabled: true,
    headers: {},
    query: {},
    body_type: "none",
    body: null,
    body_text: "{}",
  };
}

const formData = ref<BizAuthForm>(createInitialForm());
const initialFormData = createInitialForm();
const headerRows = ref<KvRow[]>([{ key: "", value: "" }]);
const queryRows = ref<KvRow[]>([{ key: "", value: "" }]);
const formBodyRows = ref<KvRow[]>([{ key: "", value: "" }]);
const captureRows = ref<CaptureRow[]>([{ name: "access_token", from: "json", path: "" }]);
const { dialogVisible } = useCrudDialog();
const formRef = ref<InstanceType<typeof FaForm> | null>(null);
const formRenderKey = ref(0);
const guide = computed(() => (formData.value.method ? AUTH_GUIDES[formData.value.method] : undefined));

function emptyCaptureRows(): CaptureRow[] {
  return [{ name: "access_token", from: "json", path: "" }];
}

function capturesFromRule(rule: Record<string, unknown> | undefined | null): CaptureRow[] {
  const raw = rule?.captures;
  if (Array.isArray(raw) && raw.length) {
    return raw.map((item) => {
      const row = item as Record<string, unknown>;
      return {
        name: String(row.name ?? ""),
        from: String(row.from ?? "json"),
        path: String(row.path ?? ""),
      };
    });
  }
  const from = rule?.token_from;
  if (typeof from === "string" && from) {
    return [
      {
        name: "access_token",
        from,
        path: typeof rule?.token_name === "string" ? rule.token_name : "",
      },
    ];
  }
  return emptyCaptureRows();
}

function resetCustomRequestEditors() {
  headerRows.value = [{ key: "", value: "" }];
  queryRows.value = [{ key: "", value: "" }];
  formBodyRows.value = [{ key: "", value: "" }];
  captureRows.value = emptyCaptureRows();
  formData.value.headers = {};
  formData.value.query = {};
  formData.value.body_type = "none";
  formData.value.body = null;
  formData.value.body_text = "{}";
}

watch(
  () => formData.value.method,
  (method, prev) => {
    if (method === "custom" && prev !== "custom") {
      if (!formData.value.body_type) formData.value.body_type = "none";
    }
    if (prev === "custom" && method !== "custom") {
      resetCustomRequestEditors();
    }
  },
);

function syncCapturesIntoRuleText() {
  if (formData.value.method !== "custom") return;
  const raw = (formData.value.rule_text ?? "").trim() || "{}";
  const parsed = JSON.parse(raw) as unknown;
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("取值规则须为 JSON 对象");
  }
  const rule = parsed as Record<string, unknown>;
  const captures = captureRows.value
    .map((row) => ({
      name: row.name.trim(),
      from: row.from.trim(),
      path: row.path.trim(),
    }))
    .filter((row) => row.name);
  if (!captures.length) {
    throw new Error("请至少配置一条捕获变量");
  }
  rule.captures = captures;
  delete rule.token_from;
  delete rule.token_name;
  formData.value.rule_text = JSON.stringify(rule, null, 2);
}

function syncCustomRequestToForm() {
  if (formData.value.method !== "custom") return;
  formData.value.headers = rowsToRecord(headerRows.value);
  formData.value.query = rowsToRecord(queryRows.value);
  syncCapturesIntoRuleText();
  const bodyType = (formData.value.body_type ?? "none") as BizAuthBodyType;
  formData.value.body_type = bodyType;
  if (bodyType === "none") {
    formData.value.body = null;
    return;
  }
  if (bodyType === "form") {
    formData.value.body = rowsToRecord(formBodyRows.value);
    return;
  }
  const raw = (formData.value.body_text ?? "").trim() || "{}";
  const parsed = JSON.parse(raw) as unknown;
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Body 须为 JSON 对象");
  }
  formData.value.body = parsed as Record<string, unknown>;
}

const rules = reactive({
  system_id: [{ required: true, message: "请选择业务系统", trigger: "change" }],
  method: [{ required: true, message: "请选择鉴权方法", trigger: "change" }],
  url: [{ required: true, message: "请输入地址", trigger: "blur" }],
  http_method: [
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if ((formData.value.method === "custom" || formData.value.method === "basic") && !value) {
          callback(new Error("请选择 HTTP 方法"));
          return;
        }
        callback();
      },
      trigger: "change",
    },
  ],
  body_type: [
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (formData.value.method === "custom" && !value) {
          callback(new Error("请选择 Body 类型"));
          return;
        }
        callback();
      },
      trigger: "change",
    },
  ],
  body_text: [
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (formData.value.method !== "custom" || formData.value.body_type !== "json") {
          callback();
          return;
        }
        try {
          const parsed = JSON.parse((value ?? "").trim() || "{}") as unknown;
          if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
            callback(new Error("Body 须为 JSON 对象"));
            return;
          }
          callback();
        } catch {
          callback(new Error("Body 须为合法 JSON"));
        }
      },
      trigger: "blur",
    },
  ],
  username: [
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (formData.value.method === "basic" && !(value ?? "").trim()) {
          callback(new Error("请输入 Basic 用户名"));
          return;
        }
        callback();
      },
      trigger: "blur",
    },
  ],
  password: [
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (formData.value.method === "basic" && !value) {
          callback(new Error("请输入 Basic 密码"));
          return;
        }
        callback();
      },
      trigger: "blur",
    },
  ],
  rule_text: [jsonObjectRule("取值规则须为 JSON 对象")],
});

const dialogFormItems = computed<FormItem[]>(() => {
  const items: FormItem[] = [
    {
      label: "业务系统",
      key: "system_id",
      type: "select",
      span: 24,
      props: { placeholder: "请选择业务系统", options: systemOptions.value, filterable: true },
    },
    {
      label: "鉴权方法",
      key: "method",
      type: "select",
      span: 24,
      props: { placeholder: "请选择鉴权方法", options: METHOD_OPTIONS },
    },
    {
      label: "地址",
      key: "url",
      type: "input",
      span: 24,
      props: { placeholder: "https://oa.example.com/login 或 /login", maxlength: 512 },
    },
  ];
  if (formData.value.method === "custom" || formData.value.method === "basic") {
    items.push({
      label: "HTTP 方法",
      key: "http_method",
      type: "select",
      span: 24,
      props: { placeholder: "请选择 HTTP 方法", options: HTTP_METHOD_OPTIONS },
    });
  }
  if (formData.value.method === "custom") {
    items.push(
      { label: "请求头", key: "headers_rows", type: "input", span: 24 },
      { label: "Query 参数", key: "query_rows", type: "input", span: 24 },
      {
        label: "Body 类型",
        key: "body_type",
        type: "select",
        span: 24,
        props: { placeholder: "请选择 Body 类型", options: [...BODY_TYPE_OPTIONS] },
      },
    );
    if (formData.value.body_type === "json") {
      items.push({
        label: "Body",
        key: "body_text",
        type: "input",
        span: 24,
        props: { type: "textarea", rows: 6, placeholder: '{\n  "uid": "{{user.uid}}"\n}' },
      });
    } else if (formData.value.body_type === "form") {
      items.push({ label: "Body", key: "body_form_rows", type: "input", span: 24 });
    }
    items.push({ label: "捕获变量", key: "captures_rows", type: "input", span: 24 });
  }
  if (formData.value.method === "basic") {
    items.push(
      { label: "用户名", key: "username", type: "input", span: 24, props: { placeholder: "系统账号", maxlength: 128 } },
      {
        label: "密码",
        key: "password",
        type: "input",
        span: 24,
        props: { type: "password", showPassword: true, placeholder: "系统密码", maxlength: 512 },
      },
    );
  }
  items.push(
    {
      label: "取值规则",
      key: "rule_text",
      type: "input",
      span: 24,
      props: { type: "textarea", rows: 8, placeholder: RULE_PLACEHOLDER },
    },
    { label: "启用", key: "enabled", type: "switch", span: 24 },
  );
  return items;
});

async function detailForForm(id: number) {
  const response = await BizAuthAPI.detailAuth(id);
  const row = response.data.data;
  if (!row) return { data: { data: undefined } };
  const bodyType = (row.body_type ?? "none") as BizAuthBodyType;
  headerRows.value = recordToRows(row.headers);
  queryRows.value = recordToRows(row.query);
  formBodyRows.value = bodyType === "form" ? recordToRows(row.body as Record<string, string> | null) : [{ key: "", value: "" }];
  captureRows.value = row.method === "custom" ? capturesFromRule(row.rule) : emptyCaptureRows();
  const data: BizAuthForm = {
    id: row.id,
    system_id: row.system_id,
    method: row.method,
    url: row.url ?? "",
    http_method: row.http_method,
    username: row.username ?? "",
    password: row.password ?? "",
    rule_text: JSON.stringify(row.rule ?? {}, null, 2),
    enabled: row.enabled !== false,
    headers: row.headers ?? {},
    query: row.query ?? {},
    body_type: row.method === "custom" ? bodyType : "none",
    body: row.body ?? null,
    body_text: JSON.stringify(row.body ?? {}, null, 2),
  };
  return { data: { data } };
}

async function openEdit(row: BizAuthTable) {
  if (!row.id) return;
  await loadSystems();
  await handleOpenDialog("update", row.id);
}

async function createAuthWithShape(form: BizAuthForm) {
  syncCustomRequestToForm();
  return BizAuthAPI.createAuth(form);
}

async function updateAuthWithShape(id: number, form: BizAuthForm) {
  syncCustomRequestToForm();
  return BizAuthAPI.updateAuth(id, form);
}

const {
  submitLoading,
  handleCloseDialog: closeCrudDialog,
  handleOpenDialog,
  handleSubmit,
} = useCrudForm<BizAuthForm>({
  formData,
  initialFormData,
  dialogVisible,
  dataFormRef: formRef,
  formRenderKey,
  detailApi: detailForForm,
  createApi: createAuthWithShape,
  updateApi: updateAuthWithShape,
  titles: { create: "新增鉴权", update: "修改鉴权" },
  onCreateSuccess: async () => {
    await refreshCreate();
  },
  onUpdateSuccess: async () => {
    await refreshUpdate();
  },
});

async function handleCloseDialog() {
  await closeCrudDialog();
  resetCustomRequestEditors();
}

async function handleAdd() {
  createLoading.value = true;
  try {
    await loadSystems();
    resetCustomRequestEditors();
    await handleOpenDialog("create");
  } finally {
    createLoading.value = false;
  }
}

async function handleSearch(params: BizAuthPageQuery) {
  replaceSearchParams({ system_id: params.system_id, method: params.method, enabled: params.enabled });
  await getData();
}

async function onResetSearch() {
  searchForm.value = { system_id: undefined, method: undefined, enabled: undefined };
  await resetSearchParams();
}

onMounted(() => {
  void loadSystems();
});
</script>

<style scoped>
.auth-note {
  margin: 0 16px 12px;
  color: var(--el-text-color-secondary, #909399);
  font-size: 13px;
  line-height: 1.6;
}

.auth-guide {
  margin: 0 16px 16px;
  padding: 12px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 8px;
}

.auth-guide__title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
}

.auth-seq__head,
.auth-seq__row,
.auth-seq__lifelines {
  display: grid;
  grid-template-columns: repeat(var(--actors), minmax(0, 1fr));
}

.auth-seq__actor {
  margin: 0 4px;
  padding: 6px 4px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 6px;
  background: var(--el-fill-color-light, #f5f7fa);
  text-align: center;
  font-size: 13px;
  font-weight: 600;
}

.auth-seq__canvas {
  position: relative;
  margin-top: 8px;
}

.auth-seq__lifelines {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.auth-seq__lifelines span {
  height: 100%;
  justify-self: center;
  border-left: 1px dashed var(--el-border-color, #dcdfe6);
}

.auth-seq__row {
  position: relative;
  z-index: 1;
  min-height: 40px;
  align-items: end;
}

.auth-seq__label {
  display: block;
  margin-bottom: 2px;
  padding: 0 4px;
  color: var(--el-text-color-regular, #606266);
  font-size: 12px;
  font-style: normal;
  line-height: 16px;
  text-align: center;
}

.auth-seq__arrow {
  display: block;
  position: relative;
  margin: 0 calc(100% / var(--span) / 2);
  border-top: 2px solid var(--el-color-primary, #409eff);
}

.auth-seq__arrow::after {
  content: "";
  position: absolute;
  top: -5px;
  right: -1px;
  border-style: solid;
  border-width: 5px 0 5px 7px;
  border-color: transparent transparent transparent var(--el-color-primary, #409eff);
}

.auth-seq__arrow.is-back::after {
  right: auto;
  left: -1px;
  border-width: 5px 7px 5px 0;
  border-color: transparent var(--el-color-primary, #409eff) transparent transparent;
}

.auth-guide__facts {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.auth-guide__facts li {
  display: grid;
  grid-template-columns: 128px 1fr;
  gap: 8px;
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.6;
}

.auth-guide__facts span {
  color: var(--el-text-color-secondary, #909399);
}

.auth-guide .auth-note {
  margin: 12px 0 0;
}
</style>
