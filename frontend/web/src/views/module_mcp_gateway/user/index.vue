<!-- 业务用户与用户组：同一页维护两张目录，成员只追加、不替换已有组 -->
<template>
  <div class="fa-full-height">
    <ElTabs v-model="activeTab" class="fa-full-height">
      <ElTabPane label="业务用户" name="user" class="fa-full-height">
        <FaSearchBar
          v-show="showUserSearch"
          ref="userSearchBarRef"
          v-model="userSearchForm"
          :items="userSearchItems"
          :is-expand="false"
          :show-expand="false"
          :show-reset="true"
          :show-search="true"
          @search="handleUserSearch"
          @reset="onResetUserSearch"
        />

        <ElCard class="fa-table-card" :style="{ 'margin-top': showUserSearch ? '12px' : '0' }">
          <FaTableHeader
            v-model:columns="userColumnChecks"
            v-model:showSearchBar="showUserSearch"
            :loading="userLoading"
            @refresh="refreshUserData"
          >
            <template #left>
              <FaTableHeaderLeft
                :perm-create="['module_mcp_gateway:biz-user:create']"
                :create-loading="userCreateLoading"
                @add="handleAddUser"
              />
            </template>
          </FaTableHeader>

          <FaTable
            :loading="userLoading"
            :data="userData"
            :columns="userColumns"
            :pagination="userPagination"
            @pagination:size-change="handleUserSizeChange"
            @pagination:current-change="handleUserCurrentChange"
          />
        </ElCard>
      </ElTabPane>

      <ElTabPane label="用户组" name="group">
        <FaSearchBar
          v-show="showGroupSearch"
          ref="groupSearchBarRef"
          v-model="groupSearchForm"
          :items="groupSearchItems"
          :is-expand="false"
          :show-expand="false"
          :show-reset="true"
          :show-search="true"
          @search="handleGroupSearch"
          @reset="onResetGroupSearch"
        />

        <ElCard class="fa-table-card" :style="{ 'margin-top': showGroupSearch ? '12px' : '0' }">
          <FaTableHeader
            v-model:columns="groupColumnChecks"
            v-model:showSearchBar="showGroupSearch"
            :loading="groupLoading"
            @refresh="refreshGroupData"
          >
            <template #left>
              <FaTableHeaderLeft
                :perm-create="['module_mcp_gateway:biz-user-group:create']"
                :create-loading="groupCreateLoading"
                @add="handleAddGroup"
              />
            </template>
          </FaTableHeader>

          <FaTable
            :loading="groupLoading"
            :data="groupData"
            :columns="groupColumns"
            :pagination="groupPagination"
            @pagination:size-change="handleGroupSizeChange"
            @pagination:current-change="handleGroupCurrentChange"
          />
        </ElCard>
      </ElTabPane>
    </ElTabs>

    <FaDialog
      v-model="userDialogVisible.visible"
      :title="userDialogVisible.title"
      width="640px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      :form-mode="userDialogVisible.type"
      :confirm-loading="userSubmitLoading"
      @cancel="handleCloseUserDialog"
      @close="handleCloseUserDialog"
      @confirm="handleUserSubmit()"
    >
      <FaForm
        :key="userFormRenderKey"
        ref="userFormRef"
        v-model="userFormData"
        :items="userDialogFormItems"
        :rules="userRules"
        label-suffix=":"
        :label-width="100"
        label-position="right"
        :span="24"
        :gutter="16"
        :show-reset="false"
        :show-submit="false"
        class="crud-dialog-art-form"
      />
    </FaDialog>

    <FaDialog
      v-model="groupDialogVisible.visible"
      :title="groupDialogVisible.title"
      width="640px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      :form-mode="groupDialogVisible.type"
      :confirm-loading="groupSubmitLoading"
      @cancel="handleCloseGroupDialog"
      @close="handleCloseGroupDialog"
      @confirm="handleGroupSubmit()"
    >
      <FaForm
        :key="groupFormRenderKey"
        ref="groupFormRef"
        v-model="groupFormData"
        :items="groupDialogFormItems"
        :rules="groupRules"
        label-suffix=":"
        :label-width="100"
        label-position="right"
        :span="24"
        :gutter="16"
        :show-reset="false"
        :show-submit="false"
        class="crud-dialog-art-form"
      />
    </FaDialog>

    <FaDialog
      v-model="memberDialogVisible"
      title="添加组成员"
      width="520px"
      dialog-class="crud-embed-dialog"
      modal-class="crud-embed-dialog"
      :confirm-loading="memberSubmitting"
      @cancel="memberDialogVisible = false"
      @close="memberDialogVisible = false"
      @confirm="submitMembers"
    >
      <ElSelect
        v-model="memberUserIds"
        multiple
        filterable
        placeholder="选择业务用户"
        style="width: 100%"
      >
        <ElOption
          v-for="user in memberUserOptions"
          :key="user.id"
          :label="memberUserLabel(user)"
          :value="user.id!"
        />
      </ElSelect>
    </FaDialog>
  </div>
</template>

<script setup lang="ts">
import BizUserAPI, {
  type BizUserForm,
  type BizUserGroupForm,
  type BizUserGroupPageQuery,
  type BizUserGroupTable,
  type BizUserPageQuery,
  type BizUserTable,
} from "@/api/module_mcp_gateway/user";
import type { FormItem } from "@/components/forms/fa-form/index.vue";
import type { SearchFormItem } from "@/components/forms/fa-search-bar/index.vue";
import FaForm from "@/components/forms/fa-form/index.vue";
import FaTableHeader from "@/components/tables/fa-table-header/index.vue";
import { ElMessage } from "element-plus";
import { renderTableOperationCell, type TableOperationAction } from "@utils";

defineOptions({
  name: "McpGatewayBizUser",
  inheritAttrs: false,
});

const activeTab = ref("user");

const ENABLED_OPTIONS = [
  { label: "启用", value: true },
  { label: "停用", value: false },
] as const;

function enabledText(enabled?: boolean) {
  return enabled === false ? "停用" : "启用";
}

const showUserSearch = ref(true);
const userSearchForm = ref<BizUserPageQuery>({ name: undefined, enabled: undefined });
const userSearchBarRef = ref();
const userSearchItems = computed<SearchFormItem[]>(() => [
  {
    label: "姓名",
    key: "name",
    type: "input",
    placeholder: "请输入姓名",
    clearable: true,
    span: 6,
  },
  {
    label: "启用",
    key: "enabled",
    type: "select",
    props: { placeholder: "请选择", options: ENABLED_OPTIONS, clearable: true },
    span: 6,
  },
]);

const userCreateLoading = ref(false);
const {
  columns: userColumns,
  columnChecks: userColumnChecks,
  data: userData,
  loading: userLoading,
  pagination: userPagination,
  replaceSearchParams: replaceUserSearchParams,
  resetSearchParams: resetUserSearchParams,
  getData: getUserData,
  handleSizeChange: handleUserSizeChange,
  handleCurrentChange: handleUserCurrentChange,
  refreshData: refreshUserData,
  refreshCreate: refreshUserCreate,
} = useTable({
  core: {
    apiFn: BizUserAPI.listUser,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "name", label: "姓名", minWidth: 120, showOverflowTooltip: true },
      { prop: "nickname", label: "昵称", minWidth: 100, showOverflowTooltip: true },
      { prop: "email", label: "邮箱", minWidth: 180, showOverflowTooltip: true },
      { prop: "mobile", label: "手机号", minWidth: 140, showOverflowTooltip: true },
      {
        prop: "enabled",
        label: "启用",
        width: 88,
        formatter: (row: BizUserTable) => enabledText(row.enabled),
      },
      { prop: "created_time", label: "创建时间", width: 168, showOverflowTooltip: true },
    ],
  },
});

const userFormData = ref<BizUserForm>({
  id: undefined,
  name: "",
  email: "",
  mobile: "",
  nickname: "",
  enabled: true,
});
const userInitialForm: BizUserForm = {
  id: undefined,
  name: "",
  email: "",
  mobile: "",
  nickname: "",
  enabled: true,
};
const { dialogVisible: userDialogVisible } = useCrudDialog();
const userFormRef = ref<InstanceType<typeof FaForm> | null>(null);
const userFormRenderKey = ref(0);
const userRules = reactive({
  name: [{ required: true, message: "请输入姓名", trigger: "blur" }],
});
const userDialogFormItems = computed<FormItem[]>(() => [
  { label: "姓名", key: "name", type: "input", span: 24, props: { placeholder: "请输入姓名", maxlength: 64 } },
  { label: "昵称", key: "nickname", type: "input", span: 24, props: { placeholder: "请输入昵称", maxlength: 64 } },
  { label: "邮箱", key: "email", type: "input", span: 24, props: { placeholder: "请输入邮箱", maxlength: 128 } },
  { label: "手机号", key: "mobile", type: "input", span: 24, props: { placeholder: "请输入手机号", maxlength: 20 } },
  { label: "启用", key: "enabled", type: "switch", span: 24 },
]);
const {
  submitLoading: userSubmitLoading,
  handleCloseDialog: handleCloseUserDialog,
  handleOpenDialog: handleOpenUserDialog,
  handleSubmit: handleUserSubmit,
} = useCrudForm<BizUserForm>({
  formData: userFormData,
  initialFormData: userInitialForm,
  dialogVisible: userDialogVisible,
  dataFormRef: userFormRef,
  formRenderKey: userFormRenderKey,
  createApi: BizUserAPI.createUser,
  titles: { create: "新增业务用户" },
  onCreateSuccess: async () => {
    await refreshUserCreate();
  },
});

async function handleAddUser() {
  userCreateLoading.value = true;
  try {
    await handleOpenUserDialog("create");
  } finally {
    userCreateLoading.value = false;
  }
}

async function handleUserSearch(params: BizUserPageQuery) {
  replaceUserSearchParams({ name: params.name, enabled: params.enabled });
  await getUserData();
}

async function onResetUserSearch() {
  userSearchForm.value = { name: undefined, enabled: undefined };
  await resetUserSearchParams();
}

const showGroupSearch = ref(true);
const groupSearchForm = ref<BizUserGroupPageQuery>({ name: undefined, enabled: undefined });
const groupSearchBarRef = ref();
const groupSearchItems = computed<SearchFormItem[]>(() => [
  {
    label: "组名",
    key: "name",
    type: "input",
    placeholder: "请输入组名",
    clearable: true,
    span: 6,
  },
  {
    label: "启用",
    key: "enabled",
    type: "select",
    props: { placeholder: "请选择", options: ENABLED_OPTIONS, clearable: true },
    span: 6,
  },
]);

const groupCreateLoading = ref(false);

function groupRowActions(row: BizUserGroupTable): TableOperationAction[] {
  return [
    {
      key: "members",
      label: "成员",
      artType: "edit",
      perm: "module_mcp_gateway:biz-user-group:update",
      run: () => void openMemberDialog(row),
    },
  ];
}

const {
  columns: groupColumns,
  columnChecks: groupColumnChecks,
  data: groupData,
  loading: groupLoading,
  pagination: groupPagination,
  replaceSearchParams: replaceGroupSearchParams,
  resetSearchParams: resetGroupSearchParams,
  getData: getGroupData,
  handleSizeChange: handleGroupSizeChange,
  handleCurrentChange: handleGroupCurrentChange,
  refreshData: refreshGroupData,
  refreshCreate: refreshGroupCreate,
} = useTable({
  core: {
    apiFn: BizUserAPI.listGroup,
    apiParams: { page_no: 1, page_size: 10 },
    columnsFactory: () => [
      { type: "globalIndex", width: 56, label: "序号" },
      { prop: "name", label: "组名", minWidth: 140, showOverflowTooltip: true },
      {
        prop: "enabled",
        label: "启用",
        width: 88,
        formatter: (row: BizUserGroupTable) => enabledText(row.enabled),
      },
      { prop: "created_time", label: "创建时间", width: 168, showOverflowTooltip: true },
      {
        prop: "operation",
        label: "操作",
        width: 120,
        fixed: "right",
        align: "center",
        formatter: (row: BizUserGroupTable) =>
          renderTableOperationCell(groupRowActions(row), {
            wrapperClass: "inline-flex flex-wrap items-center justify-end gap-1 align-middle",
          }),
      },
    ],
  },
});

const groupFormData = ref<BizUserGroupForm>({ id: undefined, name: "", enabled: true });
const groupInitialForm: BizUserGroupForm = { id: undefined, name: "", enabled: true };
const { dialogVisible: groupDialogVisible } = useCrudDialog();
const groupFormRef = ref<InstanceType<typeof FaForm> | null>(null);
const groupFormRenderKey = ref(0);
const groupRules = reactive({
  name: [{ required: true, message: "请输入组名", trigger: "blur" }],
});
const groupDialogFormItems = computed<FormItem[]>(() => [
  { label: "组名", key: "name", type: "input", span: 24, props: { placeholder: "请输入组名", maxlength: 64 } },
  { label: "启用", key: "enabled", type: "switch", span: 24 },
]);
const {
  submitLoading: groupSubmitLoading,
  handleCloseDialog: handleCloseGroupDialog,
  handleOpenDialog: handleOpenGroupDialog,
  handleSubmit: handleGroupSubmit,
} = useCrudForm<BizUserGroupForm>({
  formData: groupFormData,
  initialFormData: groupInitialForm,
  dialogVisible: groupDialogVisible,
  dataFormRef: groupFormRef,
  formRenderKey: groupFormRenderKey,
  createApi: BizUserAPI.createGroup,
  titles: { create: "新增用户组" },
  onCreateSuccess: async () => {
    await refreshGroupCreate();
  },
});

async function handleAddGroup() {
  groupCreateLoading.value = true;
  try {
    await handleOpenGroupDialog("create");
  } finally {
    groupCreateLoading.value = false;
  }
}

async function handleGroupSearch(params: BizUserGroupPageQuery) {
  replaceGroupSearchParams({ name: params.name, enabled: params.enabled });
  await getGroupData();
}

async function onResetGroupSearch() {
  groupSearchForm.value = { name: undefined, enabled: undefined };
  await resetGroupSearchParams();
}

const memberDialogVisible = ref(false);
const memberSubmitting = ref(false);
const memberGroupId = ref<number>();
const memberUserIds = ref<number[]>([]);
const memberUserOptions = ref<BizUserTable[]>([]);

function memberUserLabel(user: BizUserTable) {
  const nickname = user.nickname ? `（${user.nickname}）` : "";
  return `${user.name ?? ""}${nickname}`;
}

async function openMemberDialog(row: BizUserGroupTable) {
  if (!row.id) return;
  memberGroupId.value = row.id;
  memberUserIds.value = [];
  const response = await BizUserAPI.listUser({ page_no: 1, page_size: 100 });
  memberUserOptions.value = response.data.data?.items ?? [];
  memberDialogVisible.value = true;
}

async function submitMembers() {
  if (!memberGroupId.value) return;
  if (memberUserIds.value.length === 0) {
    ElMessage.warning("请选择业务用户");
    return;
  }
  memberSubmitting.value = true;
  try {
    await BizUserAPI.addGroupMembers(memberGroupId.value, memberUserIds.value);
    memberDialogVisible.value = false;
    memberUserIds.value = [];
  } finally {
    memberSubmitting.value = false;
  }
}
</script>
