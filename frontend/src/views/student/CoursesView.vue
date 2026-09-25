<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { get } from '../../api/http'
import type { Course, Progress } from '../../types'
const courses = ref<Course[]>([]), progress = ref<Progress[]>([]), busy = ref(true)
const search = ref(''), state = ref(''), failed = ref(false)
const completed = computed(() => new Set(progress.value.filter(p => p.completed).map(p => p.lesson_id)))
function percent(c: Course) { const all = c.chapters.flatMap(ch => ch.lessons); return all.length ? Math.round(all.filter(l => completed.value.has(l.id)).length / all.length * 100) : 0 }
function spineSegments(c: Course) { const all = c.chapters.flatMap(ch => ch.lessons); return Math.min(14, Math.max(4, all.length)) }
function spineDone(c: Course) { const all = c.chapters.flatMap(ch => ch.lessons); return all.length ? Math.round(spineSegments(c) * all.filter(l => completed.value.has(l.id)).length / all.length) : 0 }
const filtered = computed(() => courses.value.filter(c => {
  const matchesSearch = `${c.name} ${c.description}`.toLowerCase().includes(search.value.trim().toLowerCase())
  const value = percent(c)
  return matchesSearch && (!state.value || (state.value === 'new' && value === 0) || (state.value === 'active' && value > 0 && value < 100) || (state.value === 'complete' && value === 100))
}))
async function load() {
  busy.value = true; failed.value = false
  try { [courses.value, progress.value] = await Promise.all([get<Course[]>('/courses'), get<Progress[]>('/me/progress')]) }
  catch { failed.value = true } finally { busy.value = false }
}
onMounted(load)
</script>
<template>
<div v-loading="busy">
<div class="page-heading">
<div>
<h1>课程中心</h1>
<p class="muted">从基础原理出发，建立完整的安全知识体系。</p>
</div>
<span class="count-pill">{{ courses.length }} 门课程</span>
</div>
<div class="filter-bar">
<el-input v-model="search" :prefix-icon="Search" placeholder="搜索课程名称或内容" aria-label="搜索课程" clearable style="max-width:320px"/>
<el-select v-model="state" placeholder="全部学习状态" aria-label="学习状态" clearable style="width:160px">
<el-option value="new" label="尚未开始"/><el-option value="active" label="学习中"/><el-option value="complete" label="已完成"/>
</el-select>
</div>
<div v-if="failed" role="alert" class="load-error">课程暂时无法加载。<el-button link type="primary" @click="load">重新加载</el-button></div>
<div class="course-grid">
<router-link v-for="course in filtered" :key="course.id" :to="`/courses/${course.id}`" class="panel course-card">
<div class="course-cover">
<div class="cover-spine" aria-hidden="true"><i v-for="n in spineSegments(course)" :key="n" :class="{ done: n <= spineDone(course) }"/></div>
<p><b>{{ course.chapters.length }}</b> 章 <b>{{ course.chapters.reduce((n, c) => n + c.lessons.length, 0) }}</b> 课时</p>
</div>
<h2>{{ course.name }}</h2>
<p class="muted">{{ course.description }}</p>
<div class="progress-label">
<span>学习进度</span>
<span><strong>{{ percent(course) }}%</strong></span>
</div>
<el-progress :percentage="percent(course)" :stroke-width="5" :show-text="false"/>
<span class="card-link">{{ percent(course) === 100 ? '回顾课程' : percent(course) ? '继续学习' : '开始学习' }}</span>
</router-link>
</div>
<el-empty v-if="!busy && !failed && !filtered.length" :description="courses.length ? '没有找到符合条件的课程' : '暂无已发布课程'">
<el-button v-if="search || state" @click="search = ''; state = ''">清除筛选</el-button>
</el-empty>
</div>
</template>
