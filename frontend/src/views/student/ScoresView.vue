<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { get } from '../../api/http'
import type { Score } from '../../types'
import { date } from '../../types'
const scores = ref<Score[]>([]), busy = ref(true)
onMounted(async () => { try { scores.value = await get<Score[]>('/me/scores') } catch {} finally { busy.value = false } })
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
</div>
</template>
