<!-- Capabilities：Agent profile（指令 / 工具），对齐 tiga GenbiAgentCapabilities 精简版 -->
<template>
  <ElCard v-loading="loading" shadow="never" class="genbi-caps">
    <template #header>
      <div class="genbi-caps__head">
        <span>Agent Capabilities</span>
        <ElButton
          v-hasPerm="['module_genbi:project:update']"
          type="primary"
          size="small"
          :loading="saving"
          @click="save"
        >
          保存
        </ElButton>
      </div>
    </template>

    <ElAlert
      type="info"
      :closable="false"
      class="genbi-caps__hint"
      title="配置写入项目 agent_profile"
      description="完整 MCP/Skills 扩展面板未移植；此处维护 tiga 同名字段：instructions、tools_config、virtual_agent_id。"
    />

    <ElForm label-width="120px" class="genbi-caps__form">
      <ElFormItem label="Virtual Agent ID">
        <ElInput v-model="form.virtual_agent_id" placeholder="可选" />
      </ElFormItem>
      <ElFormItem label="系统指令">
        <ElInput
          v-model="instructionsText"
          type="textarea"
          :rows="8"
          placeholder="每行一条指令"
        />
      </ElFormItem>
      <ElFormItem label="工具（tools）">
        <ElSelect
          v-model="toolNames"
          multiple
          filterable
          allow-create
          default-first-option
          placeholder="输入工具名后回车"
          style="width: 100%"
        />
      </ElFormItem>
      <ElFormItem label="MCP / Skills">
        <ElInput
          v-model="extensionsJson"
          type="textarea"
          :rows="8"
          placeholder='{"mcp_config":[],"skills_config":{}}'
        />
      </ElFormItem>
    </ElForm>
  </ElCard>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import GenbiProjectAPI, { type GenbiAgentProfile } from "@/api/module_genbi/project";

defineOptions({ name: "GenbiCapabilitiesPanel", inheritAttrs: false });

const props = defineProps<{ projectId: number }>();

const loading = ref(false);
const saving = ref(false);
const form = ref<GenbiAgentProfile>({
  instructions: [],
  tools_config: [],
  mcp_config: [],
  skills_config: {},
  knowledge_config: {},
  virtual_agent_id: "",
});
const instructionsText = ref("");
const toolNames = ref<string[]>([]);
const extensionsJson = ref('{"mcp_config":[],"skills_config":{}}');

function toolNameOf(entry: string | { name: string }) {
  return typeof entry === "string" ? entry : entry?.name || "";
}

async function load() {
  loading.value = true;
  try {
    const res = await GenbiProjectAPI.getAgentProfile(props.projectId);
    const profile = res.data.data;
    form.value = {
      llm_model_id: profile?.llm_model_id ?? null,
      instructions: profile?.instructions ?? [],
      tools_config: profile?.tools_config ?? [],
      mcp_config: profile?.mcp_config ?? [],
      skills_config: profile?.skills_config ?? {},
      knowledge_config: profile?.knowledge_config ?? {},
      virtual_agent_id: profile?.virtual_agent_id || "",
    };
    instructionsText.value = (form.value.instructions || []).join("\n");
    toolNames.value = (form.value.tools_config || [])
      .map(toolNameOf)
      .filter(Boolean);
    extensionsJson.value = JSON.stringify(
      {
        mcp_config: form.value.mcp_config || [],
        skills_config: form.value.skills_config || {},
        knowledge_config: form.value.knowledge_config || {},
      },
      null,
      2,
    );
  } finally {
    loading.value = false;
  }
}

async function save() {
  let extensions: {
    mcp_config?: unknown[];
    skills_config?: Record<string, unknown>;
    knowledge_config?: Record<string, unknown>;
  };
  try {
    extensions = JSON.parse(extensionsJson.value) as typeof extensions;
  } catch {
    ElMessage.error("MCP / Skills JSON 无法解析");
    return;
  }

  saving.value = true;
  try {
    await GenbiProjectAPI.patchAgentProfile(props.projectId, {
      virtual_agent_id: form.value.virtual_agent_id || "",
      instructions: instructionsText.value
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      tools_config: toolNames.value.filter(Boolean).map((name) => ({ name })),
      mcp_config: Array.isArray(extensions.mcp_config) ? extensions.mcp_config : [],
      skills_config: extensions.skills_config || {},
      knowledge_config: extensions.knowledge_config || {},
    });
    ElMessage.success("Capabilities 已保存");
    await load();
  } finally {
    saving.value = false;
  }
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
.genbi-caps__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.genbi-caps__hint {
  margin-bottom: 16px;
}

.genbi-caps__form {
  max-width: 880px;
}
</style>
