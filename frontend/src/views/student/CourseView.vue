<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { get, post } from '../../api/http'
import type { Course, Lesson, Progress } from '../../types'
import MarkdownContent from '../../components/MarkdownContent.vue'
const route = useRoute(), course = ref<Course>(), lesson = ref<Lesson>(), progress = ref<Progress[]>([]), busy = ref(true), saving = ref(false)
async function selectLesson(id: string) { try { lesson.value = await get<Lesson>(`/lessons/${id}`) } catch {} }
async function complete() { if (!lesson.value) return; saving.value = true; try { await post(`/lessons/${lesson.value.id}/complete`); progress.value = await get<Progress[]>('/me/progress'); ElMessage.success('学习进度已记录') } catch {} finally { saving.value = false } }
onMounted(async () => { try { [course.value, progress.value] = await Promise.all([get<Course>(`/courses/${route.params.id}`), get<Progress[]>('/me/progress')]); const first = course.value.chapters.flatMap(c => c.lessons)[0]; if (first) await selectLesson(first.id) } catch {} finally { busy.value = false } })
</script>
<template>
<div v-loading="busy">
<div class="page-heading">
<div>
<router-link to="/courses" class="back-link">← 课程中心</router-link>
<h1>{{ course?.name || '理论学习' }}</h1>
<p class="muted">{{ course?.description }}</p>
</div>
</div>
<div class="learning-layout">
<aside class="panel lesson-directory">
<h2>课程目录</h2>
<section v-for="(chapter, i) in course?.chapters" :key="chapter.id">
<h3><span>{{ String(i + 1).padStart(2, '0') }}</span>{{ chapter.title }}</h3>
<button v-for="item in chapter.lessons" :key="item.id" :class="['lesson-link', { active: lesson?.id === item.id }]" @click="selectLesson(item.id)">
<span class="lesson-mark" :class="{ done: progress.some(p => p.lesson_id === item.id) }">✓</span>{{ item.title }}</button>
</section>
</aside>
<article class="panel lesson-article">
<template v-if="lesson">
<h1>{{ lesson.title }}</h1>
<MarkdownContent :content="lesson.content"/>
<div class="lesson-actions">
<el-button type="primary" :loading="saving" :disabled="progress.some(p => p.lesson_id === lesson?.id)" @click="complete">{{ progress.some(p => p.lesson_id === lesson?.id) ? '✓ 已完成学习' : '标记为已完成' }}</el-button>
<router-link v-if="lesson.related_lab_id" :to="`/labs/${lesson.related_lab_id}`">
<el-button>进入关联实验</el-button>
</router-link>
</div>
</template>
<el-empty v-else description="暂无已发布课时"/>
</article>
</div>
</div>
</template>
