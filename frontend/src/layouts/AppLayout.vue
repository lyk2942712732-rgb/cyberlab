<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { House, Reading, Monitor, Trophy, Collection, Box, User, SwitchButton, ArrowRight, Fold, Expand } from '@element-plus/icons-vue'
import { useAuth } from '../stores/auth'
const auth = useAuth(), route = useRoute(), router = useRouter()
const collapsed = ref(localStorage.getItem('cyberlab-sidebar-collapsed') === 'true' || (localStorage.getItem('cyberlab-sidebar-collapsed') === null && window.innerWidth <= 950))
watch(collapsed, value => localStorage.setItem('cyberlab-sidebar-collapsed', String(value)))
const isAdmin = computed(() => auth.user?.role === 'ADMIN')
const menu = computed(() => isAdmin.value ? [
  { path: '/', label: '首页', icon: House }, { path: '/admin/courses', label: '课程管理', icon: Reading },
  { path: '/admin/labs', label: '实验管理', icon: Collection }, { path: '/admin/images', label: '镜像管理', icon: Box },
  { path: '/admin/students', label: '学生成绩', icon: Trophy }, { path: '/admin/sessions', label: '运行实例', icon: Monitor },
] : [{ path: '/', label: '学习工作台', icon: House }, { path: '/courses', label: '课程中心', icon: Reading }, { path: '/labs', label: '实验空间', icon: Monitor }, { path: '/scores', label: '我的成绩', icon: Trophy }])
function logout() { auth.logout(); router.push('/login') }
</script>
<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': collapsed }">
    <aside class="sidebar">
      <router-link to="/" class="brand">
<span class="brand-mark">C<span>_</span>
</span>
<div>CyberLab<small>网络安全教育实验室</small>
</div>
</router-link>
      <button class="sidebar-toggle" :aria-label="collapsed ? '展开侧栏' : '收起侧栏'" :title="collapsed ? '展开侧栏' : '收起侧栏'" :aria-expanded="!collapsed" @click="collapsed = !collapsed">
        <el-icon><Expand v-if="collapsed"/><Fold v-else/></el-icon><span v-if="!collapsed">收起侧栏</span>
      </button>
      <div class="workspace-label">{{ isAdmin ? '教学管理端' : '学生学习空间' }} <span>{{ isAdmin ? 'ADMIN' : 'LEARN' }}</span>
</div>
      <nav>
<router-link v-for="item in menu" :key="item.path" :to="item.path" :title="item.label" :aria-label="item.label" :aria-current="(item.path === '/' ? route.path === '/' : route.path.startsWith(item.path)) ? 'page' : undefined" :class="{ selected: item.path === '/' ? route.path === '/' : route.path.startsWith(item.path) }">
<el-icon>
<component :is="item.icon" />
</el-icon><span class="nav-label">{{ item.label }}</span><el-icon class="nav-arrow">
<ArrowRight />
</el-icon>
</router-link>
</nav>
      <div class="sidebar-bottom">
<div class="sidebar-note">
<div class="eyebrow">LEARN BY DOING</div>
<p>理解每一个原理，<br/>验证每一种可能。</p>
</div>
<div class="safe-note">
<span class="status-dot" />在独立环境中探索安全</div>
<div class="user-block">
<span class="avatar">{{ (auth.user?.real_name || auth.user?.username || 'U').slice(0, 1) }}</span>
<div>
<strong>{{ auth.user?.real_name || auth.user?.username }}</strong>
<small>{{ isAdmin ? '教学管理员' : auth.user?.student_number || '学生' }}</small>
</div>
<el-button text aria-label="退出登录" @click="logout">
<el-icon>
<SwitchButton />
</el-icon>
</el-button>
</div>
</div>
    </aside>
    <div class="main-shell">
<header class="topbar">
<div>
<span class="muted">CyberLab</span>
<span class="breadcrumb-slash">/</span>{{ isAdmin && route.path === '/' ? '平台概览' : route.meta.title }}</div>
<div class="topbar-right">
<span class="status-dot" />学习 · 实践 · 成长<el-icon>
<User />
</el-icon>
</div>
</header>
<main class="page">
<router-view :key="route.path" />
</main>
<footer class="page-footer">CYBERLAB <span>从理解原理，到亲手验证。</span>
</footer>
</div>
  </div>
</template>
