<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { get, post, put, remove } from '../../api/http'
import type { Lab, TargetImage } from '../../types'
import { difficulty } from '../../types'
import StatusTag from '../../components/StatusTag.vue'
const labs = ref<Lab[]>([]), images = ref<TargetImage[]>([]), dialog = ref(false), busy = ref(false), saving = ref(false), editing = ref('')
const defaults = () => ({ name: '', description: '', objective: '', steps: '', category: 'Web 安全', difficulty: 'BEGINNER', target_image_id: '', target_port: 80, duration_minutes: 120, cpu_limit: 1, memory_limit: 512, flag: '', status: 'DRAFT' })
const form = reactive(defaults())
async function load() { busy.value = true; try { [labs.value, images.value] = await Promise.all([get<Lab[]>('/labs'), get<TargetImage[]>('/admin/images')]) } catch {} finally { busy.value = false } }
async function open(id = '') { editing.value = id; Object.assign(form, defaults()); if (id) { try { const lab = await get<Lab>(`/admin/labs/${id}`); for (const key of Object.keys(defaults()) as (keyof typeof form)[]) (form as Record<string, unknown>)[key] = lab[key] } catch { return } } dialog.value = true }
async function save() { saving.value = true; try { if (editing.value) await put(`/admin/labs/${editing.value}`, form); else await post('/admin/labs', form); ElMessage.success('实验模板已保存'); dialog.value = false; await load() } catch {} finally { saving.value = false } }
async function erase(id: string) { try { await ElMessageBox.confirm('有关联历史记录的实验将下架保留成绩，其余实验将删除。', '删除实验', { type: 'warning' }) } catch { return } try { await remove(`/admin/labs/${id}`); await load() } catch {} }
onMounted(load)
</script>
<template>
<div v-loading="busy">
<div class="page-heading">
<div>
<div class="eyebrow">DESIGN HANDS-ON LEARNING</div>
<h1>实验管理</h1>
<p class="muted">配置实验目标、靶机镜像与判题规则。</p>
</div>
<el-button type="primary" size="large" @click="open()">＋ 新建实验</el-button>
</div>
<section class="panel">
<el-table :data="labs" empty-text="还没有实验模板">
<el-table-column prop="name" label="实验名称" min-width="200"/>
<el-table-column label="难度" width="100">
<template #default="{ row }">{{ difficulty[row.difficulty] }}</template>
</el-table-column>
<el-table-column prop="duration_minutes" label="时长 / 分钟" width="120"/>
<el-table-column label="靶机资源" min-width="150">
<template #default="{ row }">{{ row.cpu_limit }} 核 / {{ row.memory_limit }} MB</template>
</el-table-column>
<el-table-column label="状态" width="120">
<template #default="{ row }">
<StatusTag :status="row.status"/>
</template>
</el-table-column>
<el-table-column label="操作" width="140">
<template #default="{ row }">
<el-button link type="primary" @click="open(row.id)">编辑</el-button>
<el-button link type="danger" @click="erase(row.id)">删除</el-button>
</template>
</el-table-column>
</el-table>
</section>
<el-dialog v-model="dialog" :title="editing ? '编辑实验模板' : '新建实验模板'" width="min(800px, 94vw)">
<el-form label-position="top">
<div class="form-grid">
<el-form-item label="实验名称" required>
<el-input v-model="form.name" maxlength="200"/>
</el-form-item>
<el-form-item label="分类">
<el-input v-model="form.category" maxlength="64"/>
</el-form-item>
</div>
<el-form-item label="实验介绍">
<el-input v-model="form.description" type="textarea" :rows="2"/>
</el-form-item>
<el-form-item label="实验目标（Markdown）">
<el-input v-model="form.objective" type="textarea" :rows="3"/>
</el-form-item>
<el-form-item label="实验步骤（Markdown）">
<el-input v-model="form.steps" type="textarea" :rows="5"/>
</el-form-item>
<div class="form-grid">
<el-form-item label="靶机镜像" required>
<el-select v-model="form.target_image_id" filterable class="full-width" placeholder="请选择已导入的镜像">
<el-option v-for="image in images.filter(i => i.status === 'READY')" :key="image.id" :value="image.id" :label="`${image.display_name} (${image.tag})`"/>
</el-select>
</el-form-item>
<el-form-item label="难度">
<el-select v-model="form.difficulty" class="full-width">
<el-option v-for="(label, key) in difficulty" :key="key" :value="key" :label="label"/>
</el-select>
</el-form-item>
<el-form-item label="靶机内部端口（明确填写，不对宿主机开放）" required>
<el-input-number v-model="form.target_port" :min="1" :max="65535"/>
</el-form-item>
<el-form-item label="时长（分钟）">
<el-input-number v-model="form.duration_minutes" :min="5" :max="480"/>
</el-form-item>
<el-form-item label="CPU（核）">
<el-input-number v-model="form.cpu_limit" :min="0.25" :max="4" :step="0.25"/>
</el-form-item>
<el-form-item label="内存（MB）">
<el-input-number v-model="form.memory_limit" :min="64" :max="4096" :step="64"/>
</el-form-item>
<el-form-item label="Flag（仅教学管理端可见）" required>
<el-input v-model="form.flag" type="password" show-password maxlength="512" placeholder="flag{...}"/>
</el-form-item>
</div>
<el-form-item label="发布状态">
<el-radio-group v-model="form.status">
<el-radio-button value="DRAFT">草稿</el-radio-button>
<el-radio-button value="PUBLISHED">发布</el-radio-button>
<el-radio-button value="DISABLED">下架</el-radio-button>
</el-radio-group>
</el-form-item>
<p class="muted small">有运行实例时暂不可修改模板。判题 Flag 应与靶机内的 Flag 一致。演示镜像支持 LAB_FLAG 环境变量，其他成品镜像可使用其已有 Flag。</p>
</el-form>
<template #footer>
<el-button @click="dialog = false">取消</el-button>
<el-button type="primary" :loading="saving" @click="save">保存实验</el-button>
</template>
</el-dialog>
</div>
</template>
