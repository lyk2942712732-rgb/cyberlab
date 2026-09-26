<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { get, post } from '../../api/http'
import type { LabSession } from '../../types'
import { activeStatuses, date } from '../../types'
import StatusTag from '../../components/StatusTag.vue'
import ActivityLog from '../../components/ActivityLog.vue'
const activitySession = ref(''), activityOpen = ref(false)
function showActivity(id: string) { activitySession.value = id; activityOpen.value = true }
const sessions = ref<LabSession[]>([]), showAll = ref(false), now = ref(Date.now())
let poll: ReturnType<typeof setTimeout> | undefined, disposed = false
async function load() { try { const data = await get<LabSession[]>('/admin/lab-sessions'); if (!disposed) { sessions.value = data; now.value = Date.now() } } catch {} finally { if (!disposed) poll = setTimeout(load, 5000) } }
async function stop(id: string) { try { await ElMessageBox.confirm('这将强制结束该学生的实验并回收所有实验资源。', '终止实验', { type: 'warning' }) } catch { return } try { await post(`/admin/lab-sessions/${id}/stop`); clearTimeout(poll); await load() } catch {} }
onMounted(load); onBeforeUnmount(() => { disposed = true; clearTimeout(poll) })
</script>
<template>
<div>
<div class="page-heading">
<div>
<h1>运行实例</h1>
<p class="muted">查看隔离实验环境的实时状态，及时处理异常实例。列表每 5 秒自动更新。</p>
</div>
<el-switch v-model="showAll" active-text="显示历史实例"/>
</div>
<section class="panel">
<el-table :data="sessions.filter(s => showAll || activeStatuses.includes(s.status))" empty-text="当前没有运行中的实验">
<el-table-column label="学生 / 学号" min-width="150">
<template #default="{ row }">{{ row.student?.real_name || row.student?.username }}<small class="table-subline">{{ row.student?.student_number }}</small>
</template>
</el-table-column>
<el-table-column label="实验 / Session" min-width="240">
<template #default="{ row }">{{ row.lab_name }}<code class="table-subline small">{{ row.id }}</code>
</template>
</el-table-column>
<el-table-column label="容器状态" min-width="170">
<template #default="{ row }">
<div v-for="i in row.instances" :key="i.id" class="instance-state">
<small>{{ i.instance_type }}</small>
<StatusTag :status="i.status"/>
</div>
</template>
</el-table-column>
<el-table-column label="状态" width="120">
<template #default="{ row }">
<StatusTag :status="row.status"/>
</template>
</el-table-column>
<el-table-column label="启动 / 剩余" min-width="180">
<template #default="{ row }">{{ date(row.started_at) }}<small class="table-subline">{{ activeStatuses.includes(row.status) ? `${Math.max(0, Math.ceil((new Date(row.expires_at).getTime() - now) / 60000))} 分钟` : '已结束' }}</small>
</template>
</el-table-column>
<el-table-column label="操作" width="240">
<template #default="{ row }">
<router-link :to="`/sessions/${row.id}`">详情</router-link>
<el-button link type="primary" style="margin-left:12px" @click="showActivity(row.id)">操作记录</el-button>
<el-button link type="danger" style="margin-left:12px" :disabled="!activeStatuses.includes(row.status)" @click="stop(row.id)">强制停止</el-button>
</template>
</el-table-column>
</el-table>
</section>
<el-dialog v-model="activityOpen" title="学生实验操作记录" width="min(1100px, 94vw)" destroy-on-close><ActivityLog v-if="activityOpen" :session-id="activitySession"/></el-dialog>
</div>
</template>
