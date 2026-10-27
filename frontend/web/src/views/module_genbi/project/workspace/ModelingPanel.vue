<!-- Modeling：结构化模型/列编辑器（ElTable，替代纯 JSON） -->
<template>
  <div v-loading="loading" class="genbi-modeling">
    <div class="genbi-modeling__toolbar">
      <div class="genbi-modeling__hint">
        左侧选择/维护模型，右侧编辑列。保存会整表替换项目下的 MDL 模型与关系。
      </div>
      <div class="genbi-modeling__actions">
        <ElButton size="small" @click="load">刷新</ElButton>
        <ElButton
          v-hasPerm="['module_genbi:project:update']"
          size="small"
          @click="showJson = !showJson"
        >
          {{ showJson ? "结构化编辑" : "JSON 视图" }}
        </ElButton>
        <ElButton
          v-hasPerm="['module_genbi:project:update']"
          type="primary"
          size="small"
          :loading="saving"
          @click="saveAll"
        >
          保存模型
        </ElButton>
      </div>
    </div>

    <template v-if="showJson">
      <ElInput
        v-model="modelsJson"
        type="textarea"
        :rows="18"
        placeholder='[{"display_name":"订单","source_table_name":"orders","reference_name":"orders","columns":[]}]'
      />
    </template>

    <div v-else class="genbi-modeling__layout">
      <ElCard shadow="never" class="genbi-modeling__models" :body-style="{ padding: '12px' }">
        <div class="genbi-modeling__card-head">
          <span>模型</span>
          <ElButton
            v-hasPerm="['module_genbi:project:update']"
            size="small"
            type="primary"
            plain
            @click="addModel"
          >
            新增模型
          </ElButton>
        </div>
        <ElTable
          :data="draftModels"
          size="small"
          highlight-current-row
          height="420"
          @current-change="onSelectModel"
        >
          <ElTableColumn prop="display_name" label="显示名" min-width="100">
            <template #default="{ row }">
              <ElInput v-model="row.display_name" size="small" />
            </template>
          </ElTableColumn>
          <ElTableColumn prop="reference_name" label="引用名" min-width="100">
            <template #default="{ row }">
              <ElInput v-model="row.reference_name" size="small" />
            </template>
          </ElTableColumn>
          <ElTableColumn prop="source_table_name" label="源表" min-width="110">
            <template #default="{ row }">
              <ElInput v-model="row.source_table_name" size="small" />
            </template>
          </ElTableColumn>
          <ElTableColumn label="" width="56" align="center">
            <template #default="{ $index }">
              <ElButton
                v-hasPerm="['module_genbi:project:update']"
                type="danger"
                link
                size="small"
                @click.stop="removeModel($index)"
              >
                删
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElCard>

      <ElCard shadow="never" class="genbi-modeling__columns" :body-style="{ padding: '12px' }">
        <div class="genbi-modeling__card-head">
          <span>
            列
            <template v-if="selectedModel">
              · {{ selectedModel.display_name || selectedModel.reference_name || "未命名" }}
            </template>
          </span>
          <ElButton
            v-hasPerm="['module_genbi:project:update']"
            size="small"
            type="primary"
            plain
            :disabled="!selectedModel"
            @click="addColumn"
          >
            新增列
          </ElButton>
        </div>
        <ElEmpty v-if="!selectedModel" description="请选择左侧模型" :image-size="64" />
        <ElTable v-else :data="selectedModel.columns" size="small" height="420">
          <ElTableColumn label="显示名" min-width="110">
            <template #default="{ row }">
              <ElInput v-model="row.display_name" size="small" />
            </template>
          </ElTableColumn>
          <ElTableColumn label="源列" min-width="110">
            <template #default="{ row }">
              <ElInput v-model="row.source_column_name" size="small" />
            </template>
          </ElTableColumn>
          <ElTableColumn label="类型" width="120">
            <template #default="{ row }">
              <ElInput v-model="row.column_type" size="small" placeholder="varchar" />
            </template>
          </ElTableColumn>
          <ElTableColumn label="计算列" width="72" align="center">
            <template #default="{ row }">
              <ElSwitch v-model="row.is_calculated" size="small" />
            </template>
          </ElTableColumn>
          <ElTableColumn label="表达式" min-width="140">
            <template #default="{ row }">
              <ElInput
                v-model="row.expression"
                size="small"
                :disabled="!row.is_calculated"
                placeholder="expression"
              />
            </template>
          </ElTableColumn>
          <ElTableColumn label="" width="56" align="center">
            <template #default="{ $index }">
              <ElButton
                v-hasPerm="['module_genbi:project:update']"
                type="danger"
                link
                size="small"
                @click="removeColumn($index)"
              >
                删
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElCard>
    </div>

    <ElCard shadow="never" class="genbi-modeling__rels" :body-style="{ padding: '12px' }">
      <div class="genbi-modeling__card-head">
        <span>关系（diagram-lite）</span>
        <ElButton
          v-hasPerm="['module_genbi:project:update']"
          size="small"
          type="primary"
          plain
          :disabled="draftModels.length < 2"
          @click="addRelationship"
        >
          新增关系
        </ElButton>
      </div>
      <ElTable :data="draftRels" size="small">
        <ElTableColumn label="源模型" min-width="140">
          <template #default="{ row }">
            <ElSelect v-model="row.from_ref" size="small" filterable placeholder="引用名">
              <ElOption
                v-for="m in draftModels"
                :key="`from-${m._key}`"
                :label="m.reference_name || m.display_name"
                :value="m.reference_name"
              />
            </ElSelect>
          </template>
        </ElTableColumn>
        <ElTableColumn label="目标模型" min-width="140">
          <template #default="{ row }">
            <ElSelect v-model="row.to_ref" size="small" filterable placeholder="引用名">
              <ElOption
                v-for="m in draftModels"
                :key="`to-${m._key}`"
                :label="m.reference_name || m.display_name"
                :value="m.reference_name"
              />
            </ElSelect>
          </template>
        </ElTableColumn>
        <ElTableColumn label="Join" width="140">
          <template #default="{ row }">
            <ElSelect v-model="row.join_type" size="small">
              <ElOption label="MANY_TO_ONE" value="MANY_TO_ONE" />
              <ElOption label="ONE_TO_MANY" value="ONE_TO_MANY" />
              <ElOption label="ONE_TO_ONE" value="ONE_TO_ONE" />
              <ElOption label="MANY_TO_MANY" value="MANY_TO_MANY" />
            </ElSelect>
          </template>
        </ElTableColumn>
        <ElTableColumn label="条件" min-width="180">
          <template #default="{ row }">
            <ElInput v-model="row.condition" size="small" placeholder="a.id = b.a_id" />
          </template>
        </ElTableColumn>
        <ElTableColumn label="" width="56" align="center">
          <template #default="{ $index }">
            <ElButton
              v-hasPerm="['module_genbi:project:update']"
              type="danger"
              link
              size="small"
              @click="draftRels.splice($index, 1)"
            >
              删
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import GenbiProjectAPI, {
  type GenbiModelColumnIn,
  type GenbiModelIn,
  type GenbiModelTable,
  type GenbiRelationshipTable,
} from "@/api/module_genbi/project";

defineOptions({ name: "GenbiModelingPanel", inheritAttrs: false });

const props = defineProps<{ projectId: number }>();
const emit = defineEmits<{ saved: [] }>();

interface DraftColumn extends GenbiModelColumnIn {
  _key: string;
}

interface DraftModel extends GenbiModelIn {
  _key: string;
  _id?: number;
  columns: DraftColumn[];
}

interface DraftRel {
  _key: string;
  from_ref: string;
  to_ref: string;
  join_type: string;
  condition: string;
}

const loading = ref(false);
const saving = ref(false);
const showJson = ref(false);
const draftModels = ref<DraftModel[]>([]);
const draftRels = ref<DraftRel[]>([]);
const selectedKey = ref<string>();
const modelsJson = ref("[]");

let keySeq = 0;
function nextKey(prefix: string) {
  keySeq += 1;
  return `${prefix}-${keySeq}`;
}

const selectedModel = computed(() =>
  draftModels.value.find((m) => m._key === selectedKey.value),
);

function emptyColumn(): DraftColumn {
  return {
    _key: nextKey("col"),
    display_name: "",
    source_column_name: "",
    column_type: "varchar",
    is_calculated: false,
    expression: null,
  };
}

function emptyModel(): DraftModel {
  return {
    _key: nextKey("model"),
    display_name: "",
    source_table_name: "",
    reference_name: "",
    columns: [emptyColumn()],
  };
}

function modelFromApi(model: GenbiModelTable): DraftModel {
  return {
    _key: nextKey("model"),
    _id: model.id,
    display_name: model.display_name || "",
    source_table_name: model.source_table_name || "",
    reference_name: model.reference_name || "",
    ref_sql: model.ref_sql ?? null,
    cached: model.cached === true,
    refresh_time: model.refresh_time ?? null,
    properties: model.properties ?? null,
    columns: (model.columns ?? []).map((col) => ({
      _key: nextKey("col"),
      display_name: col.display_name || "",
      source_column_name: col.source_column_name || "",
      column_type: col.column_type || "varchar",
      is_calculated: col.is_calculated === true,
      expression: col.expression ?? null,
      properties: col.properties ?? null,
    })),
  };
}

function relFromApi(rel: GenbiRelationshipTable, models: DraftModel[]): DraftRel {
  const from = models.find((m) => m._id === rel.from_model_id);
  const to = models.find((m) => m._id === rel.to_model_id);
  return {
    _key: nextKey("rel"),
    from_ref: from?.reference_name || "",
    to_ref: to?.reference_name || "",
    join_type: rel.join_type || "MANY_TO_ONE",
    condition: rel.condition || "",
  };
}

function syncJsonFromDraft() {
  modelsJson.value = JSON.stringify(
    draftModels.value.map(({ _key: _k, _id: _i, ...rest }) => ({
      ...rest,
      columns: (rest.columns || []).map(({ _key: __k, ...col }) => col),
    })),
    null,
    2,
  );
}

function applyJsonToDraft() {
  const parsed = JSON.parse(modelsJson.value) as unknown;
  if (!Array.isArray(parsed)) throw new Error("模型须为 JSON 数组");
  draftModels.value = (parsed as GenbiModelIn[]).map((item) => ({
    _key: nextKey("model"),
    display_name: item.display_name || "",
    source_table_name: item.source_table_name || "",
    reference_name: item.reference_name || "",
    ref_sql: item.ref_sql ?? null,
    cached: item.cached === true,
    refresh_time: item.refresh_time ?? null,
    properties: item.properties ?? null,
    columns: (item.columns ?? []).map((col) => ({
      _key: nextKey("col"),
      display_name: col.display_name || "",
      source_column_name: col.source_column_name || "",
      column_type: col.column_type || "varchar",
      is_calculated: col.is_calculated === true,
      expression: col.expression ?? null,
      properties: col.properties ?? null,
    })),
  }));
  selectedKey.value = draftModels.value[0]?._key;
  draftRels.value = [];
}

async function load() {
  loading.value = true;
  try {
    const [modelsRes, relsRes] = await Promise.all([
      GenbiProjectAPI.listModels(props.projectId),
      GenbiProjectAPI.listRelationships(props.projectId),
    ]);
    const models = (modelsRes.data.data ?? []).map(modelFromApi);
    draftModels.value = models;
    draftRels.value = (relsRes.data.data ?? []).map((r) => relFromApi(r, models));
    selectedKey.value = models[0]?._key;
    syncJsonFromDraft();
  } finally {
    loading.value = false;
  }
}

function onSelectModel(row: DraftModel | undefined) {
  selectedKey.value = row?._key;
}

function addModel() {
  const model = emptyModel();
  draftModels.value.push(model);
  selectedKey.value = model._key;
}

function removeModel(index: number) {
  const removed = draftModels.value.splice(index, 1)[0];
  if (removed && selectedKey.value === removed._key) {
    selectedKey.value = draftModels.value[0]?._key;
  }
}

function addColumn() {
  selectedModel.value?.columns.push(emptyColumn());
}

function removeColumn(index: number) {
  selectedModel.value?.columns.splice(index, 1);
}

function addRelationship() {
  draftRels.value.push({
    _key: nextKey("rel"),
    from_ref: draftModels.value[0]?.reference_name || "",
    to_ref: draftModels.value[1]?.reference_name || "",
    join_type: "MANY_TO_ONE",
    condition: "",
  });
}

function toSyncPayload(): GenbiModelIn[] {
  return draftModels.value.map((model) => ({
    display_name: (model.display_name || "").trim(),
    source_table_name: (model.source_table_name || "").trim(),
    reference_name: (model.reference_name || "").trim(),
    ref_sql: model.ref_sql ?? null,
    cached: model.cached === true,
    refresh_time: model.refresh_time ?? null,
    properties: model.properties ?? null,
    columns: (model.columns || []).map((col) => ({
      display_name: (col.display_name || "").trim(),
      source_column_name: (col.source_column_name || "").trim(),
      column_type: col.column_type || "varchar",
      is_calculated: col.is_calculated === true,
      expression: col.expression ?? null,
      properties: col.properties ?? null,
    })),
  }));
}

async function saveAll() {
  if (showJson.value) {
    try {
      applyJsonToDraft();
    } catch {
      ElMessage.error("模型 JSON 无法解析");
      return;
    }
  }

  const models = toSyncPayload();
  if (!models.length) {
    ElMessage.error("至少需要一个模型");
    return;
  }
  for (const model of models) {
    if (!model.display_name || !model.source_table_name || !model.reference_name) {
      ElMessage.error("模型显示名 / 源表 / 引用名均不能为空");
      return;
    }
  }

  saving.value = true;
  try {
    const saved = await GenbiProjectAPI.syncModels(props.projectId, models);
    const savedModels = saved.data.data ?? [];
    const refToId = new Map(
      savedModels
        .filter((m) => m.reference_name && m.id)
        .map((m) => [m.reference_name as string, m.id as number]),
    );
    const relationships = draftRels.value
      .map((rel) => {
        const fromId = refToId.get(rel.from_ref);
        const toId = refToId.get(rel.to_ref);
        if (!fromId || !toId) return null;
        return {
          from_model_id: fromId,
          to_model_id: toId,
          join_type: rel.join_type || "MANY_TO_ONE",
          condition: rel.condition || null,
        };
      })
      .filter((item): item is NonNullable<typeof item> => item != null);

    await GenbiProjectAPI.syncRelationships(props.projectId, relationships);
    ElMessage.success("模型与关系已保存");
    emit("saved");
    await load();
  } finally {
    saving.value = false;
  }
}

watch(showJson, (jsonMode) => {
  if (jsonMode) syncJsonFromDraft();
  else {
    try {
      applyJsonToDraft();
    } catch {
      ElMessage.warning("JSON 无效，已保留结构化草稿");
      showJson.value = true;
    }
  }
});

watch(
  () => props.projectId,
  () => {
    void load();
  },
  { immediate: true },
);
</script>

<style scoped>
.genbi-modeling__toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.genbi-modeling__hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.genbi-modeling__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.genbi-modeling__layout {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) minmax(360px, 1.2fr);
  gap: 12px;
}

.genbi-modeling__card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-weight: 600;
}

.genbi-modeling__rels {
  margin-top: 12px;
}

@media (max-width: 1100px) {
  .genbi-modeling__layout {
    grid-template-columns: 1fr;
  }
}
</style>
