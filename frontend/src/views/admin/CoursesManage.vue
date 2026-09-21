<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { get, post, put, remove } from '../../api/http'
import type { Chapter, Course, Lab, Lesson } from '../../types'
import StatusTag from '../../components/StatusTag.vue'
import MarkdownContent from '../../components/MarkdownContent.vue'
const courses = ref<Course[]>([]), labs = ref<Lab[]>([]), busy = ref(false), dialog = ref(false), kind = ref<'courses' | 'chapters' | 'lessons'>('courses'), editing = ref(''), saving = ref(false)
const form = reactive({ name: '', description: '', status: 'DRAFT', course_id: '', chapter_id: '', title: '', sort_order: 0, content: '', related_lab_id: '' })
async function load() { busy.value = true; try { [courses.value, labs.value] = await Promise.all([get<Course[]>('/courses'), get<Lab[]>('/labs')]) } catch {} finally { busy.value = false } }
async function open(type: typeof kind.value, record?: Course | Chapter | Lesson, parent = '') {
  kind.value = type; editing.value = record?.id || ''
  Object.assign(form, { name: '', description: '', status: 'DRAFT', course_id: type === 'chapters' ? parent : '', chapter_id: type === 'lessons' ? parent : '', title: '', sort_order: 0, content: '', related_lab_id: '' })
  if (record) { if (type === 'lessons') { try { Object.assign(form, await get<Lesson>(`/lessons/${record.id}`)) } catch { return } } else Object.assign(form, record) }
  dialog.value = true
}
async function save() {
  const payload = kind.value === 'courses' ? { name: form.name, description: form.description, status: form.status } : kind.value === 'chapters' ? { title: form.title, course_id: form.course_id, sort_order: form.sort_order } : { title: form.title, chapter_id: form.chapter_id, content: form.content, sort_order: form.sort_order, related_lab_id: form.related_lab_id || null, status: form.status }
  saving.value = true
  try { if (editing.value) await put(`/admin/${kind.value}/${editing.value}`, payload); else await post(`/admin/${kind.value}`, payload); dialog.value = false; ElMessage.success('保存成功'); await load() } catch {} finally { saving.value = false }
}
async function erase(type: string, id: string) { try { await ElMessageBox.confirm('删除后将同时移除下属章节、课时及相关学习进度。确认删除？', '删除内容', { type: 'warning' }) } catch { return } try { await remove(`/admin/${type}/${id}`); await load() } catch {} }
onMounted(load)
</script>
<template>
<div v-loading="busy">
<div class="page-heading">
<div>
<div class="eyebrow">BUILD THE LEARNING PATH</div>
<h1>课程管理</h1>
<p class="muted">组织课程、章节与课时，将理论内容连接到实验。</p>
</div>
<el-button type="primary" size="large" @click="open('courses')">＋ 新建课程</el-button>
</div>
<section v-for="course in courses" :key="course.id" class="panel margin-bottom">
<div class="section-heading">
<div>
<h2>{{ course.name }} <StatusTag :status="course.status"/>
</h2>
<p class="muted">{{ course.description }}</p>
</div>
<div class="inline-gap">
<el-button @click="open('chapters', undefined, course.id)">添加章节</el-button>
<el-button @click="open('courses', course)">编辑</el-button>
<el-button type="danger" link @click="erase('courses', course.id)">删除</el-button>
</div>
</div>
<el-collapse>
<el-collapse-item v-for="chapter in course.chapters" :key="chapter.id" :name="chapter.id">
<template #title>
<strong>{{ chapter.sort_order }} · {{ chapter.title }}</strong>
</template>
<div class="chapter-actions">
<el-button size="small" @click="open('lessons', undefined, chapter.id)">＋ 添加课时</el-button>
<el-button size="small" @click="open('chapters', chapter)">编辑章节</el-button>
<el-button size="small" type="danger" link @click="erase('chapters', chapter.id)">删除章节</el-button>
</div>
<el-table :data="chapter.lessons" empty-text="暂无课时">
<el-table-column prop="title" label="课时名称"/>
<el-table-column label="状态" width="130">
<template #default="{ row }">
<StatusTag :status="row.status"/>
</template>
</el-table-column>
<el-table-column label="操作" width="160">
<template #default="{ row }">
<el-button link type="primary" @click="open('lessons', row)">编辑内容</el-button>
<el-button link type="danger" @click="erase('lessons', row.id)">删除</el-button>
</template>
</el-table-column>
</el-table>
</el-collapse-item>
</el-collapse>
</section>
<el-empty v-if="!courses.length && !busy" description="创建第一门课程，开始组织教学内容"/>
<el-dialog v-model="dialog" :title="`${editing ? '编辑' : '新建'}${kind === 'courses' ? '课程' : kind === 'chapters' ? '章节' : '课时'}`" :width="kind === 'lessons' ? 'min(1040px, 94vw)' : 'min(600px, 94vw)'" destroy-on-close>
<el-form label-position="top" @submit.prevent="save">
<el-form-item :label="kind === 'courses' ? '课程名称' : '标题'" required>
<el-input v-if="kind === 'courses'" v-model="form.name" maxlength="200"/>
<el-input v-else v-model="form.title" maxlength="200"/>
</el-form-item>
<el-form-item v-if="kind === 'courses'" label="课程介绍">
<el-input v-model="form.description" type="textarea" :rows="4"/>
</el-form-item>
<el-form-item v-if="kind !== 'courses'" label="排序（从小到大）">
<el-input-number v-model="form.sort_order" :min="0"/>
</el-form-item>
<template v-if="kind === 'lessons'">
<div class="markdown-editor">
<el-form-item label="教学内容（Markdown）">
<el-input v-model="form.content" type="textarea" :rows="16" maxlength="100000"/>
</el-form-item>
<div class="markdown-preview">
<small class="muted">内容预览</small>
<MarkdownContent :content="form.content"/>
</div>
</div>
<el-form-item label="关联实验">
<el-select v-model="form.related_lab_id" clearable filterable class="full-width">
<el-option v-for="lab in labs" :key="lab.id" :value="lab.id" :label="lab.name"/>
</el-select>
</el-form-item>
</template>
<el-form-item v-if="kind !== 'chapters'" label="发布状态">
<el-radio-group v-model="form.status">
<el-radio-button value="DRAFT">草稿</el-radio-button>
<el-radio-button value="PUBLISHED">发布</el-radio-button>
<el-radio-button value="DISABLED">下架</el-radio-button>
</el-radio-group>
</el-form-item>
</el-form>
<template #footer>
<el-button @click="dialog = false">取消</el-button>
<el-button type="primary" :loading="saving" @click="save">保存</el-button>
</template>
</el-dialog>
</div>
</template>
