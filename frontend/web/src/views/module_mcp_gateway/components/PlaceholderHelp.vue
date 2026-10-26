<template>
  <ElCollapse v-model="activeNames" class="placeholder-help">
    <ElCollapseItem name="help">
      <template #title>
        <span class="placeholder-help__title">
          <ElIcon class="placeholder-help__icon"><InfoFilled /></ElIcon>
          {{ title }}
        </span>
      </template>

      <p class="placeholder-help__intro">{{ intro }}</p>

      <ElTable :data="variables" border size="small" class="placeholder-help__table">
        <ElTableColumn prop="name" label="变量" min-width="140" />
        <ElTableColumn prop="meaning" label="含义" min-width="160" />
        <ElTableColumn prop="source" label="来源" min-width="200" />
      </ElTable>

      <h4 class="placeholder-help__section">适用位置</h4>
      <ul class="placeholder-help__usage">
        <li v-for="(item, index) in usage" :key="index">{{ item }}</li>
      </ul>

      <h4 class="placeholder-help__section">示例</h4>
      <div v-for="(example, index) in examples" :key="index" class="placeholder-help__example">
        <p class="placeholder-help__caption">{{ example.caption }}</p>
        <pre class="placeholder-help__code">{{ example.code }}</pre>
      </div>
    </ElCollapseItem>
  </ElCollapse>
</template>

<script setup lang="ts">
import { InfoFilled } from "@element-plus/icons-vue";
import type { PlaceholderExample, PlaceholderVariableRow } from "./placeholderHelpContent";

defineOptions({ name: "McpGatewayPlaceholderHelp" });

withDefaults(
  defineProps<{
    title?: string;
    intro: string;
    variables: PlaceholderVariableRow[];
    usage: string[];
    examples: PlaceholderExample[];
  }>(),
  { title: "变量使用说明" },
);

const activeNames = ref<string[]>(["help"]);
</script>

<style scoped>
.placeholder-help {
  margin: 0 16px 12px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 8px;
}

.placeholder-help :deep(.el-collapse-item__header) {
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 500;
  background: var(--el-fill-color-light, #f5f7fa);
}

.placeholder-help :deep(.el-collapse-item__wrap) {
  border-top: 1px solid var(--el-border-color-lighter, #ebeef5);
}

.placeholder-help :deep(.el-collapse-item__content) {
  padding: 10px 12px 12px;
}

.placeholder-help__title {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.placeholder-help__icon {
  flex-shrink: 0;
}

.placeholder-help__intro {
  margin: 0 0 10px;
  color: var(--el-text-color-secondary, #909399);
  font-size: 13px;
  line-height: 1.6;
}

.placeholder-help__table :deep(.el-table__cell) {
  font-size: 12px;
}

.placeholder-help__section {
  margin: 12px 0 6px;
  font-size: 13px;
  font-weight: 600;
}

.placeholder-help__usage {
  margin: 0;
  padding-left: 18px;
  color: var(--el-text-color-regular, #606266);
  font-size: 13px;
  line-height: 1.6;
}

.placeholder-help__example {
  margin-top: 8px;
}

.placeholder-help__caption {
  margin: 0 0 4px;
  color: var(--el-text-color-secondary, #909399);
  font-size: 12px;
}

.placeholder-help__code {
  margin: 0;
  padding: 8px 10px;
  overflow-x: auto;
  border-radius: 6px;
  background: var(--el-fill-color, #f0f2f5);
  color: var(--el-text-color-regular, #606266);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
