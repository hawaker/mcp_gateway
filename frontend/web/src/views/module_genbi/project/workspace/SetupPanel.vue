<!-- Setup：入驻状态与建模入口（对齐 tiga GenbiSetup 流程，无自动导入时展示清单） -->
<template>
  <ElCard shadow="never" class="genbi-setup">
    <template #header>
      <div class="genbi-setup__head">
        <span>项目 Setup</span>
        <ElButton size="small" @click="emit('refresh')">刷新</ElButton>
      </div>
    </template>

    <ElDescriptions :column="2" border>
      <ElDescriptionsItem label="名称">{{ project.display_name }}</ElDescriptionsItem>
      <ElDescriptionsItem label="状态">{{ project.onboarding_status || "—" }}</ElDescriptionsItem>
      <ElDescriptionsItem label="语言">{{ project.language || "—" }}</ElDescriptionsItem>
      <ElDescriptionsItem label="数据源 ID">{{ project.datasource_id }}</ElDescriptionsItem>
      <ElDescriptionsItem label="MDL 模型数">{{ modelCount }}</ElDescriptionsItem>
      <ElDescriptionsItem label="项目 ID">{{ project.id }}</ElDescriptionsItem>
    </ElDescriptions>

    <ElAlert
      class="genbi-setup__hint"
      type="info"
      :closable="false"
      title="对齐 tiga 流程"
      description="数据源已在「数据源」菜单维护。此处检查入驻状态后进入 Modeling 编辑模型与列，再配置 Knowledge / Capabilities，最后 Deploy。"
    />

    <div class="genbi-setup__steps">
      <div
        v-for="step in steps"
        :key="step.key"
        class="genbi-setup__step"
        :class="{ 'is-done': step.done }"
      >
        <div class="genbi-setup__step-title">{{ step.title }}</div>
        <div class="genbi-setup__step-desc">{{ step.desc }}</div>
        <ElButton size="small" type="primary" plain @click="emit('goto', step.key)">
          {{ step.action }}
        </ElButton>
      </div>
    </div>

    <div class="genbi-setup__actions">
      <ElButton
        v-hasPerm="['module_genbi:project:update']"
        type="primary"
        :loading="saving"
        :disabled="modelCount < 1"
        @click="markModeling"
      >
        标记为 modeling
      </ElButton>
      <ElButton type="primary" @click="emit('goto', 'modeling')">进入 Modeling</ElButton>
    </div>
  </ElCard>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import GenbiProjectAPI, { type GenbiProjectTable } from "@/api/module_genbi/project";

defineOptions({ name: "GenbiSetupPanel", inheritAttrs: false });

const props = defineProps<{
  project: GenbiProjectTable;
  modelCount: number;
}>();

const emit = defineEmits<{
  refresh: [];
  goto: [tab: "modeling" | "knowledge" | "capabilities" | "deploy"];
}>();

const saving = ref(false);

const steps = computed(() => [
  {
    key: "modeling" as const,
    title: "1. Modeling",
    desc: props.modelCount > 0 ? `已有 ${props.modelCount} 个模型` : "尚未配置 MDL 模型",
    action: "编辑模型",
    done: props.modelCount > 0,
  },
  {
    key: "knowledge" as const,
    title: "2. Knowledge",
    desc: "指令 / 指标文档 / SQL 问答对",
    action: "配置知识",
    done: false,
  },
  {
    key: "capabilities" as const,
    title: "3. Capabilities",
    desc: "Agent 指令与工具配置",
    action: "配置能力",
    done: false,
  },
  {
    key: "deploy" as const,
    title: "4. Deploy",
    desc: props.project.onboarding_status === "deployed" ? "已部署" : "部署到 Wren / pgvector",
    action: "查看部署",
    done: props.project.onboarding_status === "deployed",
  },
]);

async function markModeling() {
  if (!props.project.id) return;
  saving.value = true;
  try {
    await GenbiProjectAPI.updateProject(props.project.id, { onboarding_status: "modeling" });
    ElMessage.success("已更新状态");
    emit("refresh");
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.genbi-setup__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.genbi-setup__hint {
  margin-top: 16px;
}

.genbi-setup__steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.genbi-setup__step {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 12px;
  background: var(--el-fill-color-blank);
}

.genbi-setup__step.is-done {
  border-color: var(--el-color-success-light-5);
}

.genbi-setup__step-title {
  font-weight: 600;
  margin-bottom: 6px;
}

.genbi-setup__step-desc {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin-bottom: 10px;
  min-height: 36px;
}

.genbi-setup__actions {
  margin-top: 16px;
  display: flex;
  gap: 8px;
}
</style>
