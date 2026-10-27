<!-- Deploy：部署状态与日志 -->
<template>
  <div v-loading="loading" class="genbi-deploy">
    <ElCard shadow="never">
      <template #header>
        <div class="genbi-deploy__head">
          <span>部署状态</span>
          <div class="genbi-deploy__actions">
            <ElButton size="small" @click="load">刷新</ElButton>
            <ElButton
              v-hasPerm="['module_genbi:project:update']"
              type="primary"
              size="small"
              :loading="deploying"
              @click="deploy(false)"
            >
              部署
            </ElButton>
            <ElButton
              v-hasPerm="['module_genbi:project:update']"
              size="small"
              :loading="deploying"
              @click="deploy(true)"
            >
              强制部署
            </ElButton>
          </div>
        </div>
      </template>

      <ElDescriptions :column="2" border>
        <ElDescriptionsItem label="项目">{{ project.display_name }}</ElDescriptionsItem>
        <ElDescriptionsItem label="入驻状态">{{ project.onboarding_status }}</ElDescriptionsItem>
        <ElDescriptionsItem label="最近部署">
          <template v-if="latest">
            <ElTag :type="statusType(latest.status)" size="small">{{ latest.status }}</ElTag>
            <span class="genbi-deploy__meta">{{ latest.stage || "—" }} · {{ latest.deployed_at || "—" }}</span>
          </template>
          <span v-else>—</span>
        </ElDescriptionsItem>
        <ElDescriptionsItem label="MDL Hash">{{ latest?.mdl_hash || "—" }}</ElDescriptionsItem>
      </ElDescriptions>

      <ElAlert
        v-if="latest?.error"
        class="genbi-deploy__error"
        type="error"
        :closable="false"
        :title="latest.error"
      />
    </ElCard>

    <ElCard shadow="never" class="genbi-deploy__logs">
      <template #header>部署日志</template>
      <ElTable :data="logs" size="small">
        <ElTableColumn prop="status" label="状态" width="100" />
        <ElTableColumn prop="stage" label="阶段" width="100" />
        <ElTableColumn prop="mdl_hash" label="MDL Hash" min-width="160" show-overflow-tooltip />
        <ElTableColumn prop="deployed_at" label="时间" width="170" show-overflow-tooltip />
        <ElTableColumn prop="error" label="错误" min-width="200" show-overflow-tooltip />
      </ElTable>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import GenbiProjectAPI, {
  type GenbiDeployOut,
  type GenbiProjectTable,
} from "@/api/module_genbi/project";

defineOptions({ name: "GenbiDeployPanel", inheritAttrs: false });

const props = defineProps<{
  projectId: number;
  project: GenbiProjectTable;
}>();
const emit = defineEmits<{ deployed: [] }>();

const loading = ref(false);
const deploying = ref(false);
const logs = ref<GenbiDeployOut[]>([]);

const latest = computed(() => logs.value[0]);

function statusType(status?: string) {
  if (status === "success") return "success";
  if (status === "failed") return "danger";
  return "info";
}

async function load() {
  loading.value = true;
  try {
    const res = await GenbiProjectAPI.listDeployLogs(props.projectId, 20);
    logs.value = res.data.data ?? [];
  } finally {
    loading.value = false;
  }
}

async function deploy(force: boolean) {
  try {
    await ElMessageBox.confirm(
      force ? "确认强制重新部署？" : `确认部署项目「${props.project.display_name || props.projectId}」？`,
      "部署",
      { type: "warning", confirmButtonText: "部署", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  deploying.value = true;
  try {
    const res = await GenbiProjectAPI.deploy(props.projectId, force);
    const result = res.data.data;
    if (result?.error) {
      ElMessage.error(result.error);
    } else {
      ElMessage.success(`部署完成：${result?.status || "ok"}`);
    }
    emit("deployed");
    await load();
  } finally {
    deploying.value = false;
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
.genbi-deploy__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.genbi-deploy__actions {
  display: flex;
  gap: 8px;
}

.genbi-deploy__meta {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.genbi-deploy__error {
  margin-top: 12px;
}

.genbi-deploy__logs {
  margin-top: 12px;
}
</style>
