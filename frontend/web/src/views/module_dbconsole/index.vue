<!-- SQL 控制台：仅外部 MySQL/PostgreSQL（不含本地/内置库） -->
<template>
  <div class="fa-full-height flex flex-col gap-3 p-3">
    <ElCard shadow="hover" class="fa-card">
      <div class="mb-3 flex items-center justify-between">
        <span class="text-[15px] font-medium">数据库连接（仅外部 MySQL / PostgreSQL）</span>
        <ElButton type="primary" @click="openCreate">新增连接</ElButton>
      </div>
      <ElTable :data="connections" size="small" max-height="240" empty-text="尚未配置连接">
        <ElTableColumn prop="name" label="名称" min-width="140" />
        <ElTableColumn prop="db_type" label="类型" width="100" />
        <ElTableColumn label="地址" min-width="180">
          <template #default="{ row }">{{ row.host }}:{{ row.port }}</template>
        </ElTableColumn>
        <ElTableColumn prop="database" label="默认库" width="140" />
        <ElTableColumn label="状态" width="90">
          <template #default="{ row }">
            <ElTag :type="row.status === 0 ? 'success' : 'info'" size="small">{{
              row.status === 0 ? "启用" : "停用"
            }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" @click="selectConnection(row)">使用</ElButton>
            <ElButton link @click="handleTest(row)">测试</ElButton>
            <ElButton link @click="openEdit(row)">编辑</ElButton>
            <ElButton link type="danger" @click="handleDelete(row)">删除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <ElCard shadow="hover" class="fa-card flex flex-1 flex-col">
      <div class="mb-2 flex flex-wrap items-center gap-2">
        <span class="text-[15px] font-medium">查询</span>
        <ElSelect
          v-model="currentId"
          placeholder="选择连接"
          style="width: 180px"
          @change="onConnectionChange"
        >
          <ElOption v-for="c in connections" :key="c.id" :label="c.name" :value="c.id" />
        </ElSelect>
        <ElSelect
          v-model="currentDatabase"
          placeholder="库/schema"
          style="width: 150px"
          clearable
          @change="loadTables"
        >
          <ElOption v-for="d in databases" :key="d.name" :label="d.name" :value="d.name" />
        </ElSelect>
        <ElSelect
          v-model="currentTable"
          placeholder="表（选中填入查询）"
          style="width: 190px"
          clearable
          filterable
          @change="fillTableQuery"
        >
          <ElOption v-for="t in tables" :key="t.name" :label="t.name" :value="t.name" />
        </ElSelect>
        <div class="ml-auto flex items-center gap-2">
          <span class="text-xs text-[#909399]">允许写操作</span>
          <ElSwitch v-model="confirmed" size="small" />
          <ElButton type="primary" :loading="running" :disabled="!currentId" @click="runQuery"
            >执行</ElButton
          >
        </div>
      </div>
      <ElInput
        v-model="sql"
        type="textarea"
        :rows="6"
        placeholder="select * from ...（只读语句自动校验；写语句需先打开「允许写操作」）"
      />
      <div v-if="result" class="mt-3">
        <ElAlert
          v-if="result.masked_columns.length"
          type="warning"
          :closable="false"
          class="mb-2"
          :title="`敏感列已打码：${result.masked_columns.join(', ')}`"
        />
        <ElAlert
          v-if="result.truncated"
          type="info"
          :closable="false"
          class="mb-2"
          title="结果超过 200 行，已截断"
        />
        <div class="mb-2 text-xs text-[#909399]">
          {{ result.read_only ? "只读查询" : "写操作" }} · {{ result.rowcount }} 行 ·
          {{ result.elapsed_ms }} ms
        </div>
        <ElTable :data="resultRows" size="small" max-height="360" border>
          <ElTableColumn
            v-for="(col, idx) in result.columns"
            :key="`${col}-${idx}`"
            :label="col"
            min-width="140"
          >
            <template #default="{ row }">{{ row[idx] }}</template>
          </ElTableColumn>
        </ElTable>
      </div>
    </ElCard>

    <ElDialog v-model="dialogVisible" :title="editingId ? '编辑连接' : '新增连接'" width="560px">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="90px">
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="form.name" placeholder="唯一名称" />
        </ElFormItem>
        <ElFormItem label="类型" prop="db_type">
          <ElSelect v-model="form.db_type">
            <ElOption label="MySQL" value="mysql" />
            <ElOption label="PostgreSQL" value="postgres" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="主机" prop="host"><ElInput v-model="form.host" /></ElFormItem>
        <ElFormItem label="端口" prop="port">
          <ElInputNumber v-model="form.port" :min="1" :max="65535" />
        </ElFormItem>
        <ElFormItem label="用户名" prop="username"><ElInput v-model="form.username" /></ElFormItem>
        <ElFormItem label="密码" prop="password">
          <ElInput
            v-model="form.password"
            type="password"
            show-password
            :placeholder="editingId ? '不修改请留空' : ''"
          />
        </ElFormItem>
        <ElFormItem label="默认库">
          <ElInput v-model="form.database" placeholder="可空" />
        </ElFormItem>
        <ElFormItem label="备注">
          <ElInput v-model="form.description" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton :loading="testing" @click="handleTestConfig">测试连接</ElButton>
        <ElButton type="primary" :loading="saving" @click="handleSave">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script lang="ts" setup>
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import DbConsoleAPI, {
  type DbConnection,
  type DbConnectionForm,
  type DbObject,
  type DbQueryResult,
} from "@/api/module_dbconsole/connection";

defineOptions({ name: "DbConsole" });

const connections = ref<DbConnection[]>([]);
const currentId = ref<number>();
const databases = ref<DbObject[]>([]);
const tables = ref<DbObject[]>([]);
const currentDatabase = ref<string>();
const currentTable = ref<string>();
const sql = ref("select 1");
const confirmed = ref(false);
const running = ref(false);
const result = ref<DbQueryResult>();

const dialogVisible = ref(false);
const editingId = ref<number>();
const saving = ref(false);
const testing = ref(false);
const formRef = ref<FormInstance>();
const form = reactive<DbConnectionForm>({
  name: "",
  db_type: "mysql",
  host: "",
  port: 3306,
  username: "",
  password: "",
  database: "",
  description: "",
});
const rules: FormRules<DbConnectionForm> = {
  name: [{ required: true, message: "请输入名称", trigger: "blur" }],
  db_type: [{ required: true, message: "请选择类型", trigger: "change" }],
  host: [{ required: true, message: "请输入主机", trigger: "blur" }],
  port: [{ required: true, message: "请输入端口", trigger: "blur" }],
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
};

const resultRows = computed<Record<number, unknown>[]>(() => {
  if (!result.value) return [];
  return result.value.rows.map((row) =>
    Object.fromEntries(row.map((value, index) => [index, value]))
  );
});

async function loadConnections() {
  const res = await DbConsoleAPI.listConnections();
  connections.value = res.data.data || [];
}

function openCreate() {
  editingId.value = undefined;
  Object.assign(form, {
    name: "",
    db_type: "mysql",
    host: "",
    port: 3306,
    username: "",
    password: "",
    database: "",
    description: "",
  });
  dialogVisible.value = true;
}

function openEdit(raw: unknown) {
  const row = raw as DbConnection;
  editingId.value = row.id;
  Object.assign(form, {
    name: row.name,
    db_type: row.db_type,
    host: row.host,
    port: row.port,
    username: row.username,
    password: "",
    database: row.database || "",
    description: row.description || "",
  });
  dialogVisible.value = true;
}

async function handleSave() {
  if (!formRef.value) return;
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;
  saving.value = true;
  try {
    if (editingId.value) {
      await DbConsoleAPI.updateConnection(editingId.value, { ...form });
      ElMessage.success("已保存");
    } else {
      await DbConsoleAPI.createConnection({ ...form });
      ElMessage.success("已新增");
    }
    dialogVisible.value = false;
    await loadConnections();
  } finally {
    saving.value = false;
  }
}

async function handleTest(raw: unknown) {
  const row = raw as DbConnection;
  const res = await DbConsoleAPI.testConnection(row.id);
  ElMessage.success(res.data?.msg || "连接成功");
}

async function handleTestConfig() {
  testing.value = true;
  try {
    const res = await DbConsoleAPI.testConnectionConfig({ ...form });
    ElMessage.success(res.data?.msg || "连接成功");
  } finally {
    testing.value = false;
  }
}

async function handleDelete(raw: unknown) {
  const row = raw as DbConnection;
  await ElMessageBox.confirm(`确认删除连接「${row.name}」？`, "提示", { type: "warning" });
  await DbConsoleAPI.deleteConnections([row.id]);
  ElMessage.success("已删除");
  if (currentId.value === row.id) currentId.value = undefined;
  await loadConnections();
}

async function selectConnection(raw: unknown) {
  const row = raw as DbConnection;
  currentId.value = row.id;
  await onConnectionChange(row.id);
}

async function onConnectionChange(id: number) {
  currentDatabase.value = undefined;
  currentTable.value = undefined;
  result.value = undefined;
  await loadDatabases(id);
}

async function loadDatabases(id: number) {
  const res = await DbConsoleAPI.listDatabases(id);
  databases.value = res.data.data || [];
}

async function loadTables() {
  if (!currentId.value) return;
  const res = await DbConsoleAPI.listTables(currentId.value, currentDatabase.value);
  tables.value = res.data.data || [];
}

async function fillTableQuery(table?: string) {
  if (!table) return;
  sql.value = `select * from ${table} limit 100`;
}

async function runQuery() {
  if (!currentId.value) return;
  running.value = true;
  try {
    const res = await DbConsoleAPI.runQuery(currentId.value, {
      sql: sql.value,
      confirmed: confirmed.value,
    });
    result.value = res.data.data;
    ElMessage.success(res.data?.msg || "执行成功");
  } finally {
    running.value = false;
  }
}

onMounted(loadConnections);
</script>
