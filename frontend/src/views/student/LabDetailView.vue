<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post } from '../../api/http'
import type { Lab, LabSession } from '../../types'
import { difficulty } from '../../types'
import MarkdownContent from '../../components/MarkdownContent.vue'
const route = useRoute(), router = useRouter(), lab = ref<Lab>(), busy = ref(false)
onMounted(async () => { try { lab.value = await get<Lab>(`/labs/${route.params.id}`) } catch {} })
async function start() { busy.value = true; try { const session = await post<LabSession>(`/labs/${route.params.id}/sessions`); router.push(`/sessions/${session.id}`) } catch {} finally { busy.value = false } }
</script>
<template>
<div v-if="lab">
<router-link to="/labs" class="back-link">← 实验空间</router-link>
<div class="page-heading">
<div>
<div class="eyebrow">{{ lab.category }} / {{ difficulty[lab.difficulty] }}</div>
<h1>{{ lab.name }}</h1>
<p class="muted">{{ lab.description }}</p>
</div>
</div>
<div class="detail-layout">
<article class="panel">
<h2>实验目标</h2>
<MarkdownContent :content="lab.objective"/>
<div class="divider"/>
<h2>实验说明</h2>
<MarkdownContent :content="lab.steps"/>
</article>
<aside class="panel lab-summary">
<span class="lab-icon">&gt;_</span>
<h2>准备好开始了吗？</h2>
<p class="muted">启动后将为你创建专属 Kali 桌面和靶机环境。</p>
<dl>
<div>
<dt>实验时长</dt>
<dd>{{ lab.duration_minutes }} 分钟</dd>
</div>
<div>
<dt>难度</dt>
<dd>{{ difficulty[lab.difficulty] }}</dd>
</div>
<div>
<dt>内部端口</dt>
<dd>{{ lab.target_port }}</dd>
</div>
<div>
<dt>靶机配置</dt>
<dd>{{ lab.cpu_limit }} 核 / {{ lab.memory_limit }} MB</dd>
</div>
<div>
<dt>实验成绩</dt>
<dd>正确提交 100 分</dd>
</div>
</dl>
<el-button type="primary" size="large" class="full-width" :loading="busy" @click="start">启动实验 ↗</el-button>
<small class="muted">每次仅可运行一个实验；到期自动回收。</small>
</aside>
</div>
</div>
<el-empty v-else description="正在读取实验信息"/>
</template>
