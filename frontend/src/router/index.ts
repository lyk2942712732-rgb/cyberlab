import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores/auth'

const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/desktop/:id', component: () => import('../views/student/DesktopView.vue') },
  { path: '/', component: () => import('../layouts/AppLayout.vue'), children: [
    { path: '', component: () => import('../views/DashboardView.vue'), meta: { title: '学习工作台' } },
    { path: 'courses', component: () => import('../views/student/CoursesView.vue'), meta: { title: '课程中心' } },
    { path: 'courses/:id', component: () => import('../views/student/CourseView.vue'), meta: { title: '理论学习' } },
    { path: 'labs', component: () => import('../views/student/LabsView.vue'), meta: { title: '实验空间' } },
    { path: 'labs/:id', component: () => import('../views/student/LabDetailView.vue'), meta: { title: '实验详情' } },
    { path: 'sessions/:id', component: () => import('../views/student/SessionView.vue'), meta: { title: '在线实验' } },
    { path: 'scores', component: () => import('../views/student/ScoresView.vue'), meta: { title: '我的成绩' } },
    { path: 'admin/courses', component: () => import('../views/admin/CoursesManage.vue'), meta: { admin: true, title: '课程管理' } },
    { path: 'admin/labs', component: () => import('../views/admin/LabsManage.vue'), meta: { admin: true, title: '实验管理' } },
    { path: 'admin/images', component: () => import('../views/admin/ImagesManage.vue'), meta: { admin: true, title: '镜像管理' } },
    { path: 'admin/students', component: () => import('../views/admin/StudentsView.vue'), meta: { admin: true, title: '学生成绩' } },
    { path: 'admin/sessions', component: () => import('../views/admin/SessionsManage.vue'), meta: { admin: true, title: '运行实例' } },
  ] },
  { path: '/:pathMatch(.*)*', redirect: '/' },
] })
router.beforeEach(async to => {
  if (to.meta.public) return true
  const auth = useAuth()
  if (!sessionStorage.getItem('cyberlab-token')) return '/login'
  if (!auth.user) { try { await auth.load() } catch { return '/login' } }
  if (to.meta.admin && auth.user?.role !== 'ADMIN') return '/'
  document.title = `${String(to.meta.title || 'Kali Desktop')} · CyberLab`
})
export default router
