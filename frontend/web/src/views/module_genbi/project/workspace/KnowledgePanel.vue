<!-- Knowledge：指令 / 指标文档 / SQL 问答对 -->
<template>
  <div v-loading="loading" class="genbi-knowledge">
    <ElTabs v-model="subTab">
      <ElTabPane label="指令" name="instructions">
        <div class="genbi-knowledge__toolbar">
          <span class="genbi-knowledge__hint">问数指令与关联问题（对齐 tiga instructions）</span>
          <ElButton
            v-hasPerm="['module_genbi:project:update']"
            size="small"
            type="primary"
            @click="openInstruction()"
          >
            新增
          </ElButton>
        </div>
        <ElTable :data="instructions" size="small">
          <ElTableColumn prop="instruction" label="指令" min-width="220" show-overflow-tooltip />
          <ElTableColumn label="关联问题" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              {{ (row.questions || []).join("；") || "—" }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="120" align="center" fixed="right">
            <template #default="{ row }">
              <ElButton
                v-hasPerm="['module_genbi:project:update']"
                link
                type="primary"
                size="small"
                @click="openInstruction(row)"
              >
                编辑
              </ElButton>
              <ElButton
                v-hasPerm="['module_genbi:project:update']"
                link
                type="danger"
                size="small"
                @click="removeInstruction(row)"
              >
                删除
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>

      <ElTabPane label="指标文档" name="metric-docs">
        <div class="genbi-knowledge__toolbar">
          <span class="genbi-knowledge__hint">业务指标说明文档</span>
          <ElButton
            v-hasPerm="['module_genbi:project:update']"
            size="small"
            type="primary"
            @click="openMetricDoc()"
          >
            新增
          </ElButton>
        </div>
        <ElTable :data="metricDocs" size="small">
          <ElTableColumn prop="name" label="名称" min-width="140" show-overflow-tooltip />
          <ElTableColumn prop="content" label="内容" min-width="240" show-overflow-tooltip />
          <ElTableColumn label="启用" width="72" align="center">
            <template #default="{ row }">{{ row.enabled ? "是" : "否" }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="120" align="center" fixed="right">
            <template #default="{ row }">
              <ElButton
                v-hasPerm="['module_genbi:project:update']"
                link
                type="primary"
                size="small"
                @click="openMetricDoc(row)"
              >
                编辑
              </ElButton>
              <ElButton
                v-hasPerm="['module_genbi:project:update']"
                link
                type="danger"
                size="small"
                @click="removeMetricDoc(row)"
              >
                删除
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>

      <ElTabPane label="SQL 问答对" name="sql-pairs">
        <div class="genbi-knowledge__toolbar">
          <span class="genbi-knowledge__hint">问题 ↔ SQL 示例对</span>
          <ElButton
            v-hasPerm="['module_genbi:project:update']"
            size="small"
            type="primary"
            @click="openSqlPair()"
          >
            新增
          </ElButton>
        </div>
        <ElTable :data="sqlPairs" size="small">
          <ElTableColumn prop="question" label="问题" min-width="180" show-overflow-tooltip />
          <ElTableColumn prop="sql" label="SQL" min-width="240" show-overflow-tooltip />
          <ElTableColumn label="启用" width="72" align="center">
            <template #default="{ row }">{{ row.enabled ? "是" : "否" }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="120" align="center" fixed="right">
            <template #default="{ row }">
              <ElButton
                v-hasPerm="['module_genbi:project:update']"
                link
                type="primary"
                size="small"
                @click="openSqlPair(row)"
              >
                编辑
              </ElButton>
              <ElButton
                v-hasPerm="['module_genbi:project:update']"
                link
                type="danger"
                size="small"
                @click="removeSqlPair(row)"
              >
                删除
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>
    </ElTabs>

    <FaDialog
      v-model="instVisible"
      :title="editingInstId ? '编辑指令' : '新增指令'"
      width="640px"
      form-mode="create"
      :confirm-loading="instSaving"
      @cancel="instVisible = false"
      @close="instVisible = false"
      @confirm="saveInstruction"
    >
      <ElForm label-width="88px" class="genbi-knowledge__form">
        <ElFormItem label="指令" required>
          <ElInput v-model="instForm.instruction" type="textarea" :rows="4" />
        </ElFormItem>
        <ElFormItem label="关联问题">
          <ElInput
            v-model="instForm.questions"
            type="textarea"
            :rows="3"
            placeholder="每行一个问题"
          />
        </ElFormItem>
      </ElForm>
    </FaDialog>

    <FaDialog
      v-model="docVisible"
      :title="editingDocId ? '编辑指标文档' : '新增指标文档'"
      width="640px"
      form-mode="create"
      :confirm-loading="docSaving"
      @cancel="docVisible = false"
      @close="docVisible = false"
      @confirm="saveMetricDoc"
    >
      <ElForm label-width="88px" class="genbi-knowledge__form">
        <ElFormItem label="名称" required>
          <ElInput v-model="docForm.name" maxlength="255" />
        </ElFormItem>
        <ElFormItem label="内容" required>
          <ElInput v-model="docForm.content" type="textarea" :rows="6" />
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="docForm.enabled" />
        </ElFormItem>
      </ElForm>
    </FaDialog>

    <FaDialog
      v-model="pairVisible"
      :title="editingPairId ? '编辑 SQL 问答对' : '新增 SQL 问答对'"
      width="720px"
      form-mode="create"
      :confirm-loading="pairSaving"
      @cancel="pairVisible = false"
      @close="pairVisible = false"
      @confirm="saveSqlPair"
    >
      <ElForm label-width="88px" class="genbi-knowledge__form">
        <ElFormItem label="问题" required>
          <ElInput v-model="pairForm.question" type="textarea" :rows="2" />
        </ElFormItem>
        <ElFormItem label="SQL" required>
          <ElInput v-model="pairForm.sql" type="textarea" :rows="8" />
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="pairForm.enabled" />
        </ElFormItem>
      </ElForm>
    </FaDialog>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import GenbiProjectAPI, {
  type GenbiInstructionTable,
  type GenbiMetricDocTable,
  type GenbiSqlPairTable,
} from "@/api/module_genbi/project";

defineOptions({ name: "GenbiKnowledgePanel", inheritAttrs: false });

const props = defineProps<{ projectId: number }>();

const loading = ref(false);
const subTab = ref("instructions");
const instructions = ref<GenbiInstructionTable[]>([]);
const metricDocs = ref<GenbiMetricDocTable[]>([]);
const sqlPairs = ref<GenbiSqlPairTable[]>([]);

const instVisible = ref(false);
const instSaving = ref(false);
const editingInstId = ref<number>();
const instForm = ref({ instruction: "", questions: "" });

const docVisible = ref(false);
const docSaving = ref(false);
const editingDocId = ref<number>();
const docForm = ref({ name: "", content: "", enabled: true });

const pairVisible = ref(false);
const pairSaving = ref(false);
const editingPairId = ref<number>();
const pairForm = ref({ question: "", sql: "", enabled: true });

async function load() {
  loading.value = true;
  try {
    const [instRes, docRes, pairRes] = await Promise.all([
      GenbiProjectAPI.listInstructions(props.projectId),
      GenbiProjectAPI.listMetricDocs(props.projectId),
      GenbiProjectAPI.listSqlPairs(props.projectId),
    ]);
    instructions.value = instRes.data.data ?? [];
    metricDocs.value = docRes.data.data ?? [];
    sqlPairs.value = pairRes.data.data ?? [];
  } finally {
    loading.value = false;
  }
}

function openInstruction(row?: GenbiInstructionTable) {
  editingInstId.value = row?.id;
  instForm.value = {
    instruction: row?.instruction || "",
    questions: (row?.questions || []).join("\n"),
  };
  instVisible.value = true;
}

async function saveInstruction() {
  const instruction = instForm.value.instruction.trim();
  if (!instruction) {
    ElMessage.error("请填写指令");
    return;
  }
  const questions = instForm.value.questions
    .split("\n")
    .map((q) => q.trim())
    .filter(Boolean);
  instSaving.value = true;
  try {
    if (editingInstId.value) {
      await GenbiProjectAPI.updateInstruction(props.projectId, editingInstId.value, {
        instruction,
        questions,
      });
    } else {
      await GenbiProjectAPI.createInstruction(props.projectId, {
        instruction,
        questions,
        is_default: true,
      });
    }
    instVisible.value = false;
    ElMessage.success("已保存");
    await load();
  } finally {
    instSaving.value = false;
  }
}

async function removeInstruction(row: GenbiInstructionTable) {
  if (!row.id) return;
  try {
    await ElMessageBox.confirm("确认删除该指令？", "删除", { type: "warning" });
  } catch {
    return;
  }
  await GenbiProjectAPI.deleteInstruction(props.projectId, row.id);
  ElMessage.success("已删除");
  await load();
}

function openMetricDoc(row?: GenbiMetricDocTable) {
  editingDocId.value = row?.id;
  docForm.value = {
    name: row?.name || "",
    content: row?.content || "",
    enabled: row?.enabled !== false,
  };
  docVisible.value = true;
}

async function saveMetricDoc() {
  const name = docForm.value.name.trim();
  const content = docForm.value.content.trim();
  if (!name || !content) {
    ElMessage.error("名称与内容不能为空");
    return;
  }
  docSaving.value = true;
  try {
    const payload = { name, content, enabled: docForm.value.enabled };
    if (editingDocId.value) {
      await GenbiProjectAPI.updateMetricDoc(props.projectId, editingDocId.value, payload);
    } else {
      await GenbiProjectAPI.createMetricDoc(props.projectId, payload);
    }
    docVisible.value = false;
    ElMessage.success("已保存");
    await load();
  } finally {
    docSaving.value = false;
  }
}

async function removeMetricDoc(row: GenbiMetricDocTable) {
  if (!row.id) return;
  try {
    await ElMessageBox.confirm("确认删除该指标文档？", "删除", { type: "warning" });
  } catch {
    return;
  }
  await GenbiProjectAPI.deleteMetricDoc(props.projectId, row.id);
  ElMessage.success("已删除");
  await load();
}

function openSqlPair(row?: GenbiSqlPairTable) {
  editingPairId.value = row?.id;
  pairForm.value = {
    question: row?.question || "",
    sql: row?.sql || "",
    enabled: row?.enabled !== false,
  };
  pairVisible.value = true;
}

async function saveSqlPair() {
  const question = pairForm.value.question.trim();
  const sql = pairForm.value.sql.trim();
  if (!question || !sql) {
    ElMessage.error("问题与 SQL 不能为空");
    return;
  }
  pairSaving.value = true;
  try {
    const payload = { question, sql, enabled: pairForm.value.enabled };
    if (editingPairId.value) {
      await GenbiProjectAPI.updateSqlPair(props.projectId, editingPairId.value, payload);
    } else {
      await GenbiProjectAPI.createSqlPair(props.projectId, payload);
    }
    pairVisible.value = false;
    ElMessage.success("已保存");
    await load();
  } finally {
    pairSaving.value = false;
  }
}

async function removeSqlPair(row: GenbiSqlPairTable) {
  if (!row.id) return;
  try {
    await ElMessageBox.confirm("确认删除该 SQL 问答对？", "删除", { type: "warning" });
  } catch {
    return;
  }
  await GenbiProjectAPI.deleteSqlPair(props.projectId, row.id);
  ElMessage.success("已删除");
  await load();
}

watch(
  () => props.projectId,
  () => {
    void load();
  },
  { immediate: true },
);
</script>

<style scoped>
.genbi-knowledge__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.genbi-knowledge__hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.genbi-knowledge__form {
  padding: 0 16px 8px;
}
</style>
