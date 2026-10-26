<template>
  <div class="kv-rows">
    <div v-for="(row, index) in modelValue" :key="index" class="flex gap-2 items-center flex-wrap mb-2">
      <ElInput v-model="row.key" placeholder="名" class="!w-40" />
      <ElInput v-model="row.value" placeholder="值，可写 {{user.uid}}" class="!flex-1 min-w-40" />
      <ElButton text type="danger" @click="remove(index)">删除</ElButton>
    </div>
    <ElButton plain @click="add">{{ addLabel }}</ElButton>
  </div>
</template>

<script setup lang="ts">
export interface KvRow {
  key: string;
  value: string;
}

const props = withDefaults(
  defineProps<{ modelValue: KvRow[]; addLabel?: string }>(),
  { addLabel: "添加一行" },
);
const emit = defineEmits<{ "update:modelValue": [KvRow[]] }>();

function add() {
  emit("update:modelValue", [...props.modelValue, { key: "", value: "" }]);
}

function remove(index: number) {
  const next = props.modelValue.slice();
  next.splice(index, 1);
  emit("update:modelValue", next.length ? next : [{ key: "", value: "" }]);
}
</script>
