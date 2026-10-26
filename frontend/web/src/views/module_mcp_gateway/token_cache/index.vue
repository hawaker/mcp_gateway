<!-- 业务 token 缓存：按用户和系统查看 Redis 里的令牌。没有记录时表格为空。 -->
<template>
  <div class="fa-full-height">
    <FaSearchBar
      v-show="showSearch"
      ref="searchBarRef"
      v-model="searchForm"
      :items="searchItems"
      :is-expand="false"
      :show-expand="false"
      :show-reset="true"
      :show-search="true"
      :include-audit="false"
      @search="handleSearch"
      @reset="onResetSearch"
    />

    <ElCard class="fa-table-card" :style="{ 'margin-top': showSearch ? '12px' : '0' }">
      <FaTableHeader
        v-model:columns="columnChecks"
        v-model:showSearchBar="showSearch"
        :loading="loading"
        @refresh="refreshData"
      />

      <FaTable :loading="loading" :data="data" :columns="columns" />
    </ElCard>
  </div>
</template>

<script setup lang="ts">
import BizTokenCacheAPI, { type BizTokenCacheQuery, type BizTokenCacheRow } from "@/api/module_mcp_gateway/token_cache";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import type { TableResponse } from "@utils";

defineOptions({
  name: "McpGatewayTokenCache",
  inheritAttrs: false,
});

function expiredText(expired?: boolean) {
  return expired ? "已过期" : "未过期";
}

function adaptTokenCacheResponse(response: { data?: { data?: unknown } }): TableResponse<BizTokenCacheRow> {
  const payload = response?.data?.data;
  const records = Array.isArray(payload) ? (payload as BizTokenCacheRow[]) : [];
  return {
    records,
    total: records.length,
    current: 1,
    size: Math.max(records.length, 1),
    has_next: false,
  };
}

const showSearch = ref(true);
const searchForm = ref<Partial<BizTokenCacheQuery>>({});
const searchBarRef = ref();
const searchItems = computed<SearchFormItem[]>(() => [
  {
    label: "用户",
    key: "user_id",
    type: "number",
    span: 6,
    props: { placeholder: "业务用户 ID", clearable: true, min: 1, step: 1, controls: false },
  },
  {
    label: "系统",
    key: "system_id",
    type: "number",
    span: 6,
    props: { placeholder: "业务系统 ID", clearable: true, min: 1, step: 1, controls: false },
  },
]);

function definedId(value: unknown): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value)) return undefined;
  return value;
}

const { columns, columnChecks, data, loading, replaceSearchParams, resetSearchParams, getData, refreshData } = useTable({
  core: {
    apiFn: BizTokenCacheAPI.listCache,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "user_id", label: "用户", width: 88 },
      { prop: "system_id", label: "系统", width: 88 },
      {
        prop: "var_keys",
        label: "变量键",
        minWidth: 160,
        showOverflowTooltip: true,
        formatter: (row: BizTokenCacheRow) => (row.var_keys ?? Object.keys(row.vars ?? {})).join(", "),
      },
      { prop: "access_token", label: "access_token", minWidth: 160, showOverflowTooltip: true },
      { prop: "expires_at", label: "过期时间", width: 180, showOverflowTooltip: true },
      {
        prop: "expired",
        label: "是否过期",
        width: 100,
        formatter: (row: BizTokenCacheRow) => expiredText(row.expired),
      },
    ],
  },
  transform: {
    responseAdapter: adaptTokenCacheResponse,
  },
});

async function handleSearch(params: Partial<BizTokenCacheQuery>) {
  const next: Partial<BizTokenCacheQuery> = {};
  const userId = definedId(params.user_id);
  const systemId = definedId(params.system_id);
  if (userId !== undefined) next.user_id = userId;
  if (systemId !== undefined) next.system_id = systemId;
  replaceSearchParams(next);
  await getData();
}

async function onResetSearch() {
  searchForm.value = {};
  await resetSearchParams();
}
</script>
