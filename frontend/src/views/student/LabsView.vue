<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { get } from '../../api/http'
import type { Lab, Score } from '../../types'
import { difficulty } from '../../types'
const labs = ref<Lab[]>([]), scores = ref<Score[]>([]), search = ref(''), level = ref(''), busy = ref(true)
const filtered = computed(() => labs.value.filter(l => l.name.toLowerCase().includes(search.value.toLowerCase()) && (!level.value || l.difficulty === level.value)))
onMounted(async () => { try { [labs.value, scores.value] = await Promise.all([get<Lab[]>('/labs'), get<Score[]>('/me/scores')]) } catch {} finally { busy.value = false } })
</script>
<template>
<div v-loading="busy">
<div class="page-heading">
<div>
<div class="eyebrow">A SPACE TO EXPERIMENT</div>
<h1>实验空间</h1>
<p class="muted">在专属环境中动手实践，把每个知识点变成你的经验。</p>
</div>
<span class="count-pill">{{ labs.length }} 个实验</span>
</div>
<div class="filter-bar">
<el-input v-model="search" placeholder="搜索实验名称" clearable style="max-width:320px"/>
<el-select v-model="level" placeholder="全部难度" clearable style="width:150px">
<el-option v-for="(label, key) in difficulty" :key="key" :value="key" :label="label"/>
</el-select>
</div>
<div class="lab-grid">
<article v-for="(lab, index) in filtered" :key="lab.id" class="panel lab-card">
<div class="lab-card-top">
<span class="lab-number">LAB / {{ String(index + 1).padStart(2, '0') }}</span>
<el-tag effect="plain" round>{{ difficulty[lab.difficulty] }}</el-tag>
</div>
<div class="lab-icon">&gt;_</div>
<span class="eyebrow">{{ lab.category }}</span>
<h2>{{ lab.name }}</h2>
<p class="muted clamp-two">{{ lab.description }}</p>
<div class="lab-meta">
<span>◷ {{ lab.duration_minutes }} 分钟</span>
<span>{{ scores.find(s => s.lab_id === lab.id)?.completed ? '✓ 已完成 · 100 分' : '等待你的探索' }}</span>
</div>
<router-link :to="`/labs/${lab.id}`" class="card-link">查看实验 <span>↗</span>
</router-link>
</article>
</div>
<el-empty v-if="!busy && !filtered.length" description="暂无符合条件的实验"/>
</div>
</template>
