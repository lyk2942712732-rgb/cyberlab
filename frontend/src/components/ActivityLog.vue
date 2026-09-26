<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { get } from '../api/http'
interface Event { seq: number; timestamp: number; source: string; type: string; data: Record<string, unknown> }
interface Journal { state: { status: string; error?: string; generation?: number; complete?: boolean; rejected_events?: number; providers?: Record<string, {status: string}> }; events: Event[]; generations: number[]; next: number | null }
const props = defineProps<{ sessionId: string }>()
const data = ref<Journal>(), loading = ref(false), error = ref(''), generation = ref<number>(), after = ref(0)
const history = ref<number[]>([])
const partial = computed(() => !!data.value?.state.rejected_events || Object.values(data.value?.state.providers || {}).some(p => p.status === 'partial'))
const labels: Record<string, string> = { 'terminal.submit': '提交命令', 'web.click': '网页点击', 'web.change': '完成输入', 'web.submit': '提交表单', 'web.navigate': '页面导航', 'ui.click': '桌面点击', 'ui.change': '完成输入' }
const states: Record<string, string> = { running: '采集中', finished: '已结束', interrupted: '记录中断', starting: '启动中', unavailable: '暂无记录' }
let version = 0
async function load(reset = false) {
  if (reset) { after.value = 0; history.value = [] }
  const current = ++version
  loading.value = true; error.value = ''
  try {
    const params = new URLSearchParams({ after: String(after.value) })
    if (generation.value != null) params.set('generation', String(generation.value))
    const result = await get<Journal>(`/admin/lab-sessions/${props.sessionId}/activity?${params}`)
    if (current === version) data.value = result
  } catch { if (current === version) error.value = '操作记录暂时无法读取，请重试。' }
  finally { if (current === version) loading.value = false }
}
function next() { if (data.value?.next != null) { history.value.push(after.value); after.value = data.value.next; void load() } }
function previous() { after.value = history.value.pop() || 0; void load() }
function detail(event: Event) {
  if (event.type === 'terminal.submit') return `${event.data.cwd}\n${event.data.command}`
  return JSON.stringify(event.data, null, 2)
}
watch(() => props.sessionId, () => { generation.value = undefined; void load(true) }, { immediate: true })
</script>
<template>
  <div class="activity-toolbar">
    <span>{{ states[data?.state.status || 'unavailable'] }} · {{ data?.state.complete ? '记录完整结束' : '尚未完整结束' }}</span>
    <el-select v-model="generation" placeholder="最近一次实验" style="width:180px" @change="load(true)"><el-option v-for="g in data?.generations || []" :key="g" :value="g" :label="`实验代次 ${g}`"/></el-select>
    <el-button :loading="loading" @click="load()">刷新</el-button>
  </div>
  <p class="muted small">只保存最终输入、提交和点击；未知控件保留坐标。提交不代表执行成功，页面导航不等同于地址栏输入。</p>
  <p v-if="error || data?.state.error" role="alert">{{ error || data?.state.error }}</p>
  <p v-if="partial" role="alert">部分操作未能完整记录，请结合实验结果核查。</p>
  <el-table :data="data?.events || []" empty-text="此代次暂无操作记录" max-height="560">
    <el-table-column label="时间" width="165"><template #default="{ row }">{{ new Date(row.timestamp * 1000).toLocaleString('zh-CN') }}</template></el-table-column>
    <el-table-column label="动作" width="110"><template #default="{ row }">{{ labels[row.type] || row.type }}</template></el-table-column>
    <el-table-column label="最终内容 / 操作目标"><template #default="{ row }"><pre class="activity-detail">{{ detail(row) }}</pre></template></el-table-column>
  </el-table>
  <div class="activity-toolbar"><el-button :disabled="!history.length || loading" @click="previous">上一页</el-button><el-button :disabled="data?.next == null || loading" @click="next">下一页</el-button></div>
</template>
<style scoped>
.activity-toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin: 12px 0; }
.activity-detail { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; line-height: 1.6; margin: 6px 0; }
</style>
