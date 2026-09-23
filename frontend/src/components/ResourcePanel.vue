<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { get } from '../api/http'

interface Metrics {
  instance_type: string; available: boolean; status: string; health: string; oom_killed?: boolean
  cpu_percent?: number | null; cpu_limit?: number | null; cpu_limit_percent?: number | null
  memory_bytes?: number | null; memory_limit_bytes?: number | null; memory_percent?: number | null
  pids?: number | null; pids_limit?: number | null; uptime_seconds?: number | null
  network_rx_bytes?: number | null; network_tx_bytes?: number | null
  network_rx_bytes_per_second?: number | null; network_tx_bytes_per_second?: number | null
}
interface Snapshot { sampled_at: string; instances: Metrics[] }
const props = defineProps<{ sessionId: string; status: string; instanceKey: string }>()
const open = ref(false), visible = ref(!document.hidden), data = ref<Snapshot>(), error = ref(''), loading = ref(false)
const active = computed(() => open.value && visible.value && ['STARTING', 'READY'].includes(props.status))
const rows = computed(() => ['KALI', 'TARGET'].map(kind => data.value?.instances.find(i => i.instance_type === kind) || { instance_type: kind, available: false, status: 'pending', health: 'unknown' }))
const stateNames: Record<string, string> = { running: '运行中', created: '已创建', exited: '已退出', dead: '已退出', removed: '已回收', paused: '已暂停', restarting: '重启中', pending: '等待实例', unknown: '未知' }
const healthNames: Record<string, string> = { healthy: '健康', unhealthy: '检查异常', starting: '检查中', not_configured: '未配置健康检查', stopped: '已停止', unknown: '状态未知' }
let timer: ReturnType<typeof setTimeout> | undefined, controller: AbortController | undefined, version = 0
function stop() { version++; clearTimeout(timer); controller?.abort(); controller = undefined; loading.value = false }
async function refresh() {
  const current = version
  controller = new AbortController(); loading.value = true
  try {
    const snapshot = await get<Snapshot>(`/lab-sessions/${props.sessionId}/metrics`, { signal: controller.signal, silentError: true, timeout: 18000 })
    if (current === version) { data.value = snapshot; error.value = '' }
  } catch {
    if (current === version) error.value = '暂时无法更新，以下为上次采样；实验可继续。'
  } finally {
    if (current === version) { loading.value = false; if (active.value) timer = setTimeout(refresh, 5000) }
  }
}
watch([active, () => props.sessionId, () => props.instanceKey, () => props.status], () => {
  stop(); data.value = undefined; error.value = ''
  if (active.value) void refresh()
})
function visibility() { visible.value = !document.hidden }
onMounted(() => document.addEventListener('visibilitychange', visibility))
onBeforeUnmount(() => { stop(); document.removeEventListener('visibilitychange', visibility) })
function bytes(value?: number | null) {
  if (value == null) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KiB`
  return `${(value / 1024 ** 2).toFixed(1)} MiB`
}
function percent(value?: number | null) { return value == null ? '采样中' : `${value.toFixed(1)}%` }
function uptime(value?: number | null) { return value == null ? '—' : `${Math.floor(value / 3600)}时 ${Math.floor(value / 60) % 60}分 ${value % 60}秒` }
function width(value?: number | null) { return `${Math.min(100, Math.max(0, value || 0))}%` }
</script>

<template>
<section class="resource-panel panel" aria-label="实验资源监控">
  <button class="resource-toggle" :aria-expanded="open" aria-controls="resource-details" @click="open = !open">
    <span><strong>资源与健康状态</strong><small>Kali · 靶机</small></span>
    <span>{{ open ? '收起 −' : '展开 +' }}</span>
  </button>
  <div v-if="open" id="resource-details" class="resource-details">
    <p class="resource-note" role="status">{{ error || (!active ? '采集已暂停，实验就绪且页面可见时自动恢复。' : loading && !data ? '正在读取实例状态…' : '每 5 秒更新；CPU 100% 相当于一个虚拟 CPU 的使用量。') }}<span v-if="data"> 采样时间 {{ new Date(data.sampled_at).toLocaleTimeString('zh-CN') }}</span></p>
    <div class="resource-grid">
      <article v-for="row in rows" :key="row.instance_type" class="resource-card" :class="{ stale: !!error }">
        <header><strong>{{ row.instance_type === 'KALI' ? 'Kali 桌面' : '实验靶机' }}</strong><span>{{ stateNames[row.status] || row.status }}</span><span class="health-badge" :class="row.health">{{ healthNames[row.health] || '未知' }}</span></header>
        <p v-if="!row.available" class="resource-note">{{ row.status === 'removed' ? '实例已回收' : '暂无可用指标' }}</p>
        <template v-else>
          <div class="resource-measure"><span>CPU 使用量 <b>{{ percent(row.cpu_percent) }}</b></span><small>上限 {{ row.cpu_limit ?? '—' }} 核额度 · 已用 {{ percent(row.cpu_limit_percent) }}</small></div>
          <div class="resource-meter"><i :style="{ width: width(row.cpu_limit_percent) }"/></div>
          <div class="resource-measure"><span>内存 <b>{{ bytes(row.memory_bytes) }}</b></span><small>/ {{ bytes(row.memory_limit_bytes) }} · {{ percent(row.memory_percent) }}</small></div>
          <div class="resource-meter memory"><i :style="{ width: width(row.memory_percent) }"/></div>
          <dl><div><dt>进程 / 线程</dt><dd>{{ row.pids ?? '—' }} / {{ row.pids_limit && row.pids_limit > 0 ? row.pids_limit : '未设上限' }}</dd></div><div><dt>运行时间</dt><dd>{{ uptime(row.uptime_seconds) }}</dd></div><div><dt>网络接收</dt><dd>{{ bytes(row.network_rx_bytes_per_second) }}/s <small>累计 {{ bytes(row.network_rx_bytes) }}</small></dd></div><div><dt>网络发送</dt><dd>{{ bytes(row.network_tx_bytes_per_second) }}/s <small>累计 {{ bytes(row.network_tx_bytes) }}</small></dd></div></dl>
          <p v-if="row.oom_killed" class="resource-warning">容器曾因内存不足被终止。</p>
        </template>
      </article>
    </div>
    <p class="resource-note">收起面板或切换到后台标签页后暂停采集。健康状态来自容器检查，不代表所有实验功能均正常。</p>
  </div>
</section>
</template>

<style scoped>
.resource-panel { margin-bottom: 20px; padding: 0; overflow: hidden; }
.resource-toggle { width: 100%; border: 0; background: transparent; cursor: pointer; padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; color: inherit; font: inherit; text-align: left; }
.resource-toggle:focus-visible { outline: 2px solid #2e7771; outline-offset: -3px; }
.resource-toggle small { margin-left: 14px; color: #6d7775; }
.resource-details { padding: 0 20px 14px; }
.resource-note { color: #6d7775; font-size: 12px; line-height: 1.7; }
.resource-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.resource-card { padding: 16px; border: 1px solid #e2e9e6; border-radius: 10px; background: #fafcfb; }
.resource-card.stale { opacity: .6; }
.resource-card header { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 16px; }
.resource-card header > span { font-size: 12px; }
.health-badge { background: #eef0ef; color: #61716a; border-radius: 20px; padding: 3px 8px; }
.health-badge.healthy { background: #e3f3e9; color: #28774a; }
.health-badge.unhealthy, .resource-warning { color: #b54736; }
.resource-measure { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px; font-size: 13px; }
.resource-measure small { color: #6d7775; }
.resource-meter { height: 6px; margin: 8px 0 16px; background: #e4ebe7; border-radius: 5px; overflow: hidden; }
.resource-meter i { display: block; height: 100%; background: #3e8f85; transition: width .3s; }
.resource-meter.memory i { background: #7585b7; }
dl { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 0; font-size: 12px; }
dt { color: #6d7775; margin-bottom: 5px; } dd { margin: 0; } dd small { display: block; margin-top: 3px; color: #6d7775; }
@media (max-width: 760px) { .resource-grid { grid-template-columns: 1fr; } .resource-toggle small { display: none; } }
</style>
