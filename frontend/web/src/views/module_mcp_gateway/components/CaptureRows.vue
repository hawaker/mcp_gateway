<template>
  <div class="capture-rows">
    <div v-for="(row, index) in modelValue" :key="index" class="flex gap-2 items-center flex-wrap mb-2">
      <ElInput v-model="row.name" placeholder="变量名" class="!w-36" />
      <ElSelect v-model="row.from" placeholder="来源" class="!w-28">
        <ElOption v-for="opt in FROM_OPTIONS" :key="opt" :label="opt" :value="opt" />
      </ElSelect>
      <ElInput v-model="row.path" placeholder="path / 字段 / 正则" class="!flex-1 min-w-40" />
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

const FROM_OPTIONS = ["json", "header", "form", "text", "regex"] as const;

const props = withDefaults(
  defineProps<{ modelValue: CaptureRow[]; addLabel?: string }>(),
  { addLabel: "添加变量" },
);
const emit = defineEmits<{ "update:modelValue": [CaptureRow[]] }>();

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
