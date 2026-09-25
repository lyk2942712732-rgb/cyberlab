// Static fixtures for offline UI previews (VITE_MOCK=1). Not used in builds.
import type { Course, Lab, LabSession, Lesson, Progress, Score, User } from '../types'

// Preview-only role switch: set sessionStorage 'cyberlab-role' = 'ADMIN' to browse admin views.
const currentRole = (): 'STUDENT' | 'ADMIN' => (sessionStorage.getItem('cyberlab-role') === 'ADMIN' ? 'ADMIN' : 'STUDENT')
const user: User = { id: 'u1', username: 'lin', real_name: '林同学', student_number: '20260001', role: 'STUDENT' }
const lessons = (courseId: string, chapterId: string, prefix: string, titles: string[]): Lesson[] =>
  titles.map((title, i) => ({ id: `${prefix}${i + 1}`, chapter_id: chapterId, title, sort_order: i, status: 'PUBLISHED', related_lab_id: i === 0 ? 'lab1' : null, course_id: courseId, content: lessonBody(title) }))
function lessonBody(title: string) {
  return `# ${title}

本节用一个最小例子说明攻击面是如何形成的：服务暴露的每一个端口、每一个参数，都是潜在的入口。

## 请求与响应

HTTP 是无状态协议，服务器依靠头部与 Cookie 维持会话。下面是一次典型请求：

\`\`\`http
GET /search?q=1' OR '1'='1 HTTP/1.1
Host: target.lab
Cookie: session=abc123
\`\`\`

> 注意：任何来自客户端的数据都不可信。过滤与参数化必须在服务端完成。

## 常见注入点

| 位置 | 示例 | 风险 |
| --- | --- | --- |
| 查询参数 | \`?id=1\` | SQL 注入 |
| 表单字段 | 登录框 | 命令注入 |
| 请求头 | \`X-Forwarded-For\` | 日志注入 |

行内代码如 \`urldecode()\` 与 **加粗强调** 会出现在正文中，[链接](/labs) 使用强调色。
`
}
const courses: Course[] = [
  { id: 'c1', name: 'Web 安全基础', description: '从 HTTP 协议到常见 Web 漏洞，理解攻防背后的原理。', status: 'PUBLISHED', chapters: [{ id: 'ch1', course_id: 'c1', title: 'HTTP 与注入', sort_order: 0, lessons: lessons('c1', 'ch1', 'l1', ['HTTP 请求解剖', 'SQL 注入原理', 'XSS 与同源策略', '会话与认证']) }] },
  { id: 'c2', name: 'Linux 系统与安全', description: '走进命令行，掌握权限管理、系统配置与安全加固。', status: 'PUBLISHED', chapters: [{ id: 'ch2', course_id: 'c2', title: '权限与文件', sort_order: 0, lessons: lessons('c2', 'ch2', 'l2', ['文件权限模型']) }] },
  { id: 'c3', name: '网络协议分析', description: '追踪数据包的旅程，从流量中发现线索与异常。', status: 'PUBLISHED', chapters: [{ id: 'ch3', course_id: 'c3', title: '抓包入门', sort_order: 0, lessons: lessons('c3', 'ch3', 'l3', ['TCP 三次握手']) }] },
]
const labs: Lab[] = [
  { id: 'lab1', name: 'SQL 注入原理与实践', description: '在隔离靶机上复现联合查询注入，理解参数化查询为何能防御。', objective: '读取 flags 表', steps: '### 步骤\n1. 打开靶机页面\n2. 构造联合查询\n3. 提交 flag', category: 'WEB', difficulty: 'BEGINNER', target_image_id: 'img1', target_port: 80, duration_minutes: 45, cpu_limit: 1, memory_limit: 512, status: 'PUBLISHED', flag: 'flag{demo}' },
  { id: 'lab2', name: 'Linux 文件权限探索', description: '通过 SUID 与目录遍历理解最小权限原则。', objective: '读取受限文件', steps: '### 步骤\n1. 枚举 SUID 文件', category: 'SYSTEM', difficulty: 'INTERMEDIATE', target_image_id: 'img1', target_port: 22, duration_minutes: 30, cpu_limit: 1, memory_limit: 256, status: 'PUBLISHED' },
  { id: 'lab3', name: '流量分析与取证', description: '从 pcap 中还原一次明文登录过程。', objective: '找到口令', steps: '### 步骤\n1. 过滤 HTTP 流', category: 'NETWORK', difficulty: 'ADVANCED', target_image_id: 'img1', target_port: 8080, duration_minutes: 60, cpu_limit: 2, memory_limit: 1024, status: 'PUBLISHED' },
]
const session: LabSession = { id: 's1', user_id: 'u1', lab_template_id: 'lab1', lab_name: 'SQL 注入原理与实践', lab: labs[0], status: 'READY', target_ip: '172.20.0.3', started_at: new Date(Date.now() - 12 * 60000).toISOString(), expires_at: new Date(Date.now() + 33 * 60000).toISOString(), finished_at: null, error: null, instances: [{ id: 'i1', runtime_id: 'r1', instance_type: 'KALI', status: 'running', ip_address: '172.20.0.2' }, { id: 'i2', runtime_id: 'r2', instance_type: 'TARGET', status: 'running', ip_address: '172.20.0.3' }] }
const sessions: LabSession[] = [
  { ...session, student: user },
  { ...session, id: 's2', lab_name: 'Linux 文件权限探索', lab: labs[1], status: 'FINISHED', target_ip: null, started_at: new Date(Date.now() - 86400000).toISOString(), expires_at: new Date(Date.now() - 82800000).toISOString(), finished_at: new Date(Date.now() - 82800000).toISOString(), student: { ...user, id: 'u2', username: 'chen', real_name: '陈同学', student_number: '20260002' } },
]
const scores: Score[] = [
  { lab_id: 'lab1', lab_name: 'SQL 注入原理与实践', score: 100, completed: true, completed_at: new Date(Date.now() - 3600000).toISOString(), submissions_count: 2, attempted: true },
  { lab_id: 'lab2', lab_name: 'Linux 文件权限探索', score: 80, completed: true, completed_at: new Date(Date.now() - 86400000).toISOString(), submissions_count: 3, attempted: true },
  { lab_id: 'lab3', lab_name: '流量分析与取证', score: 0, completed: false, completed_at: null, submissions_count: 0, attempted: false },
]
const progress: Progress[] = [
  { id: 'p1', user_id: 'u1', lesson_id: 'l11', completed: true, completed_at: new Date().toISOString(), lesson_title: 'HTTP 请求解剖', chapter_title: 'HTTP 与注入', course_name: 'Web 安全基础' },
  { id: 'p2', user_id: 'u1', lesson_id: 'l12', completed: true, completed_at: new Date().toISOString(), lesson_title: 'SQL 注入原理', chapter_title: 'HTTP 与注入', course_name: 'Web 安全基础' },
  { id: 'p3', user_id: 'u1', lesson_id: 'l21', completed: true, completed_at: new Date().toISOString(), lesson_title: '文件权限模型', chapter_title: '权限与文件', course_name: 'Linux 系统与安全' },
]
const routes: [RegExp, unknown][] = [
  [/^auth\/me$/, () => ({ ...user, role: currentRole() })],
  [/^admin\/dashboard$/, { students: 42, published_courses: 3, published_labs: 3, running_sessions: 5, completed_today: 7 }],
  [/^admin\/lab-sessions$/, sessions],
  [/^admin\/students$/, [{ ...user, completed_labs: 2, average_score: 90, last_completed_at: new Date().toISOString() }]],
  [/^admin\/images$/, [{ id: 'img1', display_name: 'web-dvwa', repository: 'cyberlab/dvwa', tag: 'latest', image_id: 'sha256:000', repo_digest: null, size_bytes: 314572800, original_filename: 'dvwa.tar', status: 'READY', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), error_message: null }]],
  [/^courses$/, courses],
  [/^courses\/(.+)$/, (m: string[]) => courses.find(c => c.id === m[1])],
  [/^lessons\/(.+)$/, (m: string[]) => courses.flatMap(c => c.chapters.flatMap(ch => ch.lessons)).find(l => l.id === m[1])],
  [/^me\/progress$/, progress],
  [/^me\/sessions$/, sessions],
  [/^me\/scores$/, scores],
  [/^labs$/, labs],
  [/^labs\/(.+)$/, (m: string[]) => labs.find(l => l.id === m[1])],
  [/^lab-sessions\/(.+)$/, (m: string[]) => sessions.find(s => s.id === m[1])],
]
export function mockGet(url: string): unknown {
  const path = url.replace(/^\/+/, '').split('?')[0]
  for (const [pattern, value] of routes) {
    const match = pattern.exec(path)
    if (match) return typeof value === 'function' ? (value as (m: string[]) => unknown)(match) ?? null : value
  }
  return null
}

