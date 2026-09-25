<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Reading, Monitor, Trophy, Finished, ArrowRight } from '@element-plus/icons-vue'
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
function lessonCount(course: Course) { return course.chapters.reduce((n, c) => n + c.lessons.length, 0) }
function chapterCount(course: Course) { return Math.max(1, course.chapters.length) }
function spineSegments(course: Course) { return Math.min(14, Math.max(4, lessonCount(course))) }
function spineDone(course: Course) { const all = course.chapters.flatMap(c => c.lessons); return all.length ? Math.round(spineSegments(course) * all.filter(l => completed.value.has(l.id)).length / all.length) : 0 }
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
        <h1>{{ admin ? '教学平台概览' : `你好，${auth.user?.real_name || auth.user?.username}` }}<span v-if="!admin" class="greeting-dot">.</span></h1>
        <p class="muted">{{ admin ? '掌握教学进度，让每一次实践顺利发生。' : '保持好奇，动手求证。今天也离安全世界更近一步。' }}</p>
      </div>
      <div class="dashboard-date"><time>{{ today }}</time></div>
    </div>

    <div v-if="failed" class="load-error" role="alert">工作台数据暂时无法加载。<el-button link type="primary" @click="load">重新加载</el-button></div>

    <div v-if="!admin" class="dashboard-feature">
      <section class="lab-feature">
        <div class="feature-copy">
          <span class="feature-tag"><span/> 独立实验环境</span>
          <h2>真正的理解，从亲手验证开始</h2>
          <p>每个实验都运行在隔离网络中：一台 Kali 攻击机、一台靶机，浏览器即实验室。</p>
          <router-link to="/labs" class="action-link">进入实验空间</router-link>
          <div class="feature-footnote">实验到期自动回收，环境互相隔离</div>
        </div>
        <div class="network-art" aria-hidden="true">
          <svg viewBox="0 0 300 280" fill="none">
            <circle cx="150" cy="140" r="112" stroke="currentColor" stroke-dasharray="3 7" opacity=".55"/>
            <circle cx="150" cy="140" r="78" stroke="currentColor" opacity=".8"/>
            <path id="link-h" d="M40 140H102M198 140H258" stroke="currentColor"/>
            <path id="link-v" d="M150 34V92M150 188V246" stroke="currentColor"/>
            <rect class="node-core" x="102" y="92" width="96" height="96" rx="14" fill="#0e241d" stroke="#2f6b52"/>
            <path d="M126 126L146 141L126 156M156 157H180" stroke="#6ee7b7" stroke-width="4" stroke-linecap="round"/>
            <rect x="134" y="16" width="32" height="30" rx="7" fill="#14382d" stroke="#2f6b52"/>
            <path d="M143 31L148 36L158 25" stroke="#6ee7b7" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
            <rect class="node-target" x="242" y="125" width="32" height="30" rx="7" fill="#2b1d07" stroke="#a1761b"/>
            <path d="M251 134H266M251 140H262M251 146H266" stroke="#fbbf24" stroke-width="2" stroke-linecap="round"/>
            <rect x="26" y="125" width="32" height="30" rx="7" fill="#14382d" stroke="#2f6b52"/>
            <path d="M35 140H50M45 134L51 140L45 146" stroke="#6ee7b7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <rect x="134" y="234" width="32" height="30" rx="7" fill="#14382d" stroke="#2f6b52"/>
            <circle cx="150" cy="249" r="6" fill="none" stroke="#6ee7b7" stroke-width="2"/>
            <circle cx="42" cy="140" r="3.5" fill="#34d399">
              <animateMotion dur="2.4s" repeatCount="indefinite" path="M42 140H102" begin="0s"/>
            </circle>
            <circle cx="198" cy="140" r="3.5" fill="#fbbf24">
              <animateMotion dur="2.4s" repeatCount="indefinite" path="M198 140H258" begin="1.2s"/>
            </circle>
            <circle cx="150" cy="46" r="3.5" fill="#34d399">
              <animateMotion dur="2.4s" repeatCount="indefinite" path="M150 46V92" begin=".6s"/>
            </circle>
          </svg>
          <div class="diagram-caption"><span class="status-dot live"/> 隔离网络：攻击机、靶机与判题服务</div>
        </div>
      </section>
      <section class="learning-note">
        <div class="note-heading"><el-icon><Reading/></el-icon> 继续学习</div>
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
      <div v-for="card in cards" :key="card.label" class="stat-card">
        <div class="stat-label"><span>{{ card.label }}</span><el-icon><component :is="card.icon"/></el-icon></div>
        <strong>{{ busy || failed ? '—' : card.value }}<small v-if="card.label === '平均成绩'">/ 100</small></strong>
        <div class="stat-foot"><small>{{ card.note }}</small></div>
      </div>
    </div>

    <template v-if="!admin">
      <div class="section-heading"><h2>我的课程</h2><router-link to="/courses">查看全部课程</router-link></div>
      <div class="course-grid dashboard-courses">
        <router-link v-for="course in courses.slice(0, 3)" :key="course.id" :to="`/courses/${course.id}`" class="panel course-card">
          <div class="course-cover">
            <div class="cover-spine" aria-hidden="true"><i v-for="n in spineSegments(course)" :key="n" :class="{ done: n <= spineDone(course) }"/></div>
            <p><b>{{ chapterCount(course) }}</b> 章 <b>{{ lessonCount(course) }}</b> 课时</p>
          </div>
          <h3>{{ course.name }}</h3>
          <p class="muted clamp-two">{{ course.description }}</p>
          <div class="progress-label"><span>学习进度</span><span><strong>{{ percent(course) }}%</strong></span></div>
          <el-progress :percentage="percent(course)" :show-text="false" :stroke-width="4"/>
          <span class="card-link">{{ percent(course) === 100 ? '回顾课程' : percent(course) ? '继续学习' : '开始学习' }}</span>
        </router-link>
      </div>
      <el-empty v-if="!busy && !failed && !courses.length" description="课程正在准备中，稍后再来探索" />
    </template>

    <section class="panel recent-sessions">
      <div class="section-heading"><h2>最近实验</h2><router-link :to="admin ? '/admin/sessions' : '/labs'">{{ admin ? '查看全部运行实例' : '前往实验空间' }}</router-link></div>
      <el-table :data="sessions.slice(0, 6)" empty-text="还没有实验记录，去开启第一次探索吧">
        <el-table-column prop="lab_name" label="实验名称" min-width="180"/>
        <el-table-column label="状态" width="130"><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column>
        <el-table-column label="启动时间" min-width="180"><template #default="{ row }">{{ date(row.started_at) }}</template></el-table-column>
        <el-table-column label="操作" width="100"><template #default="{ row }"><router-link :to="`/sessions/${row.id}`">查看</router-link></template></el-table-column>
      </el-table>
    </section>
  </div>
</template>
