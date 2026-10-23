<!-- 调用次数只读汇总接口。每个用户、每个工具一条。 -->
<template>
  <div class="flex flex-col relative last:mb-0">
    <ElCard shadow="hover">
      <template #header>
        <div class="flex items-center gap-2">
          <span class="font-medium">每个用户访问每个工具</span>
        </div>
      </template>
      <ElEmpty v-if="rows.length === 0" :image-size="80" description="暂无数据" />
      <div v-else class="flex flex-col gap-4">
        <div v-for="row in rows" :key="`${row.user_id}:${row.tool_name}`">
          <div class="mb-2 text-sm">
            用户 {{ row.user_id }} · {{ row.tool_name }} · {{ row.count }} 次 · {{ row.elapsed_ms }} ms ·
            {{ row.created_at }}
          </div>
          <ElProgress :percentage="percentage(row.count)" :stroke-width="16" text-inside />
        </div>
      </div>
    </ElCard>
  </div>
</template>

<script lang="ts" setup>
import CallLogAPI, { type CallLogAggregate } from "@/api/module_mcp_gateway/call_log";

defineOptions({ name: "McpGatewayCallLog" });

const rows = ref<CallLogAggregate[]>([]);

const maxCount = computed(() => Math.max(1, ...rows.value.map((row) => row.count || 0)));

function percentage(count: number) {
  return Math.min(100, Math.round((count / maxCount.value) * 100));
}

async function load() {
  try {
    const res = await CallLogAPI.aggregate();
    const payload = res.data?.data;
    rows.value = Array.isArray(payload) ? payload : [];
  } catch {
    rows.value = [];
  }
}

onMounted(load);
</script>
