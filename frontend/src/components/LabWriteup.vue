<script setup lang="ts">
import { ref, watch } from 'vue'
import { get } from '../api/http'
import type { LabWriteup } from '../types'
import MarkdownContent from './MarkdownContent.vue'

const props = defineProps<{ labId: string }>()
const opened = ref(false), loading = ref(false), failed = ref(false), reference = ref<LabWriteup>()
let request = 0
watch(() => props.labId, () => { request++; opened.value = false; reference.value = undefined; loading.value = false; failed.value = false })
async function load() {
  const current = ++request
  loading.value = true
  failed.value = false
  try {
    const result = await get<LabWriteup>(`/labs/${props.labId}/writeup`, { silentError: true })
    if (current === request) reference.value = result
  } catch { if (current === request) failed.value = true }
  finally { if (current === request) loading.value = false }
}
function open() { opened.value = true; load() }
</script>

<template>
<el-button @click="open">查看参考解答</el-button>
<el-drawer v-model="opened" title="参考解答与解题思路" size="min(920px, 96vw)" append-to-body>
  <p class="muted small">建议先独立尝试，再对照步骤、预期现象与修复思路复盘。</p>
  <div v-if="loading" role="status">正在加载参考解答…</div>
  <div v-else-if="failed" role="alert">
    <p>参考解答加载失败，请重试。</p>
    <el-button @click="load">重新加载</el-button>
  </div>
  <template v-else-if="reference?.content?.trim()">
    <MarkdownContent :content="reference.content"/>
  </template>
  <el-empty v-else description="本实验暂未配置参考解答"/>
</el-drawer>
</template>
