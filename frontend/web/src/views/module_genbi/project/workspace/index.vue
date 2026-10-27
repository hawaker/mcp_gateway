<!-- GenBI 项目工作台：Setup → Modeling → Knowledge → Capabilities → Deploy -->
<template>
  <div class="genbi-workspace fa-full-height">
    <div class="genbi-workspace__header">
      <div class="genbi-workspace__title">
        <ElButton text type="primary" @click="emit('back')">
          <ElIcon class="mr-1"><ArrowLeft /></ElIcon>
          返回列表
        </ElButton>
        <span class="genbi-workspace__name">{{ project?.display_name || `项目 #${projectId}` }}</span>
        <ElTag size="small" type="info">{{ project?.onboarding_status || "—" }}</ElTag>
      </div>
    </div>

    <ElTabs v-model="activeTab" class="genbi-workspace__tabs" @tab-change="onTabChange">
      <ElTabPane label="Setup" name="setup" />
      <ElTabPane label="Modeling" name="modeling" />
      <ElTabPane label="Knowledge" name="knowledge" />
      <ElTabPane label="Capabilities" name="capabilities" />
      <ElTabPane label="Deploy" name="deploy" />
    </ElTabs>

    <div v-loading="loading" class="genbi-workspace__body">
      <SetupPanel
        v-if="activeTab === 'setup' && project"
        :project="project"
        :model-count="modelCount"
        @refresh="reload"
        @goto="activeTab = $event"
      />
      <ModelingPanel
        v-else-if="activeTab === 'modeling'"
        :project-id="projectId"
        @saved="reload"
      />
      <KnowledgePanel
        v-else-if="activeTab === 'knowledge'"
        :project-id="projectId"
      />
      <CapabilitiesPanel
        v-else-if="activeTab === 'capabilities'"
        :project-id="projectId"
      />
      <DeployPanel
        v-else-if="activeTab === 'deploy' && project"
        :project-id="projectId"
        :project="project"
        @deployed="reload"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import GenbiProjectAPI, { type GenbiProjectTable } from "@/api/module_genbi/project";
import CapabilitiesPanel from "./CapabilitiesPanel.vue";
import DeployPanel from "./DeployPanel.vue";
import KnowledgePanel from "./KnowledgePanel.vue";
import ModelingPanel from "./ModelingPanel.vue";
import SetupPanel from "./SetupPanel.vue";

defineOptions({ name: "GenbiProjectWorkspace", inheritAttrs: false });

const props = defineProps<{ projectId: number; initialTab?: string }>();
const emit = defineEmits<{ back: [] }>();

type WorkspaceTab = "setup" | "modeling" | "knowledge" | "capabilities" | "deploy";

const loading = ref(false);
const project = ref<GenbiProjectTable>();
const modelCount = ref(0);
const activeTab = ref<WorkspaceTab>((props.initialTab as WorkspaceTab) || "setup");

async function reload() {
  loading.value = true;
  try {
    const [detailRes, modelsRes] = await Promise.all([
      GenbiProjectAPI.detailProject(props.projectId),
      GenbiProjectAPI.listModels(props.projectId),
    ]);
    project.value = detailRes.data.data;
    modelCount.value = modelsRes.data.data?.length ?? 0;
  } catch (e: unknown) {
    ElMessage.error((e as Error)?.message || "加载项目失败");
  } finally {
    loading.value = false;
  }
}

function onTabChange() {
  /* keep tab; panels load themselves */
}

watch(
  () => props.projectId,
  () => {
    void reload();
  },
  { immediate: true },
);
</script>

<style scoped>
.genbi-workspace {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.genbi-workspace__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.genbi-workspace__title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.genbi-workspace__name {
  font-size: 16px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.genbi-workspace__tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.genbi-workspace__body {
  flex: 1;
  min-height: 0;
  margin-top: 12px;
  overflow: auto;
}

.mr-1 {
  margin-right: 4px;
}
</style>
