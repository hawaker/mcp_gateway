<!-- 发信记录。可按用户、MCP 组、用户组、途径、成败和时间筛选。列表不含 token 和密码。 -->
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

      <FaTable
        :loading="loading"
        :data="data"
        :columns="columns"
        :pagination="pagination"
        @pagination:size-change="handleSizeChange"
        @pagination:current-change="handleCurrentChange"
      />
    </ElCard>

    <FaDialog
      v-model="detailVisible"
      title="发信记录"
      width="560px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      form-mode="detail"
      confirm-text="关闭"
      @close="detailVisible = false"
      @confirm="detailVisible = false"
    >
      <FaForm
        v-model="detailForm"
        :items="detailItems"
        label-suffix=":"
        :label-width="100"
        label-position="right"
        :span="24"
        :show-reset="false"
        :show-submit="false"
        class="crud-dialog-art-form"
      />
    </FaDialog>
  </div>
</template>

<script setup lang="ts">
import MailAPI, { type MailLogPageQuery, type MailLogTable } from "@/api/module_mcp_gateway/mail";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { renderTableOperationCell, type TableOperationAction } from "@utils";

defineOptions({
  name: "McpGatewayMailLog",
  inheritAttrs: false,
});

const CHANNEL_OPTIONS = [
  { label: "MCP 组", value: "group" },
  { label: "用户组", value: "user_group" },
  { label: "用户", value: "user" },
] as const;

const OK_OPTIONS = [
  { label: "成功", value: true },
  { label: "失败", value: false },
] as const;

function channelText(value?: string) {
  return CHANNEL_OPTIONS.find((item) => item.value === value)?.label ?? value ?? "";
}

function okText(ok?: boolean) {
  return ok ? "成功" : "失败";
}

const showSearch = ref(true);
const searchForm = ref<MailLogPageQuery>({
  user_id: undefined,
  group_id: undefined,
  user_group_id: undefined,
  channel: undefined,
  ok: undefined,
  created_at_start: undefined,
  created_at_end: undefined,
});
const searchBarRef = ref();
const searchItems = computed<SearchFormItem[]>(() => [
  { label: "用户", key: "user_id", type: "input", placeholder: "用户编号", clearable: true, span: 6 },
  { label: "MCP 组", key: "group_id", type: "input", placeholder: "MCP 组编号", clearable: true, span: 6 },
  { label: "用户组", key: "user_group_id", type: "input", placeholder: "用户组编号", clearable: true, span: 6 },
  {
    label: "途径",
    key: "channel",
    type: "select",
    props: { placeholder: "请选择", options: CHANNEL_OPTIONS, clearable: true },
    span: 6,
  },
  {
    label: "结果",
    key: "ok",
    type: "select",
    props: { placeholder: "请选择", options: OK_OPTIONS, clearable: true },
    span: 6,
  },
  { label: "时间起", key: "created_at_start", type: "input", placeholder: "2026-10-24T00:00:00Z", clearable: true, span: 6 },
  { label: "时间止", key: "created_at_end", type: "input", placeholder: "2026-10-25T00:00:00Z", clearable: true, span: 6 },
]);

interface MailLogDetail {
  user_id?: number;
  group_id?: number;
  channel_text?: string;
  ok_text?: string;
  reason?: string;
  created_at?: string;
}

const detailVisible = ref(false);
const detailForm = ref<MailLogDetail>({});
const detailItems = computed<FormItem[]>(() => [
  { label: "用户", key: "user_id", type: "input", span: 24, props: { disabled: true } },
  { label: "MCP 组", key: "group_id", type: "input", span: 24, props: { disabled: true } },
  { label: "途径", key: "channel_text", type: "input", span: 24, props: { disabled: true } },
  { label: "结果", key: "ok_text", type: "input", span: 24, props: { disabled: true } },
  { label: "原因", key: "reason", type: "input", span: 24, props: { disabled: true } },
  { label: "时间", key: "created_at", type: "input", span: 24, props: { disabled: true } },
]);

function rowActions(row: MailLogTable): TableOperationAction[] {
  return [
    {
      key: "view",
      label: "查看",
      artType: "view",
      perm: "module_mcp_gateway:mail-log:query",
      run: () => openDetail(row),
    },
  ];
}

function openDetail(row: MailLogTable) {
  detailForm.value = {
    user_id: row.user_id,
    group_id: row.group_id,
    channel_text: channelText(row.channel),
    ok_text: okText(row.ok),
    reason: row.reason || "",
    created_at: row.created_at,
  };
  detailVisible.value = true;
}

const {
  columns,
  columnChecks,
  data,
  loading,
  pagination,
  replaceSearchParams,
  resetSearchParams,
  getData,
  handleSizeChange,
  handleCurrentChange,
  refreshData,
} = useTable({
  core: {
    apiFn: MailAPI.listMailLog,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "user_id", label: "用户", width: 90 },
      { prop: "group_id", label: "MCP 组", width: 100 },
      {
        prop: "channel",
        label: "途径",
        width: 110,
        formatter: (row: MailLogTable) => channelText(row.channel),
      },
      {
        prop: "ok",
        label: "结果",
        width: 88,
        formatter: (row: MailLogTable) => okText(row.ok),
      },
      { prop: "reason", label: "原因", minWidth: 160, showOverflowTooltip: true },
      { prop: "created_at", label: "时间", width: 180, showOverflowTooltip: true },
      {
        prop: "operation",
        label: "操作",
        width: 90,
        fixed: "right",
        align: "center",
        formatter: (row: MailLogTable) =>
          renderTableOperationCell(rowActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

async function handleSearch(params: MailLogPageQuery) {
  replaceSearchParams({
    user_id: params.user_id,
    group_id: params.group_id,
    user_group_id: params.user_group_id,
    channel: params.channel,
    ok: params.ok,
    created_at_start: params.created_at_start,
    created_at_end: params.created_at_end,
  });
  await getData();
}

async function onResetSearch() {
  searchForm.value = {
    user_id: undefined,
    group_id: undefined,
    user_group_id: undefined,
    channel: undefined,
    ok: undefined,
    created_at_start: undefined,
    created_at_end: undefined,
  };
  await resetSearchParams();
}
</script>
