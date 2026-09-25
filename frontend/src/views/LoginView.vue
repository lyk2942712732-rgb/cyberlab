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
<h1>读懂原理，<br/>再亲手验证一次。</h1>
<p>CyberLab 把理论课程与隔离实验环境放在同一个工作台上。学完一章，就在专属的 Kali 桌面里把它跑通。</p>
<div class="terminal-art">
<div class="terminal-bar">
<i/><i/><i/>
<span>student@kali: ~/labs</span>
</div>
<p><b>student@kali</b>:~/labs$ lab start --isolate</p>
<p class="terminal-output">[ ok ] 分配独立网络 172.20.0.0/24</p>
<p class="terminal-output">[ ok ] 靶机已就绪，等待连接</p>
<p class="terminal-output">[ ok ] 浏览器已接管 Kali 桌面</p>
<p class="terminal-ready">环境将在到期后自动回收。</p>
<p><b>$</b> <span class="cursor">▊</span></p>
</div>
</div>
<small>教学与授权实验用途，所有操作均被记录。</small>
</section>
<section class="login-form">
<div class="login-card">
<h2>{{ registering ? '创建学生账号' : '登录 CyberLab' }}</h2>
<p class="muted">{{ registering ? '注册后即可开始课程学习与实验。' : '使用你的账号继续学习与实验。' }}</p>
<el-form :model="form" label-position="top" @submit.prevent="submit">
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
<el-button class="full-width" type="primary" native-type="submit" size="large" :loading="busy">{{ registering ? '注册学生账号' : '登录工作台' }}</el-button>
</el-form>
<p class="login-toggle">{{ registering ? '已有账号？' : '还没有账号？' }}<el-button link type="primary" @click="registering = !registering">{{ registering ? '返回登录' : '注册学生账号' }}</el-button>
</p>
<div class="login-hint">教师与管理员统一使用教学管理端账号登录。</div>
</div>
</section>
</div>
</template>
