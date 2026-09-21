<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { get } from '../../api/http'
import type { Course, Progress } from '../../types'
const courses = ref<Course[]>([]), progress = ref<Progress[]>([]), busy = ref(true)
function percent(c: Course) { const all = c.chapters.flatMap(ch => ch.lessons); return all.length ? Math.round(all.filter(l => progress.value.some(p => p.lesson_id === l.id)).length / all.length * 100) : 0 }
onMounted(async () => { try { [courses.value, progress.value] = await Promise.all([get<Course[]>('/courses'), get<Progress[]>('/me/progress')]) } catch {} finally { busy.value = false } })
</script>
<template>
<div v-loading="busy">
<div class="page-heading">
<div>
<div class="eyebrow">KNOWLEDGE COMES FIRST</div>
<h1>课程中心</h1>
<p class="muted">从基础原理出发，建立完整的安全知识体系。</p>
</div>
<span class="count-pill">{{ courses.length }} 门课程</span>
</div>
<div class="course-grid">
<router-link v-for="(course, index) in courses" :key="course.id" :to="`/courses/${course.id}`" class="panel course-card">
<div class="course-cover">
<span>0{{ index + 1 }}</span>
<strong>{ learn }</strong>
<small>CYBER SECURITY</small>
</div>
<h2>{{ course.name }}</h2>
<p class="muted">{{ course.description }}</p>
<div class="progress-label">
<span>{{ course.chapters.length }} 章节 · {{ course.chapters.reduce((n, c) => n + c.lessons.length, 0) }} 课时</span>
<span>已学习 {{ percent(course) }}%</span>
</div>
<el-progress :percentage="percent(course)" :stroke-width="5" :show-text="false"/>
<div class="card-link">继续学习 <span>→</span>
</div>
</router-link>
</div>
<el-empty v-if="!busy && !courses.length" description="暂无已发布课程" />
</div>
</template>
