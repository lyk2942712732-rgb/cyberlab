import { test, expect, type Page } from '@playwright/test'

// Deterministic UI checks. Fixtures are intercepted here, never in the app.
const courses = [
  { id: 'web', name: 'Web 安全基础', description: '从 HTTP 协议到常见 Web 漏洞，理解攻防背后的原理。', chapters: [{ id: 'ch1', lessons: [{ id: 'l1' }, { id: 'l2' }] }] },
  { id: 'linux', name: 'Linux 系统与安全', description: '走进命令行，掌握权限管理、系统配置与安全加固。', chapters: [{ id: 'ch2', lessons: [{ id: 'l3' }] }] },
  { id: 'network', name: '网络协议分析', description: '追踪数据包的旅程，从流量中发现线索与异常。', chapters: [{ id: 'ch3', lessons: [{ id: 'l4' }] }] },
]
const progress = [{ lesson_id: 'l1', completed: true }, { lesson_id: 'l2', completed: false }, { lesson_id: 'l3', completed: true }]
const sessions = [
  { id: 's1', lab_name: 'SQL 注入原理与实践', status: 'READY', started_at: '2026-09-23T01:00:00Z' },
  { id: 's2', lab_name: 'Linux 文件权限探索', status: 'FINISHED', started_at: '2026-09-22T02:00:00Z' },
]

async function mockApi(page: Page, admin = false) {
  await page.addInitScript(() => sessionStorage.setItem('cyberlab-token', 'ui-test-token'))
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    const values: Record<string, unknown> = {
      '/api/auth/me': { id: 'student', username: 'student01', real_name: '林同学', role: admin ? 'ADMIN' : 'STUDENT', student_number: '20260001' },
      '/api/courses': courses,
      '/api/me/progress': progress,
      '/api/me/scores': [{ lab_id: 'lab1', score: 100, attempted: true, completed: true }],
      '/api/me/sessions': sessions,
      '/api/admin/lab-sessions': sessions,
      '/api/admin/dashboard': { students: 48, published_courses: 3, published_labs: 12, running_sessions: 6, completed_today: 18 },
      '/api/labs': [{ id: 'lab1', name: 'SQL 注入原理与实践', description: '理解 SQL 注入的形成原因，在独立环境中完成验证。', category: 'WEB SECURITY', difficulty: 'BEGINNER', duration_minutes: 60 }],
    }
    return route.fulfill({ json: { data: values[path] ?? [] } })
  })
}

test.use({ viewport: { width: 1440, height: 1000 } })

test('工作台统计已完成课时，并进入正确的继续学习课程', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await mockApi(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '你好，林同学.' })).toBeVisible()
  await expect(page.locator('.stat-card').filter({ hasText: '已学课时' }).locator('strong')).toHaveText('2')
  await expect(page.locator('.learning-note .note-link')).toHaveAttribute('href', '/courses/web')
  await expect(page.locator('.learning-note .progress-label')).toContainText('50%')
  await page.screenshot({ path: 'test-results/desktop-dashboard.png', fullPage: true, animations: 'disabled' })
  for (const width of [1024, 1280, 1920]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
  }
  await page.getByRole('button', { name: '收起侧栏', exact: true }).click()
  await expect(page.locator('.app-shell')).toHaveClass(/sidebar-collapsed/)
  await page.reload()
  await expect(page.getByRole('button', { name: '展开侧栏', exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('课程支持搜索、完成状态筛选、清除条件和失败重试', async ({ page }) => {
  await mockApi(page)
  await page.goto('/courses')
  await expect(page.locator('.course-card')).toHaveCount(3)
  await page.screenshot({ path: 'test-results/desktop-courses.png', fullPage: true, animations: 'disabled' })
  await page.getByRole('textbox', { name: '搜索课程' }).fill(' HTTP ')
  await expect(page.locator('.course-card')).toHaveCount(1)
  await expect(page.locator('.course-card')).toContainText('Web 安全基础')
  await page.getByRole('textbox', { name: '搜索课程' }).fill('不存在的课程')
  await expect(page.getByText('没有找到符合条件的课程')).toBeVisible()
  await page.getByRole('button', { name: '清除筛选' }).click()
  await page.getByRole('combobox', { name: '学习状态' }).press('Enter')
  await page.getByRole('option', { name: '已完成', exact: true }).click()
  await expect(page.locator('.course-card')).toHaveCount(1)
  await expect(page.locator('.course-card')).toContainText('Linux 系统与安全')
  await page.route('**/api/courses', route => route.fulfill({ status: 503, json: { error: { message: '测试加载失败' } } }))
  await page.reload()
  await expect(page.getByRole('alert').filter({ hasText: '课程暂时无法加载' })).toBeVisible()
  await page.unroute('**/api/courses')
  await page.getByRole('button', { name: '重新加载' }).click()
  await expect(page.locator('.course-card')).toHaveCount(3)
})

test('管理端指标布局、实验卡片、登录注册表单可用', async ({ page }) => {
  await mockApi(page, true)
  await page.goto('/')
  await expect(page.locator('.admin-stats .stat-card')).toHaveCount(5)
  await page.screenshot({ path: 'test-results/desktop-admin.png', fullPage: true, animations: 'disabled' })
  await page.goto('/labs')
  await expect(page.getByRole('heading', { name: 'SQL 注入原理与实践' })).toBeVisible()
  await page.screenshot({ path: 'test-results/desktop-labs.png', fullPage: true, animations: 'disabled' })
  await page.goto('/login')
  await page.screenshot({ path: 'test-results/desktop-login.png', fullPage: true, animations: 'disabled' })
  await page.getByRole('button', { name: '注册学生账号', exact: true }).click()
  await expect(page.getByText('学号', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '返回登录' }).click()
  await expect(page.getByRole('button', { name: '登录工作台 →' })).toBeVisible()
})
