<template>
  <div class="capture-rows">
    <div class="capture-rows__help">
      <p>登录响应里按「来源 + path」取出值，写入缓存后可用 <code>{{ "{{auth.变量名}}" }}</code>。</p>
      <ul>
        <li>
          <strong>json</strong>：path 填点号路径。例响应
          <code>{"data":{"token":"abc"}}</code> → path 填
          <code>data.token</code>；数组下标如 <code>items.0.id</code>。
        </li>
        <li>
          <strong>header</strong>：path 填响应头名，如 <code>X-Token</code>、<code>Authorization</code>（会去掉
          <code>Bearer </code> 前缀）。读 Cookie 时 path 填
          <code>Set-Cookie</code>，并在取值规则 JSON 里加
          <code>"cookie_name": "sid"</code>。
        </li>
        <li>
          <strong>form</strong>：path 填表单字段名。例正文
          <code>access_token=abc&amp;expires_in=60</code> → path 填
          <code>access_token</code>。
        </li>
        <li>
          <strong>text</strong>：整段响应正文就是值，path 可留空。
        </li>
        <li>
          <strong>regex</strong>：path 填正则，只用<strong>第一个捕获组</strong>。例正文
          <code>token="abc"</code> → path 填
          <code>token="([^"]+)"</code>。
        </li>
      </ul>
    </div>

    <div v-for="(row, index) in modelValue" :key="index" class="flex gap-2 items-center flex-wrap mb-2">
      <ElInput v-model="row.name" placeholder="变量名，如 access_token" class="!w-40" />
      <ElSelect v-model="row.from" placeholder="来源" class="!w-28">
        <ElOption v-for="opt in FROM_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
      </ElSelect>
      <ElInput
        v-model="row.path"
        :placeholder="pathPlaceholder(row.from)"
        :disabled="row.from === 'text'"
        class="!flex-1 min-w-40"
      />
      <ElButton text type="danger" @click="remove(index)">删除</ElButton>
    </div>
    <ElButton plain @click="add">{{ addLabel }}</ElButton>
  </div>
</template>

<script setup lang="ts">
export interface CaptureRow {
  name: string;
  from: string;
  path: string;
}

const FROM_OPTIONS = [
  { label: "json", value: "json" },
  { label: "header", value: "header" },
  { label: "form", value: "form" },
  { label: "text", value: "text" },
  { label: "regex", value: "regex" },
] as const;

const props = withDefaults(
  defineProps<{ modelValue: CaptureRow[]; addLabel?: string }>(),
  { addLabel: "添加变量" },
);
const emit = defineEmits<{ "update:modelValue": [CaptureRow[]] }>();

function pathPlaceholder(from: string) {
  switch (from) {
    case "json":
      return "例 data.token 或 data.items.0.id";
    case "header":
      return "例 X-Token 或 Authorization";
    case "form":
      return "例 access_token";
    case "regex":
      return '例 token="([^"]+)"';
    case "text":
      return "整段正文，无需填写";
    default:
      return "path / 字段 / 正则";
  }
}

function emptyRow(): CaptureRow {
  return { name: "", from: "json", path: "" };
}

function add() {
  emit("update:modelValue", [...props.modelValue, emptyRow()]);
}

function remove(index: number) {
  const next = props.modelValue.slice();
  next.splice(index, 1);
  emit("update:modelValue", next.length ? next : [emptyRow()]);
}
</script>

<style scoped>
.capture-rows__help {
  margin: 0 0 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--el-fill-color-light, #f5f7fa);
  color: var(--el-text-color-regular, #606266);
  font-size: 12px;
  line-height: 1.6;
}

.capture-rows__help p {
  margin: 0 0 6px;
}

.capture-rows__help ul {
  margin: 0;
  padding-left: 18px;
}

.capture-rows__help li {
  margin-top: 4px;
}

.capture-rows__help code {
  padding: 0 4px;
  border-radius: 3px;
  background: var(--el-fill-color, #f0f2f5);
  font-size: 11px;
}
</style>
