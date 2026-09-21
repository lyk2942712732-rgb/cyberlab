<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuth } from '../stores/auth'
import { post } from '../api/http'
const auth = useAuth(), router = useRouter(), registering = ref(false), busy = ref(false)
const form = reactive({ username: '', password: '', real_name: '', student_number: '' })
async function submit() {
  busy.value = true
  try {
    if (registering.value) { await post('/auth/register', form); ElMessage.success('注册成功，请登录'); registering.value = false }
    else { await auth.login(form.username, form.password); await router.push('/') }
  } catch { /* API interceptor displays actionable errors. */ } finally { busy.value = false }
}
</script>
<template>
<div class="login-page">
<section class="login-story">
<div class="brand">
<span class="brand-mark">C<span>_</span>
</span>CyberLab</div>
<div class="login-story-copy">
<div class="eyebrow light">LEARN. EXPLORE. SECURE.</div>
<h1>让安全知识，<br/>在实践中发生。</h1>
<p>连接理论与真实环境的网络安全学习空间。<br/>从第一行命令开始，构建你的安全能力。</p>
<div class="terminal-art">
<div class="terminal-bar">
<i/>
<i/>
<i/>
<span>cyberlab ~ learning</span>
</div>
<p>
<b>student@cyberlab</b>:~$ start learning</p>
<p class="terminal-output">✓ 理论课程已就绪<br/>✓ 独立实验环境<br/>✓ 浏览器直达 Kali Desktop</p>
<p>
<b>➜</b> <span class="cursor">_</span>
</p>
</div>
</div>
<small>专为网络安全教学与授权实验设计</small>
</section>
<section class="login-form">
<div class="login-card">
<div class="eyebrow">YOUR NEXT CHAPTER</div>
<h2>{{ registering ? '开启学习之旅' : '欢迎回到 CyberLab' }}</h2>
<p class="muted">{{ registering ? '创建学生账号，开始学习与实验。' : '登录你的账号，继续探索安全世界。' }}</p>
<form @submit.prevent="submit">
<el-form label-position="top">
<el-form-item label="用户名">
<el-input v-model="form.username" minlength="3" maxlength="64" required autocomplete="username" placeholder="请输入用户名" size="large" />
</el-form-item>
<el-form-item v-if="registering" label="姓名">
<el-input v-model="form.real_name" maxlength="100" autocomplete="name" size="large" />
</el-form-item>
<el-form-item v-if="registering" label="学号">
<el-input v-model="form.student_number" required maxlength="64" size="large" />
</el-form-item>
<el-form-item label="密码">
<el-input v-model="form.password" type="password" show-password minlength="8" maxlength="128" required :autocomplete="registering ? 'new-password' : 'current-password'" placeholder="至少 8 位密码" size="large" />
</el-form-item>
<el-button class="full-width" type="primary" native-type="submit" size="large" :loading="busy">{{ registering ? '注册学生账号' : '登录工作台 →' }}</el-button>
</el-form>
</form>
<p class="login-toggle">{{ registering ? '已有账号？' : '还没有账号？' }}<el-button link type="primary" @click="registering = !registering">{{ registering ? '返回登录' : '注册学生账号' }}</el-button>
</p>
<div class="login-hint">教师与管理员统一使用教学管理端账号登录。</div>
</div>
</section>
</div>
</template>
