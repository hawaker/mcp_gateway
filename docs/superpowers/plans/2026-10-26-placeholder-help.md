# 鉴权 / REST 工具变量说明 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在鉴权与 REST 工具的新增/编辑对话框内，增加默认展开、可折叠的变量使用说明。

**Architecture:** 共享 `PlaceholderHelp.vue`（ElCollapse + 变量表 + 适用列表 + 示例），文案集中在 `placeholderHelpContent.ts` 导出鉴权版与 REST 版两套 props；两页对话框各挂一次组件。纯前端，无后端改动。

**Tech Stack:** Vue 3、Element Plus（`ElCollapse` / `ElTable`）、现有 `frontend/web` 模块结构。参考 `frontend/web/src/views/module_generator/gencode/components/FaGencodeHelpPanel.vue` 的折叠样式。

## Global Constraints

- Spec：`docs/superpowers/specs/2026-10-26-placeholder-help-design.md`
- 占位符只认 `{{system.xxx}}`、`{{user.uid}}`、`{{user.attr.xxx}}`、`{{token}}`；MCP 入参不能覆盖
- 找不到值时占位符原文保留
- 不改后端；不做点选插入；不做自动化 UI 测试
- 中文文案与现有鉴权说明语气一致
- 提交信息用英文 `feat:` / `docs:` 前缀，与近期仓库风格一致

---

## File Structure

```
frontend/web/src/views/module_mcp_gateway/components/
  PlaceholderHelp.vue          # 可折叠帮助面板（props 驱动）
  placeholderHelpContent.ts    # AUTH_PLACEHOLDER_HELP / REST_PLACEHOLDER_HELP
frontend/web/src/views/module_mcp_gateway/auth/index.vue       # 挂载鉴权版
frontend/web/src/views/module_mcp_gateway/rest_tool/index.vue  # 挂载 REST 版
```

---

### Task 1: PlaceholderHelp 组件与两套文案

**Files:**
- Create: `frontend/web/src/views/module_mcp_gateway/components/placeholderHelpContent.ts`
- Create: `frontend/web/src/views/module_mcp_gateway/components/PlaceholderHelp.vue`

**Interfaces:**
- Consumes: Element Plus `ElCollapse` / `ElCollapseItem` / `ElTable` / `ElTableColumn`；可选 `InfoFilled` 图标（与 FaGencodeHelpPanel 一致）
- Produces:
  - Types: `PlaceholderVariableRow`, `PlaceholderExample`, `PlaceholderHelpContent`
  - Constants: `AUTH_PLACEHOLDER_HELP`, `REST_PLACEHOLDER_HELP`
  - Component props: `title?`, `intro`, `variables`, `usage`, `examples`；默认展开 name=`help`

- [ ] **Step 1: 创建文案模块**

创建 `frontend/web/src/views/module_mcp_gateway/components/placeholderHelpContent.ts`：

```ts
export interface PlaceholderVariableRow {
  name: string;
  meaning: string;
  source: string;
}

export interface PlaceholderExample {
  caption: string;
  code: string;
}

export interface PlaceholderHelpContent {
  title: string;
  intro: string;
  variables: PlaceholderVariableRow[];
  usage: string[];
  examples: PlaceholderExample[];
}

const SHARED_INTRO =
  "语法使用双花括号，例如 {{user.uid}}。只认 {{system.键}}、{{user.uid}}、{{user.attr.键}}、{{token}}。值只来自业务系统参数、绑定标识/属性、业务 token；MCP 入参不能覆盖这些占位符。找不到对应值时，占位符原文保留，不报错清空。";

export const AUTH_PLACEHOLDER_HELP: PlaceholderHelpContent = {
  title: "变量使用说明",
  intro: SHARED_INTRO,
  variables: [
    {
      name: "{{system.xxx}}",
      meaning: "业务系统参数",
      source: "该系统配置里的 params",
    },
    {
      name: "{{user.uid}}",
      meaning: "当前调用用户在该系统的唯一标识",
      source: "绑定的 uid_value",
    },
    {
      name: "{{user.attr.xxx}}",
      meaning: "绑定上的可选属性",
      source: "系统声明的属性字段 + 绑定填值",
    },
    {
      name: "{{token}}",
      meaning: "业务 token",
      source: "换 token 的登录请求里一般拿不到；勿指望在鉴权请求里使用",
    },
  ],
  usage: [
    "地址：URL 可写占位符。",
    "取值规则：JSON 里 query / json / form 对象的值可写占位符（custom / basic）。",
    "fixed：系统自动 POST {uid_field: uid}，不必手写 {{user.uid}}。",
    "interactive：主要配验证页 URL 与回调取值规则；登录请求本身不走这些占位符换 token。",
  ],
  examples: [
    {
      caption: "custom 的取值规则片段",
      code: `{
  "query": { "userId": "{{user.uid}}" },
  "json": { "dept": "{{user.attr.dept}}", "appKey": "{{system.app_key}}" },
  "token_from": "json",
  "token_name": "access_token",
  "expires_seconds": 3600
}`,
    },
  ],
};

export const REST_PLACEHOLDER_HELP: PlaceholderHelpContent = {
  title: "变量使用说明",
  intro: SHARED_INTRO,
  variables: [
    {
      name: "{{system.xxx}}",
      meaning: "业务系统参数",
      source: "该系统配置里的 params",
    },
    {
      name: "{{user.uid}}",
      meaning: "当前调用用户在该系统的唯一标识",
      source: "绑定的 uid_value",
    },
    {
      name: "{{user.attr.xxx}}",
      meaning: "绑定上的可选属性",
      source: "系统声明的属性字段 + 绑定填值",
    },
    {
      name: "{{token}}",
      meaning: "业务 token",
      source: "调用业务接口时可用（鉴权成功后缓存中的 token）",
    },
  ],
  usage: [
    "请求头：JSON 的值可写占位符，常见写法 Authorization: Bearer {{token}}。",
    "也可配合「Token 位置 / Token 字段」由系统自动注入；勿与手写 {{token}} 重复塞两遍。",
    "接口地址里的 {参数名}（单花括号）来自 MCP 入参，与 {{...}} 不是同一套：先替换路径 {id} 等，再渲染 {{...}}。",
  ],
  examples: [
    {
      caption: "URL 路径参数（MCP 入参）",
      code: `/todos/{id}  +  {"id": 12}  →  /todos/12`,
    },
    {
      caption: "请求头",
      code: `{"Authorization": "Bearer {{token}}", "X-User": "{{user.uid}}"}`,
    },
  ],
};
```

- [ ] **Step 2: 创建 PlaceholderHelp.vue**

创建 `frontend/web/src/views/module_mcp_gateway/components/PlaceholderHelp.vue`：

```vue
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
```

说明：若项目对 `ref` 为自动导入，可不写 `import { ref } from "vue"`；若本地 lint 要求显式导入，加上 `import { ref } from "vue"`。

- [ ] **Step 3: 静态核对文案**

在仓库根目录或 frontend 目录确认文件存在且 TypeScript 可解析：

```bash
test -f frontend/web/src/views/module_mcp_gateway/components/PlaceholderHelp.vue \
  && test -f frontend/web/src/views/module_mcp_gateway/components/placeholderHelpContent.ts \
  && echo OK
```

Expected: `OK`

人工扫一眼：`AUTH_PLACEHOLDER_HELP` 的 `{{token}}` 来源写「登录请求里一般拿不到」；`REST_PLACEHOLDER_HELP` 写「调用时可用」，且 usage 含 `{参数}` vs `{{...}}`。

- [ ] **Step 4: Commit**

```bash
git add frontend/web/src/views/module_mcp_gateway/components/PlaceholderHelp.vue \
  frontend/web/src/views/module_mcp_gateway/components/placeholderHelpContent.ts
git commit -m "$(cat <<'EOF'
feat: add PlaceholderHelp panel and auth/REST copy

EOF
)"
```

---

### Task 2: 鉴权对话框挂载

**Files:**
- Modify: `frontend/web/src/views/module_mcp_gateway/auth/index.vue`

**Interfaces:**
- Consumes: `PlaceholderHelp` 组件；`AUTH_PLACEHOLDER_HELP`（`title` / `intro` / `variables` / `usage` / `examples`）
- Produces: 新增/修改鉴权对话框内默认展开的鉴权版说明

- [ ] **Step 1: 增加 import**

在 `<script setup>` 顶部现有 import 旁加入：

```ts
import PlaceholderHelp from "../components/PlaceholderHelp.vue";
import { AUTH_PLACEHOLDER_HELP } from "../components/placeholderHelpContent";
```

- [ ] **Step 2: 在对话框模板中挂载**

在 `auth/index.vue` 的 `FaDialog` 内，把现有结构改为（保留原有 `auth-note` 与 `FaForm`）：

```vue
      <p class="auth-note">同一业务系统同时只启用一条鉴权。保存为启用时，该系统其余配置会改为未启用。</p>
      <PlaceholderHelp
        :title="AUTH_PLACEHOLDER_HELP.title"
        :intro="AUTH_PLACEHOLDER_HELP.intro"
        :variables="AUTH_PLACEHOLDER_HELP.variables"
        :usage="AUTH_PLACEHOLDER_HELP.usage"
        :examples="AUTH_PLACEHOLDER_HELP.examples"
      />
      <FaForm
```

即：提示段下方、`FaForm` 上方。不要改方法说明对话框（时序图那个 `FaDialog`）。

- [ ] **Step 3: 手动验收**

启动或刷新前端后：

1. 打开 MCP 网关 → 业务鉴权 → 新增鉴权  
2. 确认表单上方有「变量使用说明」，默认展开，含变量表、适用位置、custom rule 示例  
3. 点击标题可折叠；再打开「修改鉴权」同样可见  

Expected: 鉴权版文案；`{{token}}` 行提示登录请求一般拿不到。

- [ ] **Step 4: Commit**

```bash
git add frontend/web/src/views/module_mcp_gateway/auth/index.vue
git commit -m "$(cat <<'EOF'
feat: show placeholder help in auth create/edit dialog

EOF
)"
```

---

### Task 3: REST 工具对话框挂载

**Files:**
- Modify: `frontend/web/src/views/module_mcp_gateway/rest_tool/index.vue`

**Interfaces:**
- Consumes: `PlaceholderHelp`；`REST_PLACEHOLDER_HELP`
- Produces: 新增/修改 REST 工具对话框内默认展开的 REST 版说明

- [ ] **Step 1: 增加 import**

在 `<script setup>` 现有 import 旁加入：

```ts
import PlaceholderHelp from "../components/PlaceholderHelp.vue";
import { REST_PLACEHOLDER_HELP } from "../components/placeholderHelpContent";
```

- [ ] **Step 2: 在对话框模板中挂载**

在 `rest_tool/index.vue` 的 `FaDialog` 内，`FaForm` **之前**插入（调试区 `section.rest-debug` 仍在 `FaForm` 之后）：

```vue
      <PlaceholderHelp
        :title="REST_PLACEHOLDER_HELP.title"
        :intro="REST_PLACEHOLDER_HELP.intro"
        :variables="REST_PLACEHOLDER_HELP.variables"
        :usage="REST_PLACEHOLDER_HELP.usage"
        :examples="REST_PLACEHOLDER_HELP.examples"
      />
      <FaForm
```

- [ ] **Step 3: 手动验收**

1. 打开 MCP 网关 → REST 工具 → 新增 REST 工具  
2. 确认「变量使用说明」在表单上方、调试区上方，默认展开  
3. 确认含 `{id}` 与 `{{token}}` 示例，以及勿与 Token 位置重复注入的提示  
4. 打开「修改 REST 工具」同样可见；可折叠  

Expected: REST 版文案；与鉴权页内容不同。

- [ ] **Step 4: Commit**

```bash
git add frontend/web/src/views/module_mcp_gateway/rest_tool/index.vue
git commit -m "$(cat <<'EOF'
feat: show placeholder help in REST tool create/edit dialog

EOF
)"
```

---

## Spec Coverage Checklist

| Spec 要求 | Task |
|-----------|------|
| 共享可折叠组件 + props | Task 1 |
| 鉴权 / REST 两套文案 | Task 1（content） |
| 默认展开、可折叠 | Task 1（`activeNames = ["help"]`） |
| 挂到鉴权对话框（note 下、FaForm 上） | Task 2 |
| 挂到 REST 对话框（FaForm 上、调试区上） | Task 3 |
| 四种变量、适用字段、示例 | Task 1 content |
| REST：`{参数}` vs `{{...}}`、Token 位置 | Task 1 `REST_PLACEHOLDER_HELP` |
| 不改后端 / 无 UI 自动化测试 | 全计划无后端与测试文件 |

## Self-Review Notes

- 无 TBD / 「类似 Task N」占位
- Props 名与 content 导出字段一致：`title` / `intro` / `variables` / `usage` / `examples`
- 纯展示，验证以手动验收为准（与 spec「不做自动化 UI 测试」一致）
