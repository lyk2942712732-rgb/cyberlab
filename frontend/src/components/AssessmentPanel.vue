<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import AssessmentPath from './AssessmentPath.vue'
import { get, post } from '../api/http'
import { date } from '../types'

interface Item { text: string; evidence_ids: string[] }
interface Stage extends Item { title: string; kind?: string }
interface Criterion extends Item { key: string; verdict: string }
interface Report {
  schema_version?: number; summary: string; path?: Stage[]; reasoning?: Item; criteria: Criterion[]
  suggestions?: Item[]; limitations: string[]
  approach?: Stage[]; improvements?: Item[]; next_steps?: string[]
}
interface Assessment {
  status: string; enabled: boolean; error: string | null; model: string; completed_at: string | null
  report: Report | null
  evidence: null | { flag_correct: boolean; events_read: number; events_used: number; truncated: boolean; capture_complete: boolean
    events: { id: string; type: string; timestamp: number; data: unknown }[]
    submissions: { id: string; correct: boolean; created_at: string }[] }
}
const props = defineProps<{ sessionId: string; sessionStatus: string }>()
const result = ref<Assessment>(), loading = ref(false), unavailable = ref(false), selected = ref<string[]>([])
let timer: ReturnType<typeof setTimeout> | undefined, generation = 0, disposed = false
const names: Record<string, string> = { strategy: '排查与调整', method: '解题方法', verification: '结果验证', understanding: '原理解释' }
const verdicts: Record<string, string> = { achieved: '已体现', partial: '部分体现', needs_work: '有待改进', insufficient_evidence: '暂无法判断' }
const legacy = computed(() => !!result.value?.report && result.value.report.schema_version !== 2)
const report = computed(() => {
  const source = result.value?.report
  if (!source) return null
  if (!legacy.value) return { ...source, path: source.path || [], reasoning: source.reasoning!, suggestions: source.suggestions || [] }
  const inferred = (source.approach || []).filter(item => item.kind === 'inferred')
  return {
    ...source,
    path: (source.approach || []).filter(item => item.kind === 'observed'),
    reasoning: { text: inferred.map(item => item.text).join('') || '这份历史报告未单独生成思路推断，更新报告后即可查看。',
      evidence_ids: [...new Set(inferred.flatMap(item => item.evidence_ids))] },
    criteria: source.criteria.filter(item => ['method', 'verification'].includes(item.key) ||
      (item.verdict !== 'insufficient_evidence' && item.evidence_ids.length)).map(item => ({ ...item, key: item.key === 'baseline' ? 'strategy' : item.key })),
    suggestions: source.next_steps?.length ? source.next_steps.map(text => ({ text, evidence_ids: [] })) : source.improvements || [],
  }
})
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
  <template v-else-if="report && result?.status === 'COMPLETED'">
    <p class="assessment-summary">{{ report.summary }}</p>
    <div v-if="legacy && result.enabled" class="legacy-note"><span>这份历史报告可更新为精简版，补充连贯的思路推断。</span><el-button link type="primary" :loading="loading" @click="request">更新报告</el-button></div>
    <details class="journey" open>
      <summary class="journey-toggle"><h3>操作路径与可能思路</h3><span class="journey-chevron" aria-hidden="true">⌄</span></summary>
      <div class="journey-layout">
        <AssessmentPath :steps="report.path" @evidence="selected = $event" />
        <aside class="reasoning" aria-label="可能思路">
          <div class="reasoning-heading"><h4>可能思路</h4><span>AI 推断</span></div>
          <p>{{ report.reasoning.text }}</p>
          <el-button v-if="report.reasoning.evidence_ids.length" link type="primary" @click="selected = report.reasoning.evidence_ids">查看推断依据</el-button>
        </aside>
      </div>
    </details>
    <h3>分项评价</h3>
    <div class="assessment-grid">
      <div v-for="item in report.criteria" :key="item.key" class="assessment-item">
        <div class="criterion-heading"><strong>{{ names[item.key] || item.key }}</strong><el-tag size="small" :type="item.verdict === 'achieved' ? 'success' : item.verdict === 'needs_work' ? 'warning' : 'info'">{{ verdicts[item.verdict] }}</el-tag></div>
        <p>{{ item.text }}</p>
        <el-button v-if="item.evidence_ids.length" link type="primary" @click="selected = item.evidence_ids">查看依据</el-button>
      </div>
    </div>
    <h3 v-if="report.suggestions.length">改进建议</h3>
    <ul class="suggestions"><li v-for="(item, index) in report.suggestions" :key="index">
      <p>{{ item.text }} <el-button v-if="item.evidence_ids.length" link type="primary" @click="selected = item.evidence_ids">查看依据</el-button></p>
    </li></ul>
    <p v-if="report.limitations.length" class="assessment-limitations small muted">{{ [...new Set(report.limitations)].join(' ') }}</p>
    <p class="assessment-meta small muted">{{ date(result.completed_at) }} · 本次实验反馈</p>
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
.assessment-panel { margin-top: 24px; container-type: inline-size; }
.assessment-panel p, .assessment-panel li { line-height: 1.85; overflow-wrap: anywhere; }
.assessment-panel h3 { font-size: 15px; margin: 26px 0 14px; }
.assessment-summary { font-size: 15px; color: var(--ink); max-width: 90ch; margin: 18px 0 24px; }
.journey { border-block: 1px solid var(--rule); padding-bottom: 0; }
.journey[open] { padding-bottom: 22px; }
.journey-toggle { display: flex; align-items: center; justify-content: space-between; gap: 20px; cursor: pointer; padding: 17px 0; list-style: none; }
.journey-toggle::-webkit-details-marker { display: none; }
.assessment-panel .journey-toggle h3 { margin: 0; }
.journey-chevron { font-size: 22px; color: var(--muted); transform: rotate(-90deg); line-height: 1; }
.journey[open] .journey-chevron { transform: rotate(0); }
.journey-layout { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(240px, 1fr); gap: 32px; align-items: start; padding-top: 6px; }
.reasoning { border-left: 2px solid var(--accent-line); padding: 2px 0 4px 22px; min-width: 0; }
.reasoning-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.reasoning-heading h4 { margin: 0; font-size: 14px; }
.reasoning-heading span { color: var(--muted); font-size: 11px; white-space: nowrap; }
.reasoning p { margin: 12px 0; color: var(--ink-2); }
.assessment-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 24px; }
.assessment-item { padding: 2px 0 16px; border-bottom: 1px solid var(--rule); min-width: 0; }
.criterion-heading { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.assessment-item p { margin: 10px 0; }
.suggestions { margin: 0; padding-left: 20px; max-width: 100ch; }
.suggestions li::marker { color: var(--accent); }
.suggestions p { margin: 10px 0; }
.assessment-limitations { margin: 20px 0 0; }
.assessment-meta { margin: 20px 0 0; font-size: 11px; }
.legacy-note { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; color: var(--muted); font-size: 12px; }
.assessment-evidence { white-space: pre-wrap; overflow-wrap: anywhere; padding: 12px; background: var(--surface-2); max-height: 320px; overflow: auto; }
@container (max-width: 720px) { .journey-layout { grid-template-columns: 1fr; gap: 24px; } .reasoning { padding-left: 16px; } }
@container (max-width: 480px) { .assessment-grid { grid-template-columns: 1fr; } }
</style>
