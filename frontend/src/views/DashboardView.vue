<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Reading, Monitor, Trophy, Finished, ArrowRight, TopRight } from '@element-plus/icons-vue'
import { useAuth } from '../stores/auth'
import { get } from '../api/http'
import type { Course, LabSession, Progress, Score } from '../types'
import { date } from '../types'
import StatusTag from '../components/StatusTag.vue'

const auth = useAuth(), busy = ref(true), failed = ref(false)
const admin = computed(() => auth.user?.role === 'ADMIN')
const stats = ref<Record<string, number>>({}), courses = ref<Course[]>([]), sessions = ref<LabSession[]>([]), scores = ref<Score[]>([]), progress = ref<Progress[]>([])
const completed = computed(() => new Set(progress.value.filter(p => p.completed).map(p => p.lesson_id)))
const average = computed(() => { const rows = scores.value.filter(s => s.attempted); return rows.length ? Math.round(rows.reduce((a, b) => a + b.score, 0) / rows.length) : 0 })
const cards = computed(() => admin.value ? [
  { label: '学生人数', value: stats.value.students || 0, note: '已注册学生', icon: Reading },
  { label: '已发布课程', value: stats.value.published_courses || 0, note: '理论学习内容', icon: Reading },
  { label: '已发布实验', value: stats.value.published_labs || 0, note: '可供学生实践', icon: Monitor },
  { label: '当前运行实验', value: stats.value.running_sessions || 0, note: '独立实验环境', icon: Monitor },
  { label: '今日完成实验', value: stats.value.completed_today || 0, note: '正确提交记录', icon: Finished },
] : [
  { label: '当前课程', value: courses.value.length, note: '构建你的知识体系', icon: Reading },
  { label: '已学课时', value: completed.value.size, note: '每一步，都有积累', icon: Finished },
  { label: '已完成实验', value: scores.value.filter(s => s.completed).length, note: '让知识经得起验证', icon: Monitor },
  { label: '平均成绩', value: average.value, note: '按已尝试实验统计', icon: Trophy },
])
const nextCourse = computed(() => courses.value.find(c => percent(c) > 0 && percent(c) < 100) || courses.value.find(c => percent(c) < 100) || courses.value[0])
const today = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' }).format(new Date())
function percent(course: Course) { const lessons = course.chapters.flatMap(c => c.lessons); return lessons.length ? Math.round(lessons.filter(l => completed.value.has(l.id)).length / lessons.length * 100) : 0 }
async function load() {
  busy.value = true; failed.value = false
  try {
    if (admin.value) [stats.value, sessions.value] = await Promise.all([get<Record<string, number>>('/admin/dashboard'), get<LabSession[]>('/admin/lab-sessions')])
    else [courses.value, sessions.value, scores.value, progress.value] = await Promise.all([get<Course[]>('/courses'), get<LabSession[]>('/me/sessions'), get<Score[]>('/me/scores'), get<Progress[]>('/me/progress')])
  } catch { failed.value = true } finally { busy.value = false }
}
onMounted(load)
</script>

<template>
  <div v-loading="busy" class="dashboard">
    <div class="page-heading">
      <div>
        <div class="eyebrow"><span class="eyebrow-line"/>{{ admin ? 'TEACHING OVERVIEW' : 'YOUR LEARNING WORKSPACE' }}</div>
        <h1>{{ admin ? '教学平台概览' : `你好，${auth.user?.real_name || auth.user?.username}` }}<span v-if="!admin" class="greeting-dot">.</span></h1>
        <p class="muted">{{ admin ? '掌握教学进度，让每一次实践顺利发生。' : '保持好奇，动手求证。今天也离安全世界更近一步。' }}</p>
      </div>
      <div class="dashboard-date"><span>WORKSPACE / {{ admin ? 'ADMIN' : 'STUDENT' }}</span><time>{{ today }}</time></div>
    </div>

    <div v-if="failed" class="load-error" role="alert">工作台数据暂时无法加载。<el-button link type="primary" @click="load">重新加载</el-button></div>

    <div v-if="!admin" class="dashboard-feature">
      <section class="lab-feature">
        <div class="feature-copy">
          <span class="feature-tag"><span/> 理论之外，亲手探索</span>
          <h2>真正的理解，<br/>从<span>实践</span>开始。</h2>
          <p>走进独立实验环境，把每一个「为什么」<br/>变成你亲手验证的答案。</p>
          <router-link to="/labs" class="action-link action-accent">探索实验空间 <el-icon><TopRight/></el-icon></router-link>
          <div class="feature-footnote">KALI DESKTOP <span>／</span> 浏览器即实验室</div>
        </div>
        <div class="network-art" aria-hidden="true">
          <span class="diagram-label">ISOLATED LAB / 01</span>
          <svg viewBox="0 0 300 280" fill="none">
            <circle cx="150" cy="140" r="111" stroke="currentColor" stroke-dasharray="3 7"/>
            <circle cx="150" cy="140" r="78" stroke="currentColor"/>
            <path d="M150 33V85M40 140H95M205 140H260M150 195V245" stroke="currentColor"/>
            <path d="M73 63L111 101M189 179L227 217M227 63L189 101M73 217L111 179" stroke="currentColor" stroke-dasharray="4 5"/>
            <rect x="101" y="91" width="98" height="98" rx="20" fill="#223d36" stroke="#a6bb9e"/>
            <path d="M124 125L142 140L124 155M152 156H176" stroke="#e7edca" stroke-width="4"/>
            <rect x="134" y="14" width="32" height="32" rx="8" fill="#dce6cb"/><path d="M143 30L148 35L157 25" stroke="#25463a" stroke-width="2"/>
            <rect x="242" y="124" width="32" height="32" rx="8" fill="#e69970"/><path d="M251 135H265M251 141H261M251 147H265" stroke="#3b3025" stroke-width="2"/>
            <circle cx="40" cy="140" r="6" fill="#dce6cb"/><circle cx="150" cy="246" r="6" fill="#dce6cb"/>
          </svg>
          <div class="diagram-caption"><span class="status-dot"/> 独立环境 · 专注探索</div>
        </div>
      </section>
      <section class="learning-note">
        <div class="note-heading"><span class="eyebrow">CONTINUE LEARNING</span><el-icon><Reading/></el-icon></div>
        <span class="note-step">下一站 / 知识进阶</span>
        <h2>{{ nextCourse?.name || '从第一门课开始' }}</h2>
        <p>{{ nextCourse ? '拾起上次的思路，让新的知识继续生长。' : '循序渐进理解原理，再到实验中亲手验证。' }}</p>
        <template v-if="nextCourse">
          <div class="progress-label"><span>课程学习进度</span><strong>{{ percent(nextCourse) }}<small>%</small></strong></div>
          <el-progress :percentage="percent(nextCourse)" :show-text="false" :stroke-width="5"/>
        </template>
        <router-link :to="nextCourse ? `/courses/${nextCourse.id}` : '/courses'" class="note-link">{{ nextCourse && percent(nextCourse) > 0 ? '继续学习' : '开始学习' }}<el-icon><ArrowRight/></el-icon></router-link>
      </section>
    </div>

    <div class="stat-grid" :class="{ 'admin-stats': admin }">
      <div v-for="(card, index) in cards" :key="card.label" class="stat-card">
        <div class="stat-label"><span>{{ card.label }}</span><el-icon><component :is="card.icon"/></el-icon></div>
        <strong>{{ busy || failed ? '—' : card.value }}<small v-if="card.label === '平均成绩'">/ 100</small></strong>
        <div class="stat-foot"><small>{{ card.note }}</small><span>0{{ index + 1 }}</span></div>
      </div>
    </div>

    <template v-if="!admin">
      <div class="section-heading"><h2><span class="section-index">01 /</span> 我的课程</h2><router-link to="/courses">全部课程 <span aria-hidden="true">↗</span></router-link></div>
      <div class="course-grid dashboard-courses">
        <router-link v-for="(course, index) in courses.slice(0, 3)" :key="course.id" :to="`/courses/${course.id}`" class="panel course-card" :class="`course-tone-${index % 3}`">
          <div class="course-card-heading"><span class="course-symbol"><el-icon><Reading/></el-icon></span><span class="course-code">COURSE / {{ String(index + 1).padStart(2, '0') }}</span><span class="course-arrow">↗</span></div>
          <h3>{{ course.name }}</h3>
          <p class="muted clamp-two">{{ course.description }}</p>
          <div class="progress-label"><span>{{ course.chapters.length }} 个章节</span><span>已学习 <strong>{{ percent(course) }}%</strong></span></div>
          <el-progress :percentage="percent(course)" :show-text="false" :stroke-width="4" />
        </router-link>
      </div>
      <el-empty v-if="!busy && !failed && !courses.length" description="课程正在准备中，稍后再来探索" />
    </template>

    <section class="panel recent-sessions">
      <div class="section-heading"><h2><span class="section-index">{{ admin ? '01' : '02' }} /</span> 最近实验</h2><router-link :to="admin ? '/admin/sessions' : '/labs'">{{ admin ? '查看运行实例' : '前往实验空间' }} ↗</router-link></div>
      <el-table :data="sessions.slice(0, 6)" empty-text="还没有实验记录，去开启第一次探索吧">
        <el-table-column prop="lab_name" label="实验名称" min-width="180"/>
        <el-table-column label="状态" width="130"><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column>
        <el-table-column label="启动时间" min-width="180"><template #default="{ row }">{{ date(row.started_at) }}</template></el-table-column>
        <el-table-column label="操作" width="100"><template #default="{ row }"><router-link :to="`/sessions/${row.id}`">查看 →</router-link></template></el-table-column>
      </el-table>
    </section>
  </div>
</template>
