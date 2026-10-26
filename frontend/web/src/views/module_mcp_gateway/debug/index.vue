<!-- 管理员 MCP 调试。连接、Tools、Protocol、Network。不提供 stdio / prompts / resources。 -->
<template>
  <div class="mcp-debug flex flex-col gap-4">
    <ElCard shadow="hover">
      <template #header>
        <span class="font-medium">连接</span>
      </template>
      <div class="flex flex-col gap-3">
        <div class="mcp-debug__row">
          <span class="mcp-debug__label">目标</span>
          <ElRadioGroup v-model="target">
            <ElRadioButton value="group">MCP 组</ElRadioButton>
            <ElRadioButton value="upstream">MCP 代理</ElRadioButton>
            <ElRadioButton value="custom">自定义</ElRadioButton>
          </ElRadioGroup>
        </div>

        <template v-if="target === 'group'">
          <div class="mcp-debug__row">
            <span class="mcp-debug__label">MCP 组</span>
            <ElSelect v-model="groupId" filterable clearable placeholder="选择 MCP 组" class="mcp-debug__control">
              <ElOption v-for="item in groups" :key="item.id" :label="item.name" :value="item.id!" />
            </ElSelect>
          </div>
          <div class="mcp-debug__row">
            <span class="mcp-debug__label">业务用户</span>
            <ElSelect v-model="userId" filterable clearable placeholder="选择业务用户" class="mcp-debug__control">
              <ElOption v-for="item in users" :key="item.id" :label="userLabel(item)" :value="item.id!" />
            </ElSelect>
          </div>
          <div class="mcp-debug__row">
            <span class="mcp-debug__label">传输</span>
            <ElRadioGroup v-model="transport">
              <ElRadioButton value="streamable_http">Streamable HTTP</ElRadioButton>
              <ElRadioButton value="sse">SSE</ElRadioButton>
            </ElRadioGroup>
          </div>
        </template>

        <template v-else-if="target === 'upstream'">
          <div class="mcp-debug__row">
            <span class="mcp-debug__label">MCP 代理</span>
            <ElSelect v-model="upstreamId" filterable clearable placeholder="选择上游" class="mcp-debug__control">
              <ElOption
                v-for="item in upstreams"
                :key="item.id"
                :label="upstreamLabel(item)"
                :value="item.id!"
              />
            </ElSelect>
          </div>
        </template>

        <template v-else-if="target === 'custom'">
          <div class="mcp-debug__row">
            <span class="mcp-debug__label">URL</span>
            <ElInput v-model="customUrl" clearable placeholder="https://..." class="mcp-debug__control" />
          </div>
          <div class="mcp-debug__row">
            <span class="mcp-debug__label">传输</span>
            <ElRadioGroup v-model="transport">
              <ElRadioButton value="streamable_http">Streamable HTTP</ElRadioButton>
              <ElRadioButton value="sse">SSE</ElRadioButton>
            </ElRadioGroup>
          </div>
          <div class="mcp-debug__row mcp-debug__headers">
            <span class="mcp-debug__label">Header</span>
            <div class="flex flex-col gap-2 flex-1">
              <div v-for="(row, index) in headerRows" :key="index" class="flex gap-2 items-center flex-wrap">
                <ElInput v-model="row.key" placeholder="名称" class="mcp-debug__header-key" />
                <ElInput v-model="row.value" placeholder="值" class="mcp-debug__header-value" />
                <ElButton text type="danger" @click="headerRows.splice(index, 1)">删除</ElButton>
              </div>
              <ElButton plain @click="headerRows.push({ key: '', value: '' })">添加 Header</ElButton>
            </div>
          </div>
        </template>

        <div class="mcp-debug__actions">
          <ElCheckbox v-model="reveal">显示 token</ElCheckbox>
          <ElButton type="primary" :loading="sessionLoading" @click="handleConnect">连接</ElButton>
        </div>
        <div v-if="serverInfoText" class="mcp-debug__panel">
          <div class="mcp-debug__panel-title">服务器信息</div>
          <pre>{{ serverInfoText }}</pre>
        </div>
      </div>
    </ElCard>

    <ElCard shadow="hover">
      <template #header>
        <div class="flex items-center justify-between gap-2">
          <span class="font-medium">Tools</span>
          <ElButton :loading="listLoading" :disabled="!connected" @click="handleListTools">tools/list</ElButton>
        </div>
      </template>
      <ElEmpty v-if="tools.length === 0" :image-size="64" description="连接后列出工具" />
      <div v-else class="flex flex-col gap-4">
        <ElSelect v-model="selectedTool" filterable placeholder="选择工具" class="mcp-debug__control">
          <ElOption v-for="tool in tools" :key="tool.name" :label="tool.name" :value="tool.name" />
        </ElSelect>
        <div v-if="selectedToolMeta?.description" class="text-sm text-[var(--el-text-color-secondary)]">
          {{ selectedToolMeta.description }}
        </div>
        <div v-if="selectedToolMeta?.inputSchema">
          <div class="mcp-debug__panel-title">Input Schema</div>
          <pre class="mcp-debug__pre">{{ formatJson(selectedToolMeta.inputSchema) }}</pre>
        </div>
        <div>
          <div class="mcp-debug__panel-title">参数（JSON）</div>
          <ElInput v-model="callArguments" type="textarea" :rows="5" placeholder='例如 {"q": "今天"}' />
        </div>
        <div class="mcp-debug__actions">
          <ElButton type="primary" plain :loading="callLoading" :disabled="!selectedTool" @click="handleCallTool">
            tools/call
          </ElButton>
        </div>
        <div v-if="callResultText !== null" class="mcp-debug__panel">
          <div class="mcp-debug__panel-title">返回</div>
          <pre>{{ callResultText }}</pre>
        </div>
      </div>
    </ElCard>

    <ElCard shadow="hover">
      <template #header>
        <span class="font-medium">Protocol</span>
      </template>
      <ElEmpty v-if="!protocol" :image-size="64" description="暂无 JSON-RPC 记录" />
      <div v-else class="grid gap-4 md:grid-cols-2">
        <div class="mcp-debug__panel">
          <div class="mcp-debug__panel-title">请求</div>
          <pre>{{ protocol.request }}</pre>
        </div>
        <div class="mcp-debug__panel">
          <div class="mcp-debug__panel-title">响应</div>
          <pre>{{ protocol.response }}</pre>
        </div>
      </div>
    </ElCard>

    <ElCard shadow="hover">
      <template #header>
        <span class="font-medium">Network</span>
      </template>
      <ElEmpty v-if="!network" :image-size="64" description="暂无 HTTP 记录" />
      <div v-else class="flex flex-col gap-3">
        <div>HTTP 状态：{{ network.status }}</div>
        <div class="mcp-debug__panel">
          <div class="mcp-debug__panel-title">请求头</div>
          <pre>{{ network.request_headers }}</pre>
        </div>
        <div class="mcp-debug__panel">
          <div class="mcp-debug__panel-title">响应体</div>
          <pre>{{ network.response_body }}</pre>
        </div>
      </div>
    </ElCard>
  </div>
</template>

<script lang="ts" setup>
import McpDebugAPI, {
  type McpDebugNetwork,
  type McpDebugProtocol,
  type McpDebugTarget,
  type McpDebugTargetKind,
  type McpDebugTool,
  type McpDebugTransport,
} from "@/api/module_mcp_gateway/debug";
import McpGroupAPI, { type McpGroupTable } from "@/api/module_mcp_gateway/mcp_group";
import UpstreamAPI, { type UpstreamTable } from "@/api/module_mcp_gateway/upstream";
import BizUserAPI, { type BizUserTable } from "@/api/module_mcp_gateway/user";
import { ElMessage } from "element-plus";

defineOptions({ name: "McpGatewayDebug" });

const target = ref<McpDebugTargetKind>("group");
const groupId = ref<number | undefined>();
const userId = ref<number | undefined>();
const upstreamId = ref<number | undefined>();
const transport = ref<McpDebugTransport>("streamable_http");
const reveal = ref(false);
const customUrl = ref("");
const headerRows = ref<{ key: string; value: string }[]>([{ key: "", value: "" }]);

const groups = ref<McpGroupTable[]>([]);
const users = ref<BizUserTable[]>([]);
const upstreams = ref<UpstreamTable[]>([]);

const connected = ref(false);
const sessionLoading = ref(false);
const listLoading = ref(false);
const callLoading = ref(false);

const serverInfoText = ref("");
const tools = ref<McpDebugTool[]>([]);
const selectedTool = ref<string>();
const callArguments = ref("{}");
const callResultText = ref<string | null>(null);
const protocol = ref<McpDebugProtocol | null>(null);
const network = ref<McpDebugNetwork | null>(null);

const selectedToolMeta = computed(() => tools.value.find((item) => item.name === selectedTool.value));

function userLabel(item: BizUserTable) {
  if (item.nickname) return `${item.name}（${item.nickname}）`;
  return item.name ?? String(item.id);
}

function upstreamLabel(item: UpstreamTable) {
  const title = item.name && item.code ? `${item.name}（${item.code}）` : (item.name || item.code || String(item.id));
  return item.url ? `${title} · ${item.url}` : title;
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function buildCustomHeaders(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const row of headerRows.value) {
    const key = row.key.trim();
    if (!key) continue;
    out[key] = row.value;
  }
  return out;
}

function buildTarget(): McpDebugTarget | null {
  if (target.value === "group") {
    if (!groupId.value || !userId.value) {
      ElMessage.warning("请选择 MCP 组和业务用户");
      return null;
    }
    return {
      target: "group",
      group_id: groupId.value,
      user_id: userId.value,
      transport: transport.value,
      reveal: reveal.value,
    };
  }
  if (target.value === "upstream") {
    if (!upstreamId.value) {
      ElMessage.warning("请选择MCP 代理");
      return null;
    }
    return {
      target: "upstream",
      upstream_id: upstreamId.value,
      reveal: reveal.value,
    };
  }
  if (!customUrl.value.trim()) {
    ElMessage.warning("请填写 MCP URL");
    return null;
  }
  return {
    target: "custom",
    url: customUrl.value.trim(),
    headers: buildCustomHeaders(),
    transport: transport.value,
    reveal: reveal.value,
  };
}

function applyViews(nextProtocol?: McpDebugProtocol, nextNetwork?: McpDebugNetwork) {
  protocol.value = nextProtocol ?? null;
  network.value = nextNetwork ?? null;
}

async function loadOptions() {
  const [groupResp, userResp, upstreamResp] = await Promise.all([
    McpGroupAPI.listGroup({ page_no: 1, page_size: 100 }),
    BizUserAPI.listUser({ page_no: 1, page_size: 100 }),
    UpstreamAPI.listUpstream({ page_no: 1, page_size: 100 }),
  ]);
  groups.value = groupResp.data.data?.items ?? [];
  users.value = userResp.data.data?.items ?? [];
  upstreams.value = upstreamResp.data.data?.items ?? [];
}

async function handleConnect() {
  const body = buildTarget();
  if (!body) return;
  sessionLoading.value = true;
  try {
    const res = await McpDebugAPI.session(body);
    const data = res.data.data;
    connected.value = true;
    serverInfoText.value = formatJson(data?.server_info ?? {});
    applyViews(data?.protocol, data?.network);
    tools.value = [];
    selectedTool.value = undefined;
    callResultText.value = null;
    ElMessage.success("已连接");
  } catch {
    connected.value = false;
  } finally {
    sessionLoading.value = false;
  }
}

async function handleListTools() {
  const body = buildTarget();
  if (!body) return;
  listLoading.value = true;
  try {
    const res = await McpDebugAPI.toolsList(body);
    const data = res.data.data;
    tools.value = Array.isArray(data?.tools) ? data.tools : [];
    selectedTool.value = tools.value[0]?.name;
    applyViews(data?.protocol, data?.network);
    callResultText.value = null;
  } finally {
    listLoading.value = false;
  }
}

async function handleCallTool() {
  const body = buildTarget();
  if (!body || !selectedTool.value) return;
  let argumentsPayload: Record<string, unknown> = {};
  try {
    const parsed = JSON.parse(callArguments.value || "{}");
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      ElMessage.warning("参数必须是 JSON 对象");
      return;
    }
    argumentsPayload = parsed as Record<string, unknown>;
  } catch {
    ElMessage.warning("参数不是合法 JSON");
    return;
  }
  callLoading.value = true;
  try {
    const res = await McpDebugAPI.toolsCall({
      ...body,
      name: selectedTool.value,
      arguments: argumentsPayload,
    });
    const data = res.data.data;
    callResultText.value = data?.result_text ?? "";
    applyViews(data?.protocol, data?.network);
  } finally {
    callLoading.value = false;
  }
}

watch(target, () => {
  connected.value = false;
  serverInfoText.value = "";
  tools.value = [];
  selectedTool.value = undefined;
  callResultText.value = null;
  protocol.value = null;
  network.value = null;
});

onMounted(loadOptions);
</script>

<style scoped>
/* fa-page-view 会把本页压成 flex-1 + min-h-0；卡片默认可收缩且 overflow:hidden，会把连接/Tools 挤没 */
.mcp-debug {
  overflow: auto;
}

.mcp-debug > :deep(.el-card) {
  flex-shrink: 0;
}

.mcp-debug__row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.mcp-debug__label {
  width: 88px;
  flex-shrink: 0;
  color: var(--el-text-color-regular);
}

.mcp-debug__control {
  min-width: 280px;
  max-width: 480px;
}

.mcp-debug__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.mcp-debug__panel {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 12px;
  background: var(--el-fill-color-blank);
}

.mcp-debug__panel-title {
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.mcp-debug__panel pre,
.mcp-debug__pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}

.mcp-debug__header-key {
  min-width: 140px;
  max-width: 200px;
}

.mcp-debug__header-value {
  min-width: 200px;
  max-width: 360px;
}
</style>
