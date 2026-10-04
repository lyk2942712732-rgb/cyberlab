<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { get, post } from '../api/http'
import { date } from '../types'

interface Item { text: string; evidence_ids: string[] }
interface Assessment {
  status: string; enabled: boolean; error: string | null; model: string; completed_at: string | null
  report: null | {
    summary: string; approach: (Item & { title: string; kind: string })[]
    criteria: (Item & { key: string; verdict: string })[]
    strengths: Item[]; improvements: Item[]; next_steps: string[]; limitations: string[]
  }
  evidence: null | { flag_correct: boolean; events_read: number; events_used: number; truncated: boolean; capture_complete: boolean
    events: { id: string; type: string; timestamp: number; data: unknown }[]
    submissions: { id: string; correct: boolean; created_at: string }[] }
}
const props = defineProps<{ sessionId: string; sessionStatus: string }>()
const result = ref<Assessment>(), loading = ref(false), unavailable = ref(false), selected = ref<string[]>([])
let timer: ReturnType<typeof setTimeout> | undefined, generation = 0, disposed = false
const names: Record<string, string> = { baseline: '正常行为基线', method: '解题方法', verification: '结果验证', understanding: '原理与修复' }
const verdicts: Record<string, string> = { achieved: '已展示', partial: '部分展示', needs_work: '需要改进', insufficient_evidence: '证据不足' }
const ended = () => ['DESTROYED', 'FAILED'].includes(props.sessionStatus)
async function refresh() {
  const current = generation
  try { const value = await get<Assessment>(`/lab-sessions/${props.sessionId}/assessment`, { silentError: true }); if (current === generation && !disposed) { result.value = value; unavailable.value = false } }
  catch { if (current === generation && !disposed) unavailable.value = true }
  finally { if (current === generation && !disposed && ended() && (!result.value || ['QUEUED', 'RUNNING'].includes(result.value.status))) timer = setTimeout(refresh, 3000) }
}
async function request() {
  loading.value = true
  clearTimeout(timer)
  try { result.value = await post<Assessment>(`/lab-sessions/${props.sessionId}/assessment`); unavailable.value = false; timer = setTimeout(refresh, 1500) }
  catch {} finally { loading.value = false }
}
watch(() => [props.sessionId, props.sessionStatus], () => {
  generation++; clearTimeout(timer); selected.value = []; result.value = undefined
  if (ended()) refresh()
}, { immediate: true })
onBeforeUnmount(() => { disposed = true; generation++; clearTimeout(timer) })
function evidenceText(id: string) {
  const event = result.value?.evidence?.events.find(item => item.id === id)
  if (event) return `${date(new Date(event.timestamp * 1000).toISOString())} · ${event.type}\n${JSON.stringify(event.data, null, 2)}`
  const submission = result.value?.evidence?.submissions.find(item => item.id === id)
  return submission ? `${date(submission.created_at)} · Flag 提交${submission.correct ? '正确' : '错误'}` : '此条证据暂不可用'
}
</script>

<template>
<section class="panel assessment-panel" aria-label="实验复盘与反馈">
  <h2>实验复盘与反馈</h2>
  <p class="muted small">根据本次操作记录与参考解答生成，帮助你理解解题过程。分项评价不改变 Flag 成绩。</p>
  <p v-if="!ended()" class="muted">结束实验后，这里会自动生成你的复盘。</p>
  <template v-else-if="result?.report && result.status === 'COMPLETED'">
    <p class="assessment-summary">{{ result.report.summary }}</p>
    <p class="small muted">{{ date(result.completed_at) }} · {{ result.model }} · 使用 {{ result.evidence?.events_used }} 条操作记录</p>
    <p class="small">平台判题记录：{{ result.evidence?.flag_correct ? '本次有正确 Flag 提交' : '本次未记录到正确 Flag 提交' }}</p>
    <h3>操作路径与可能思路</h3>
    <div v-for="(stage, index) in result.report.approach" :key="index" class="assessment-item">
      <strong>{{ stage.title }}</strong> <el-tag size="small" :type="stage.kind === 'observed' ? 'info' : 'warning'">{{ stage.kind === 'observed' ? '已记录操作' : '可能的思路' }}</el-tag>
      <p>{{ stage.text }}</p>
      <el-button v-if="stage.evidence_ids.length" link type="primary" @click="selected = stage.evidence_ids">查看依据</el-button>
    </div>
    <h3>分项评价</h3>
    <div class="assessment-grid">
      <div v-for="item in result.report.criteria" :key="item.key" class="assessment-item">
        <strong>{{ names[item.key] }}</strong> <el-tag size="small" :type="item.verdict === 'achieved' ? 'success' : item.verdict === 'needs_work' ? 'warning' : 'info'">{{ verdicts[item.verdict] }}</el-tag>
        <p>{{ item.text }}</p>
        <el-button v-if="item.evidence_ids.length" link type="primary" @click="selected = item.evidence_ids">查看依据</el-button>
      </div>
    </div>
    <template v-for="(items, key) in { strengths: result.report.strengths, improvements: result.report.improvements }" :key="key">
      <h3 v-if="items.length">{{ key === 'strengths' ? '做得好的地方' : '可以改进的地方' }}</h3>
      <div v-for="(item, index) in items" :key="index" class="assessment-item">
        <p>{{ item.text }} <el-button v-if="item.evidence_ids.length" link type="primary" @click="selected = item.evidence_ids">查看依据</el-button></p>
      </div>
    </template>
    <h3 v-if="result.report.next_steps.length">下一步建议</h3>
    <ul><li v-for="(text, index) in result.report.next_steps" :key="index">{{ text }}</li></ul>
    <div v-if="result.report.limitations.length" class="assessment-limitations"><strong>本次评价的依据与限制</strong><ul><li v-for="(text, index) in result.report.limitations" :key="index">{{ text }}</li></ul></div>
  </template>
  <div v-else-if="unavailable" role="alert"><p>暂时无法读取复盘。</p><el-button @click="refresh">刷新复盘</el-button></div>
  <p v-else-if="result && !result.enabled" class="muted">实验复盘暂未启用。</p>
  <div v-else-if="result?.status === 'FAILED'" role="alert"><p>{{ result.error || '复盘生成失败，请重试。' }}</p><el-button :loading="loading" @click="request">重试生成</el-button></div>
  <div v-else-if="result?.status === 'NOT_REQUESTED'"><p class="muted">这次历史实验还没有复盘，可以根据已有记录生成。</p><el-button type="primary" :loading="loading" @click="request">生成实验复盘</el-button></div>
  <div v-else role="status"><p>{{ result?.status === 'RUNNING' ? '正在分析你的操作与解题思路…' : '正在排队整理实验记录…' }}</p><p class="small muted">可以离开此页面，稍后从“我的成绩 → 实验复盘记录”查看。{{ result?.error ? '服务暂时繁忙，正在自动重试。' : '' }}</p></div>
  <el-dialog :model-value="selected.length > 0" title="本次评价的操作依据" width="min(760px, 94vw)" append-to-body @close="selected = []">
    <div v-for="id in selected" :key="id"><strong>{{ id }}</strong><pre class="assessment-evidence">{{ evidenceText(id) }}</pre></div>
  </el-dialog>
</section>
</template>

<style scoped>
.assessment-panel { margin-top: 24px; }
.assessment-panel p, .assessment-panel li { line-height: 1.8; overflow-wrap: anywhere; }
.assessment-summary { font-size: 15px; }
.assessment-item { padding: 14px 0; border-bottom: 1px solid var(--rule); }
.assessment-item p { margin: 8px 0; }
.assessment-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 24px; }
.assessment-limitations { padding: 16px; margin-top: 20px; background: var(--surface-2); border-radius: 8px; }
.assessment-evidence { white-space: pre-wrap; overflow-wrap: anywhere; padding: 12px; background: var(--surface-2); max-height: 320px; overflow: auto; }
@media (max-width: 700px) { .assessment-grid { grid-template-columns: 1fr; } }
</style>
