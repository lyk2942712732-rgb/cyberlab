<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { get, remove } from '../../api/http'
import type { TargetImage } from '../../types'
import { date } from '../../types'
import StatusTag from '../../components/StatusTag.vue'
const images = ref<TargetImage[]>([]), name = ref(''), file = ref<File>(), uploading = ref(false), progress = ref(0), input = ref<HTMLInputElement>()
let poll: ReturnType<typeof setTimeout> | undefined, disposed = false
function choose(event: Event) { file.value = (event.target as HTMLInputElement).files?.[0] }
async function load() { try { const data = await get<TargetImage[]>('/admin/images'); if (!disposed) images.value = data } catch {} finally { if (!disposed) poll = setTimeout(load, 5000) } }
async function upload() {
  if (!file.value || !file.value.name.toLowerCase().endsWith('.tar')) return ElMessage.warning('请选择 .tar 镜像文件')
  if (!name.value.trim()) return ElMessage.warning('请输入镜像名称')
  if (file.value.size > 1024 * 1024 * 1024) return ElMessage.warning('上传文件不得超过 1 GB')
  const data = new FormData(); data.append('display_name', name.value); data.append('file', file.value)
  uploading.value = true; progress.value = 0
  try { await http.post('/admin/images/upload', data, { timeout: 0, onUploadProgress: e => { progress.value = Math.round((e.loaded / (e.total || 1)) * 100) } }); ElMessage.success('上传成功，后台正在导入'); file.value = undefined; name.value = ''; if (input.value) input.value.value = ''; clearTimeout(poll); await load() } catch {} finally { uploading.value = false }
}
async function erase(id: string) { try { await ElMessageBox.confirm('确认删除此 Docker 镜像及目录记录？被实验模板或容器使用时会拒绝删除。', '删除镜像', { type: 'warning' }) } catch { return } try { await remove(`/admin/images/${id}`); clearTimeout(poll); await load() } catch {} }
onMounted(load); onBeforeUnmount(() => { disposed = true; clearTimeout(poll) })
</script>
<template>
<div>
<div class="page-heading">
<div>
<div class="eyebrow">YOUR TARGET LIBRARY</div>
<h1>镜像管理</h1>
<p class="muted">上传靶机镜像，为每个实验准备可复用的运行环境。</p>
</div>
</div>
<section class="panel upload-panel">
<div>
<span class="upload-symbol">↑</span>
<h2>导入靶机镜像</h2>
<p class="muted">支持 Docker save 导出的单镜像 .tar 文件，最大 1 GB。</p>
</div>
<form class="upload-form" @submit.prevent="upload">
<el-input v-model="name" placeholder="镜像名称，例如 SQL 注入基础靶机" maxlength="200" required/>
<input ref="input" type="file" accept=".tar" aria-label="选择 Docker 镜像 tar 文件" :disabled="uploading" @change="choose"/>
<el-progress v-if="uploading" :percentage="progress"/>
<el-button type="primary" native-type="submit" :loading="uploading">{{ uploading ? '正在上传…' : '上传并导入' }}</el-button>
</form>
</section>
<section class="panel">
<div class="section-heading">
<h2>镜像仓库</h2>
<span class="muted">{{ images.length }} 个镜像</span>
</div>
<el-table :data="images" empty-text="上传第一个靶机镜像">
<el-table-column prop="display_name" label="名称" min-width="150"/>
<el-table-column label="Repository / Tag" min-width="250">
<template #default="{ row }">
<code class="small">{{ row.repository ? `${row.repository}:${row.tag}` : '等待导入' }}</code>
</template>
</el-table-column>
<el-table-column label="大小" width="110">
<template #default="{ row }">{{ (row.size_bytes / 1024 / 1024).toFixed(1) }} MB</template>
</el-table-column>
<el-table-column label="状态" min-width="150">
<template #default="{ row }">
<StatusTag :status="row.status"/>
<p v-if="row.error_message" class="error-text small">{{ row.error_message }}</p>
</template>
</el-table-column>
<el-table-column prop="original_filename" label="原文件名" min-width="150"/>
<el-table-column label="镜像引用" min-width="220">
<template #default="{ row }">
<code class="small">{{ row.image_id || '—' }}</code>
<small class="table-subline">{{ row.repo_digest || '本地镜像无仓库摘要' }}</small>
<code class="table-subline small">ID: {{ row.id }}</code>
</template>
</el-table-column>
<el-table-column label="创建时间" min-width="190">
<template #default="{ row }">{{ date(row.created_at) }}</template>
</el-table-column>
<el-table-column width="80">
<template #default="{ row }">
<el-button type="danger" link :disabled="row.status === 'IMPORTING'" @click="erase(row.id)">删除</el-button>
</template>
</el-table-column>
</el-table>
</section>
</div>
</template>
