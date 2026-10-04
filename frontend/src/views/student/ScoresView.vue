<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { get } from '../../api/http'
import type { Score } from '../../types'
import { date } from '../../types'
const scores = ref<Score[]>([]), busy = ref(true)
const history = ref<{ session_id: string; lab_name: string; status: string; started_at: string }[]>([])
const statusText: Record<string, string> = { NOT_REQUESTED: '尚未生成', QUEUED: '排队中', RUNNING: '生成中', COMPLETED: '已完成', FAILED: '可重试' }
onMounted(async () => { try { [scores.value, history.value] = await Promise.all([get<Score[]>('/me/scores'), get<typeof history.value>('/me/assessments')]) } catch {} finally { busy.value = false } })
</script>
<template>
<div v-loading="busy">
<div class="page-heading">
<div>
<h1>我的成绩</h1>
<p class="muted">记录每一次尝试，看见自己的成长。</p>
</div>
<span class="count-pill">已完成 {{ scores.filter(s => s.completed).length }} 个实验</span>
</div>
<section class="panel">
<el-table :data="scores" empty-text="暂无实验成绩">
<el-table-column prop="lab_name" label="实验" min-width="220"/>
<el-table-column label="完成状态" width="140">
<template #default="{ row }">
<el-tag :type="row.completed ? 'success' : 'info'" round>{{ row.completed ? '已完成' : row.attempted ? '进行中 / 未完成' : '未开始' }}</el-tag>
</template>
</el-table-column>
<el-table-column prop="score" label="成绩" width="100"/>
<el-table-column prop="submissions_count" label="提交次数" width="100"/>
<el-table-column label="完成时间" min-width="190">
<template #default="{ row }">{{ date(row.completed_at) }}</template>
</el-table-column>
<el-table-column width="100">
<template #default="{ row }">
<router-link :to="`/labs/${row.lab_id}`">查看实验</router-link>
</template>
</el-table-column>
</el-table>
</section>
<section class="panel" style="margin-top:24px">
<h2>实验复盘记录</h2>
<p class="muted small">最近 100 次已结束的实验，可查看反馈或为历史记录生成复盘。</p>
<el-table :data="history" empty-text="还没有已结束的实验">
<el-table-column prop="lab_name" label="实验" min-width="220"/>
<el-table-column label="开始时间" min-width="190"><template #default="{ row }">{{ date(row.started_at) }}</template></el-table-column>
<el-table-column label="复盘状态" width="110"><template #default="{ row }">{{ statusText[row.status] || row.status }}</template></el-table-column>
<el-table-column width="120"><template #default="{ row }"><router-link :to="`/sessions/${row.session_id}`">查看实验复盘</router-link></template></el-table-column>
</el-table>
</section>
</div>
</template>
