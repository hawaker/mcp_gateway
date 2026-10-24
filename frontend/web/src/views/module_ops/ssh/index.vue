<!-- SSH 运维：主机/命令片段/批量执行/终端（POST 轮询）与日志跟踪 -->
<template>
  <div class="fa-full-height p-3">
    <ElTabs v-model="activeTab" class="fa-tabs-fill">
      <ElTabPane label="主机管理" name="host">
        <ElCard shadow="hover" class="fa-card">
          <div class="mb-3 flex items-center justify-between">
            <span class="text-[15px] font-medium">SSH 主机（凭据加密存储，出参不含凭据）</span>
            <ElButton type="primary" @click="openHostCreate">新增主机</ElButton>
          </div>
          <ElTable :data="hosts" size="small" empty-text="尚未配置主机">
            <ElTableColumn prop="name" label="名称" min-width="130" />
            <ElTableColumn label="地址" min-width="170">
              <template #default="{ row }">{{ row.host }}:{{ row.port }}</template>
            </ElTableColumn>
            <ElTableColumn prop="username" label="用户" width="110" />
            <ElTableColumn label="认证" width="100">
              <template #default="{ row }">{{
                row.auth_type === "key" ? "私钥" : "密码"
              }}</template>
            </ElTableColumn>
            <ElTableColumn label="状态" width="80">
              <template #default="{ row }">
                <ElTag :type="row.status === 0 ? 'success' : 'info'" size="small">{{
                  row.status === 0 ? "启用" : "停用"
                }}</ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn label="操作" width="230" fixed="right">
              <template #default="{ row }">
                <ElButton link @click="handleHostTest(row)">测试</ElButton>
                <ElButton link type="primary" @click="openHostEdit(row)">编辑</ElButton>
                <ElButton link type="danger" @click="handleHostDelete(row)">删除</ElButton>
              </template>
            </ElTableColumn>
          </ElTable>
        </ElCard>
      </ElTabPane>

      <ElTabPane label="命令片段" name="snippet">
        <ElCard shadow="hover" class="fa-card">
          <div class="mb-3 flex items-center justify-between">
            <span class="text-[15px] font-medium">常用命令</span>
            <ElButton type="primary" @click="openSnippetCreate">新增片段</ElButton>
          </div>
          <ElTable :data="snippets" size="small" empty-text="暂无片段">
            <ElTableColumn prop="name" label="名称" min-width="140" />
            <ElTableColumn prop="command" label="命令" min-width="320" show-overflow-tooltip />
            <ElTableColumn prop="description" label="备注" min-width="160" show-overflow-tooltip />
            <ElTableColumn label="操作" width="170" fixed="right">
              <template #default="{ row }">
                <ElButton link type="primary" @click="applySnippet(row)">填入批量执行</ElButton>
                <ElButton link type="danger" @click="handleSnippetDelete(row)">删除</ElButton>
              </template>
            </ElTableColumn>
          </ElTable>
        </ElCard>
      </ElTabPane>

      <ElTabPane label="批量执行" name="batch">
        <ElCard shadow="hover" class="fa-card">
          <div class="mb-2 flex flex-wrap items-center gap-2">
            <ElSelect
              v-model="batchHostIds"
              multiple
              filterable
              placeholder="选择目标主机（最多 50）"
              style="min-width: 320px"
              collapse-tags
              collapse-tags-tooltip
            >
              <ElOption v-for="h in hosts" :key="h.id" :label="h.name" :value="h.id" />
            </ElSelect>
            <ElButton
              type="primary"
              :loading="batchRunning"
              @click="runBatch"
              :disabled="!batchHostIds.length"
            >
              执行
            </ElButton>
            <span class="text-xs text-[#909399]"
              >命令原样交给远端 shell；执行会写入操作审计日志</span
            >
          </div>
          <ElInput
            v-model="batchCommand"
            type="textarea"
            :rows="4"
            placeholder="例如：uptime && df -h（可先在「命令片段」里维护常用命令）"
          />
          <ElTable
            v-if="batchResults.length"
            :data="batchResults"
            class="mt-3"
            size="small"
            max-height="360"
          >
            <ElTableColumn prop="host_name" label="主机" width="140" />
            <ElTableColumn label="结果" width="90">
              <template #default="{ row }">
                <ElTag :type="row.ok ? 'success' : 'danger'" size="small">{{
                  row.ok ? "成功" : "失败"
                }}</ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="exit_status" label="退出码" width="90" />
            <ElTableColumn label="输出" min-width="360">
              <template #default="{ row }">
                <pre class="m-0 max-h-40 overflow-auto text-xs whitespace-pre-wrap">{{
                  row.stdout || row.stderr || row.error
                }}</pre>
              </template>
            </ElTableColumn>
            <ElTableColumn prop="elapsed_ms" label="耗时(ms)" width="100" />
          </ElTable>
        </ElCard>
      </ElTabPane>

      <ElTabPane label="终端" name="terminal">
        <ElCard shadow="hover" class="fa-card">
          <div class="mb-2 flex flex-wrap items-center gap-2">
            <ElSelect v-model="terminalHostId" placeholder="选择主机" style="width: 180px">
              <ElOption v-for="h in hosts" :key="h.id" :label="h.name" :value="h.id" />
            </ElSelect>
            <ElButton
              type="primary"
              :loading="terminalOpening"
              :disabled="!terminalHostId"
              @click="openTerminal"
            >
              打开终端
            </ElButton>
            <ElButton :disabled="!terminalSessionId" @click="closeTerminal">关闭</ElButton>
            <el-divider direction="vertical" />
            <ElInput
              v-model="logPath"
              placeholder="日志路径，如 /var/log/nginx/error.log"
              style="width: 300px"
            />
            <ElButton
              :loading="terminalOpening"
              :disabled="!terminalHostId || !logPath"
              @click="openLogTail"
            >
              日志跟踪
            </ElButton>
            <span v-if="terminalSession" class="ml-auto text-xs text-[#909399]">
              会话 {{ terminalSession.session_id.slice(0, 8) }} · {{ terminalSession.host_name }}
            </span>
          </div>
          <pre
            ref="terminalRef"
            class="terminal-output m-0 h-[46vh] overflow-auto rounded bg-[#1e1e1e] p-3 text-xs text-[#d4d4d4] whitespace-pre-wrap"
            >{{ terminalOutput || "（打开终端后在此显示输出）" }}</pre
          >
          <div class="mt-2 flex items-center gap-2">
            <ElInput
              v-model="terminalInput"
              placeholder="输入命令后回车（发送到当前终端会话）"
              :disabled="!terminalSessionId"
              @keyup.enter="sendTerminalInput"
            />
            <ElButton :disabled="!terminalSessionId" @click="sendTerminalInput">发送</ElButton>
          </div>
        </ElCard>
      </ElTabPane>
    </ElTabs>

    <ElDialog
      v-model="hostDialogVisible"
      :title="editingHostId ? '编辑主机' : '新增主机'"
      width="620px"
    >
      <ElForm ref="hostFormRef" :model="hostForm" :rules="hostRules" label-width="96px">
        <ElFormItem label="名称" prop="name"><ElInput v-model="hostForm.name" /></ElFormItem>
        <ElFormItem label="地址" prop="host"><ElInput v-model="hostForm.host" /></ElFormItem>
        <ElFormItem label="端口" prop="port">
          <ElInputNumber v-model="hostForm.port" :min="1" :max="65535" />
        </ElFormItem>
        <ElFormItem label="用户名" prop="username"
          ><ElInput v-model="hostForm.username"
        /></ElFormItem>
        <ElFormItem label="认证方式" prop="auth_type">
          <ElRadioGroup v-model="hostForm.auth_type">
            <ElRadio value="password">密码</ElRadio>
            <ElRadio value="key">私钥</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem v-if="hostForm.auth_type === 'password'" label="密码">
          <ElInput
            v-model="hostForm.password"
            type="password"
            show-password
            :placeholder="editingHostId ? '不修改请留空' : ''"
          />
        </ElFormItem>
        <template v-else>
          <ElFormItem label="私钥">
            <ElInput
              v-model="hostForm.private_key"
              type="textarea"
              :rows="6"
              :placeholder="editingHostId ? '不修改请留空' : '-----BEGIN OPENSSH PRIVATE KEY-----'"
            />
          </ElFormItem>
          <ElFormItem label="私钥口令">
            <ElInput
              v-model="hostForm.passphrase"
              type="password"
              show-password
              placeholder="可选"
            />
          </ElFormItem>
        </template>
        <ElFormItem label="状态">
          <ElSwitch v-model="hostForm.status" :active-value="0" :inactive-value="1" />
        </ElFormItem>
        <ElFormItem label="备注"><ElInput v-model="hostForm.description" /></ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="hostDialogVisible = false">取消</ElButton>
        <ElButton :loading="hostTesting" @click="handleHostTestConfig">测试连接</ElButton>
        <ElButton type="primary" :loading="hostSaving" @click="handleHostSave">保存</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="snippetDialogVisible" title="新增命令片段" width="520px">
      <ElForm label-width="80px">
        <ElFormItem label="名称"><ElInput v-model="snippetForm.name" /></ElFormItem>
        <ElFormItem label="命令">
          <ElInput v-model="snippetForm.command" type="textarea" :rows="4" />
        </ElFormItem>
        <ElFormItem label="备注"><ElInput v-model="snippetForm.description" /></ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="snippetDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="snippetSaving" @click="handleSnippetSave">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script lang="ts" setup>
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import SshAPI, {
  type BatchExecResult,
  type SshHost,
  type SshHostForm,
  type SshSnippet,
  type TerminalSession,
} from "@/api/module_ops/ssh";

defineOptions({ name: "SshOps" });

const activeTab = ref("host");
const hosts = ref<SshHost[]>([]);
const snippets = ref<SshSnippet[]>([]);

// ── 主机 ──────────────────────────────────────────────────────────────
const hostDialogVisible = ref(false);
const editingHostId = ref<number>();
const hostSaving = ref(false);
const hostTesting = ref(false);
const hostFormRef = ref<FormInstance>();
const hostForm = reactive<SshHostForm>({
  name: "",
  host: "",
  port: 22,
  username: "root",
  auth_type: "password",
  password: "",
  private_key: "",
  passphrase: "",
  status: 0,
  description: "",
});
const hostRules: FormRules<SshHostForm> = {
  name: [{ required: true, message: "请输入名称", trigger: "blur" }],
  host: [{ required: true, message: "请输入地址", trigger: "blur" }],
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
};

async function loadHosts() {
  const res = await SshAPI.listHosts();
  hosts.value = res.data.data || [];
}

function openHostCreate() {
  editingHostId.value = undefined;
  Object.assign(hostForm, {
    name: "",
    host: "",
    port: 22,
    username: "root",
    auth_type: "password",
    password: "",
    private_key: "",
    passphrase: "",
    status: 0,
    description: "",
  });
  hostDialogVisible.value = true;
}

function openHostEdit(raw: unknown) {
  const row = raw as SshHost;
  editingHostId.value = row.id;
  Object.assign(hostForm, {
    name: row.name,
    host: row.host,
    port: row.port,
    username: row.username,
    auth_type: row.auth_type,
    password: "",
    private_key: "",
    passphrase: "",
    status: row.status,
    description: row.description || "",
  });
  hostDialogVisible.value = true;
}

async function handleHostSave() {
  if (!hostFormRef.value) return;
  const valid = await hostFormRef.value.validate().catch(() => false);
  if (!valid) return;
  const payload: SshHostForm = { ...hostForm };
  if (!payload.password) delete payload.password;
  if (!payload.private_key) delete payload.private_key;
  if (!payload.passphrase) delete payload.passphrase;
  hostSaving.value = true;
  try {
    if (editingHostId.value) {
      await SshAPI.updateHost(editingHostId.value, payload);
      ElMessage.success("已保存");
    } else {
      await SshAPI.createHost(payload);
      ElMessage.success("已新增");
    }
    hostDialogVisible.value = false;
    await loadHosts();
  } finally {
    hostSaving.value = false;
  }
}

async function handleHostTest(raw: unknown) {
  const row = raw as SshHost;
  const res = await SshAPI.testHost(row.id);
  ElMessage.success(res.data?.msg || "连接成功");
}

async function handleHostTestConfig() {
  hostTesting.value = true;
  try {
    const res = await SshAPI.testHostConfig({ ...hostForm });
    ElMessage.success(res.data?.msg || "连接成功");
  } finally {
    hostTesting.value = false;
  }
}

async function handleHostDelete(raw: unknown) {
  const row = raw as SshHost;
  await ElMessageBox.confirm(`确认删除主机「${row.name}」？`, "提示", { type: "warning" });
  await SshAPI.deleteHosts([row.id]);
  ElMessage.success("已删除");
  await loadHosts();
}

// ── 片段 ──────────────────────────────────────────────────────────────
const snippetDialogVisible = ref(false);
const snippetSaving = ref(false);
const snippetForm = reactive({ name: "", command: "", description: "" });

async function loadSnippets() {
  const res = await SshAPI.listSnippets();
  snippets.value = res.data.data || [];
}

function openSnippetCreate() {
  Object.assign(snippetForm, { name: "", command: "", description: "" });
  snippetDialogVisible.value = true;
}

async function handleSnippetSave() {
  if (!snippetForm.name || !snippetForm.command) {
    ElMessage.warning("名称与命令不能为空");
    return;
  }
  snippetSaving.value = true;
  try {
    await SshAPI.createSnippet({ ...snippetForm });
    ElMessage.success("已新增");
    snippetDialogVisible.value = false;
    await loadSnippets();
  } finally {
    snippetSaving.value = false;
  }
}

function applySnippet(raw: unknown) {
  const row = raw as SshSnippet;
  batchCommand.value = row.command;
  activeTab.value = "batch";
}

async function handleSnippetDelete(raw: unknown) {
  const row = raw as SshSnippet;
  await ElMessageBox.confirm(`确认删除片段「${row.name}」？`, "提示", { type: "warning" });
  await SshAPI.deleteSnippets([row.id]);
  ElMessage.success("已删除");
  await loadSnippets();
}

// ── 批量执行 ──────────────────────────────────────────────────────────
const batchHostIds = ref<number[]>([]);
const batchCommand = ref("");
const batchRunning = ref(false);
const batchResults = ref<BatchExecResult[]>([]);

async function runBatch() {
  if (!batchHostIds.value.length || !batchCommand.value.trim()) {
    ElMessage.warning("请选择主机并填写命令");
    return;
  }
  batchRunning.value = true;
  try {
    const res = await SshAPI.batchExec({
      host_ids: batchHostIds.value,
      command: batchCommand.value,
      timeout: 15,
    });
    batchResults.value = res.data.data || [];
    ElMessage.success("批量执行完成");
  } finally {
    batchRunning.value = false;
  }
}

// ── 终端（POST 轮询）─────────────────────────────────────────────────
const terminalHostId = ref<number>();
const terminalOpening = ref(false);
const terminalSession = ref<TerminalSession>();
const terminalSessionId = computed(() => terminalSession.value?.session_id || "");
const terminalOutput = ref("");
const terminalInput = ref("");
const terminalRef = ref<HTMLElement>();
const logPath = ref("");
let pollTimer: number | undefined;

function b64encode(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  bytes.forEach((byte) => (binary += String.fromCharCode(byte)));
  return btoa(binary);
}

function b64decode(value: string): string {
  const binary = atob(value);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

function appendOutput(text: string) {
  terminalOutput.value = (terminalOutput.value + text).slice(-200_000);
  nextTick(() => {
    if (terminalRef.value) terminalRef.value.scrollTop = terminalRef.value.scrollHeight;
  });
}

function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    if (!terminalSessionId.value) return;
    try {
      const res = await SshAPI.pollTerminal(terminalSessionId.value, 1.2);
      const payload = res.data.data;
      if (payload?.data) appendOutput(b64decode(payload.data));
      if (payload?.closed) {
        appendOutput("\n[会话已结束]\n");
        stopPolling();
      }
    } catch {
      stopPolling();
    }
  }, 700);
}

function stopPolling() {
  if (pollTimer !== undefined) {
    window.clearInterval(pollTimer);
    pollTimer = undefined;
  }
}

async function openTerminal() {
  if (!terminalHostId.value) return;
  terminalOpening.value = true;
  try {
    const res = await SshAPI.openTerminal({ host_id: terminalHostId.value, cols: 120, rows: 30 });
    terminalSession.value = res.data.data;
    terminalOutput.value = "";
    appendOutput(`[已连接 ${terminalSession.value?.host_name}]\n`);
    startPolling();
  } finally {
    terminalOpening.value = false;
  }
}

async function openLogTail() {
  if (!terminalHostId.value || !logPath.value.trim()) return;
  terminalOpening.value = true;
  try {
    const res = await SshAPI.openLog({
      host_id: terminalHostId.value,
      path: logPath.value.trim(),
      lines: 200,
    });
    terminalSession.value = res.data.data;
    terminalOutput.value = "";
    appendOutput(`[日志跟踪 ${logPath.value}]\n`);
    startPolling();
  } finally {
    terminalOpening.value = false;
  }
}

async function sendTerminalInput() {
  if (!terminalSessionId.value) return;
  const text = terminalInput.value;
  terminalInput.value = "";
  await SshAPI.inputTerminal(terminalSessionId.value, b64encode(`${text}\r`));
}

async function closeTerminal() {
  const sessionId = terminalSessionId.value;
  stopPolling();
  terminalSession.value = undefined;
  if (sessionId) {
    await SshAPI.closeTerminal(sessionId).catch(() => undefined);
  }
  appendOutput("\n[已关闭]\n");
}

onMounted(async () => {
  await loadHosts();
  await loadSnippets();
});

onBeforeUnmount(() => stopPolling());
</script>

<style scoped>
.terminal-output {
  font-family: "SFMono-Regular", Menlo, Consolas, monospace;
}
</style>
