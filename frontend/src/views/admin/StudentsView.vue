<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { get } from '../../api/http'
import type { Progress, Score, StudentStats, User } from '../../types'
import { date } from '../../types'
const students = ref<StudentStats[]>([]), busy = ref(true), dialog = ref(false)
const detail = ref<{user: User; scores: Score[]; progress: Progress[]}>()
async function open(id: string) { try { detail.value = await get(`/admin/students/${id}`); dialog.value = true } catch {} }
onMounted(async () => { try { students.value = await get<StudentStats[]>('/admin/students') } catch {} finally { busy.value = false } })
</script>
<template>
<div v-loading="busy">
<div class="page-heading">
<div>
<h1>学生成绩</h1>
<p class="muted">了解实验完成情况与理论学习进度。</p>
</div>
<span class="count-pill">{{ students.length }} 名学生</span>
</div>
<section class="panel">
<el-table :data="students" empty-text="暂无学生">
<el-table-column label="姓名" min-width="150">
<template #default="{ row }">{{ row.real_name || row.username }}</template>
</el-table-column>
<el-table-column prop="student_number" label="学号" min-width="150"/>
<el-table-column prop="completed_labs" label="完成实验" width="110"/>
<el-table-column prop="average_score" label="平均成绩" width="110"/>
<el-table-column label="最近完成时间" min-width="180">
<template #default="{ row }">{{ date(row.last_completed_at) }}</template>
</el-table-column>
<el-table-column width="120">
<template #default="{ row }">
<el-button link type="primary" @click="open(row.id)">查看详情</el-button>
</template>
</el-table-column>
</el-table>
</section>
<el-dialog v-model="dialog" :title="`${detail?.user.real_name || detail?.user.username || ''} 的学习档案`" width="min(960px, 94vw)">
<template v-if="detail">
<div class="inline-gap margin-bottom">
<span class="count-pill">已完成 {{ detail.progress.length }} 个理论课时</span>
<span class="count-pill">已完成 {{ detail.scores.filter(s => s.completed).length }} 个实验</span>
</div>
<el-table :data="detail.scores">
<el-table-column prop="lab_name" label="实验名称" min-width="170"/>
<el-table-column label="状态" width="100">
<template #default="{ row }">
<el-tag :type="row.completed ? 'success' : 'info'">{{ row.completed ? '已完成' : '未完成' }}</el-tag>
</template>
</el-table-column>
<el-table-column prop="score" label="分数" width="80"/>
<el-table-column prop="submissions_count" label="提交次数" width="100"/>
<el-table-column label="完成时间" min-width="180">
<template #default="{ row }">{{ date(row.completed_at) }}</template>
</el-table-column>
</el-table>
<h3 style="margin-top:28px">理论课时完成记录</h3>
<el-table :data="detail.progress" empty-text="尚未完成理论课时">
<el-table-column prop="course_name" label="课程" min-width="150"/>
<el-table-column prop="chapter_title" label="章节" min-width="130"/>
<el-table-column prop="lesson_title" label="课时" min-width="150"/>
<el-table-column label="完成时间" min-width="180">
<template #default="{ row }">{{ date(row.completed_at) }}</template>
</el-table-column>
</el-table>
</template>
</el-dialog>
</div>
</template>
