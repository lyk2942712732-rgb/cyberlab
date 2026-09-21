<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuth } from '../stores/auth'
import { get } from '../api/http'
import type { Course, LabSession, Progress, Score } from '../types'
import { date } from '../types'
import StatusTag from '../components/StatusTag.vue'
const auth = useAuth(), busy = ref(true)
const admin = computed(() => auth.user?.role === 'ADMIN')
const stats = ref<Record<string, number>>({}), courses = ref<Course[]>([]), sessions = ref<LabSession[]>([]), scores = ref<Score[]>([]), progress = ref<Progress[]>([])
const cards = computed(() => admin.value ? [ ['学生人数', stats.value.students || 0, '已注册学生'], ['已发布课程', stats.value.published_courses || 0, '理论学习内容'], ['已发布实验', stats.value.published_labs || 0, '可供学生开始实践'], ['当前运行实验', stats.value.running_sessions || 0, '独立实验环境'], ['今日完成实验', stats.value.completed_today || 0, '正确提交记录'] ] : [ ['当前课程', courses.value.length, '持续积累安全知识'], ['已学课时', progress.value.length, '每一步都有记录'], ['已完成实验', scores.value.filter(s => s.completed).length, '在实践中验证所学'], ['平均成绩', average.value, '按已尝试实验统计'] ])
const average = computed(() => { const rows = scores.value.filter(s => s.attempted); return rows.length ? Math.round(rows.reduce((a, b) => a + b.score, 0) / rows.length) : 0 })
function percent(course: Course) { const lessons = course.chapters.flatMap(c => c.lessons); return lessons.length ? Math.round(lessons.filter(l => progress.value.some(p => p.lesson_id === l.id)).length / lessons.length * 100) : 0 }
onMounted(async () => {
  try {
    if (admin.value) { [stats.value, sessions.value] = await Promise.all([get<Record<string, number>>('/admin/dashboard'), get<LabSession[]>('/admin/lab-sessions')]) }
    else { [courses.value, sessions.value, scores.value, progress.value] = await Promise.all([get<Course[]>('/courses'), get<LabSession[]>('/me/sessions'), get<Score[]>('/me/scores'), get<Progress[]>('/me/progress')]) }
  } catch {} finally { busy.value = false }
})
</script>
<template>
<div v-loading="busy">
<div class="page-heading">
<div>
<div class="eyebrow">{{ admin ? 'TEACHING OVERVIEW' : 'YOUR LEARNING JOURNEY' }}</div>
<h1>{{ admin ? '教学平台概览' : `你好，${auth.user?.real_name || auth.user?.username}` }}<span v-if="!admin" class="greeting-dot">.</span>
</h1>
<p class="muted">{{ admin ? '掌握教学进度，让每一次实践顺利发生。' : '今天也向前一步。把学到的知识，变成解决问题的能力。' }}</p>
</div>
<router-link :to="admin ? '/admin/labs' : '/labs'">
<el-button type="primary" size="large">{{ admin ? '管理实验' : '探索实验' }} ↗</el-button>
</router-link>
</div>
<div class="stat-grid">
<div v-for="(card, index) in cards" :key="String(card[0])" class="stat-card">
<span class="stat-index">0{{ index + 1 }}</span>
<span class="muted">{{ card[0] }}</span>
<strong>{{ card[1] }}<small v-if="card[0] === '平均成绩'">分</small>
</strong>
<small>{{ card[2] }}</small>
</div>
</div>
<div v-if="!admin" class="welcome-banner">
<div>
<span class="eyebrow">LEARNING BY DOING</span>
<h2>你的下一次突破，<br/>从一个实验开始。</h2>
<p>独立 Kali 桌面 · 随时开启 · 在线实践</p>
<router-link to="/labs">
<el-button color="#d9efaf">进入实验空间 →</el-button>
</router-link>
</div>
<div class="banner-graphic" aria-hidden="true">
<div class="orbital orbital-one"/>
<div class="orbital orbital-two"/>
<span>&lt;/&gt;</span>
<small>EXPLORE WITH PURPOSE</small>
</div>
</div>
<div v-if="!admin" class="section-heading">
<h2>继续学习</h2>
<router-link to="/courses">全部课程 ↗</router-link>
</div>
<div v-if="!admin" class="course-grid">
<router-link v-for="course in courses.slice(0, 3)" :key="course.id" :to="`/courses/${course.id}`" class="panel course-card">
<span class="course-symbol">{ }</span>
<h3>{{ course.name }}</h3>
<p class="muted clamp-two">{{ course.description }}</p>
<div class="progress-label">
<span>{{ course.chapters.length }} 个章节</span>
<span>{{ percent(course) }}%</span>
</div>
<el-progress :percentage="percent(course)" :show-text="false" :stroke-width="5" />
</router-link>
<el-empty v-if="!courses.length" description="课程正在准备中" />
</div>
<section class="panel">
<div class="section-heading">
<h2>最近实验</h2>
<router-link :to="admin ? '/admin/sessions' : '/labs'">{{ admin ? '查看运行实例' : '前往实验空间' }} ↗</router-link>
</div>
<el-table :data="sessions.slice(0, 6)" empty-text="还没有实验记录">
<el-table-column prop="lab_name" label="实验名称" min-width="180"/>
<el-table-column label="状态" width="130">
<template #default="{ row }">
<StatusTag :status="row.status" />
</template>
</el-table-column>
<el-table-column label="启动时间" min-width="180">
<template #default="{ row }">{{ date(row.started_at) }}</template>
</el-table-column>
<el-table-column label="操作" width="100">
<template #default="{ row }">
<router-link :to="`/sessions/${row.id}`">查看 →</router-link>
</template>
</el-table-column>
</el-table>
</section>
</div>
</template>
