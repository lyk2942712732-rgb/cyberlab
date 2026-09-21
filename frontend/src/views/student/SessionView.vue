<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { get, post } from '../../api/http'
import type { Lab, LabSession } from '../../types'
import StatusTag from '../../components/StatusTag.vue'
import MarkdownContent from '../../components/MarkdownContent.vue'
const route = useRoute(), session = ref<LabSession>(), lab = ref<Lab>(), flag = ref(''), busy = ref(false), now = ref(Date.now()), desktopKey = ref(0)
let timer: ReturnType<typeof setInterval> | undefined, poll: ReturnType<typeof setTimeout> | undefined, disposed = false
const expanded = ref(false)
let previousOverflow = ''
watch(expanded, value => {
  if (value) { previousOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden' }
  else document.body.style.overflow = previousOverflow
})
const remaining = computed(() => { if (['DESTROYED', 'FAILED', 'FINISHED'].includes(session.value?.status || '')) return '00:00:00'; const total = Math.max(0, Math.floor((new Date(session.value?.expires_at || 0).getTime() - now.value) / 1000)); return [Math.floor(total / 3600), Math.floor(total / 60) % 60, total % 60].map(n => String(n).padStart(2, '0')).join(':') })
const canUse = computed(() => session.value?.status === 'READY' && remaining.value !== '00:00:00')
async function refresh() {
  try { const data = await get<LabSession>(`/lab-sessions/${route.params.id}`); if (!disposed) { session.value = data; lab.value = data.lab } } catch {}
  finally { if (!disposed) poll = setTimeout(refresh, 3000) }
}
async function command(action: string) {
  try { await ElMessageBox.confirm(action === 'reset' ? '重置将清除当前桌面与靶机中的操作，实验截止时间保持不变。' : '结束后将销毁实验环境，已提交的成绩会保留。', action === 'reset' ? '重置实验' : '结束实验', { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }) } catch { return }
  busy.value = true
  try { session.value = await post<LabSession>(`/lab-sessions/${route.params.id}/${action}`); desktopKey.value++ } catch {} finally { busy.value = false }
}
async function submit() {
  if (!flag.value.trim()) return ElMessage.warning('请输入 Flag')
  busy.value = true
  try { const result = await post<{correct: boolean; score: number}>(`/lab-sessions/${route.params.id}/submit`, { flag: flag.value }); if (result.correct) { ElMessage.success('回答正确！100 分已记录'); flag.value = '' } else ElMessage.warning('Flag 不正确，再检查一下实验结果。') } catch {} finally { busy.value = false }
}
onMounted(() => { refresh(); timer = setInterval(() => { now.value = Date.now() }, 1000) })
onBeforeUnmount(() => { disposed = true; clearInterval(timer); clearTimeout(poll); if (expanded.value) document.body.style.overflow = previousOverflow })
</script>
<template>
<div>
<div class="page-heading">
<div>
<router-link to="/labs" class="back-link">← 实验空间</router-link>
<h1>{{ session?.lab_name || '正在加载实验' }}</h1>
<div class="inline-gap">
<StatusTag v-if="session" :status="session.status"/>
<span class="muted small">每次实践，都是新的发现。</span>
</div>
</div>
<div class="session-clock">
<small>剩余实验时间</small>
<strong>{{ remaining }}</strong>
</div>
</div>
<el-alert v-if="session?.error" :title="session.error" type="error" :closable="false" show-icon class="margin-bottom"/>
<div class="experiment-layout">
<aside class="panel experiment-guide">
<div class="eyebrow">EXPERIMENT GUIDE</div>
<h3>实验目标</h3>
<MarkdownContent :content="lab?.objective"/>
<div class="target-address">
<small>在 Kali 内访问靶机</small>
<code>{{ session?.target_ip ? `${session.target_ip}:${lab?.target_port}` : '等待环境就绪' }}</code>
<p class="small muted" style="margin:8px 0 0">IP：{{ session?.target_ip || '—' }} · 端口：{{ lab?.target_port || '—' }}</p>
</div>
<h3>操作指引</h3>
<MarkdownContent :content="lab?.steps"/>
</aside>
<section class="desktop-panel" :class="{ 'desktop-panel-expanded': expanded }">
<header>
<div>
<span class="status-dot"/>Kali Desktop<span v-if="expanded" class="desktop-remaining">剩余 {{ remaining }}</span></div>
<div class="desktop-header-actions">
<a v-if="canUse" :href="`/desktop/${session?.id}`" target="_blank" rel="noopener">在新窗口打开 ↗</a>
<el-button size="small" :aria-pressed="expanded" @click="expanded = !expanded">{{ expanded ? '退出全屏' : '全屏' }}</el-button>
</div>
</header>
<iframe v-if="canUse" :key="desktopKey" :src="`/desktop/${session?.id}`" title="Kali 在线实验桌面" allow="clipboard-read; clipboard-write"/>
<div v-else class="desktop-placeholder">
<div class="desktop-glyph">&gt;_</div>
<h2>{{ ['DESTROYED', 'FAILED'].includes(session?.status || '') ? '本次实验已结束' : '正在准备你的实验环境' }}</h2>
<p>{{ ['DESTROYED', 'FAILED'].includes(session?.status || '') ? '成绩已保留，可返回实验详情重新开始。' : '独立网络、Kali 桌面和靶机准备就绪后将在这里显示。' }}</p>
<router-link v-if="session && ['DESTROYED', 'FAILED'].includes(session.status)" :to="`/labs/${session.lab_template_id}`">
<el-button>返回实验详情</el-button>
</router-link>
</div>
</section>
</div>
<section class="panel submission-bar">
<form @submit.prevent="submit">
<label for="flag-input">提交实验 Flag</label>
<el-input id="flag-input" v-model="flag" placeholder="flag{...}" maxlength="512" :disabled="!canUse"/>
<el-button type="primary" native-type="submit" :loading="busy" :disabled="!canUse">提交验证 →</el-button>
</form>
<div class="session-actions">
<el-button :disabled="!canUse || busy" @click="command('reset')">重置实验</el-button>
<el-button type="danger" plain :disabled="!session || ['DESTROYED', 'STOPPING'].includes(session.status) || busy" @click="command('stop')">结束实验</el-button>
</div>
</section>
</div>
</template>
