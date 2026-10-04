import { test, expect } from '@playwright/test'

const lab = { id: 'reference-lab', name: '题解验收实验', description: '实验介绍', objective: '理解原理', steps: '先独立尝试', category: 'Web 安全', difficulty: 'BEGINNER', target_image_id: 'image', target_port: 8000, duration_minutes: 90, cpu_limit: 1, memory_limit: 256, status: 'PUBLISHED' }
const content = '# 参考步骤\n\n先建立正常基线。\n\n```html\n<script>window.writeupExecuted=true</script>\n```\n\n<img src="x" onerror="window.writeupExecuted=true">\n\n## 本实验评估要点\n\n只提交请求不代表执行成功。'

for (const path of ['/labs/reference-lab', '/sessions/reference-session']) {
  test(`按需查看参考解答，安全显示代码：${path}`, async ({ page }) => {
    let calls = 0
    await page.addInitScript(() => sessionStorage.setItem('cyberlab-token', 'writeup-test'))
    await page.route(/^https?:\/\/[^/]+\/api\//, route => {
      const url = new URL(route.request().url()).pathname
      let data: unknown = lab
      if (url.endsWith('/auth/me')) data = { id: 'student', username: 'student01', role: 'STUDENT' }
      if (url.endsWith('/reference-session')) data = { id: 'reference-session', lab_template_id: lab.id, lab_name: lab.name, lab, status: 'DESTROYED', instances: [], expires_at: new Date().toISOString() }
      if (url.endsWith('/writeup')) { calls++; data = { schema_version: 1, lab_id: lab.id, format: 'markdown', content } }
      return route.fulfill({ json: { data } })
    })
    await page.goto(path)
    await expect(page.getByRole('button', { name: '查看参考解答' })).toBeVisible()
    expect(calls).toBe(0)
    await page.getByRole('button', { name: '查看参考解答' }).click()
    const drawer = page.getByRole('dialog', { name: '参考解答与解题思路' })
    await expect(drawer.getByRole('heading', { name: '参考步骤' })).toBeVisible()
    await expect(drawer.locator('pre')).toContainText('<script>')
    expect(await page.evaluate(() => (window as any).writeupExecuted)).toBeUndefined()
    await page.setViewportSize({ width: 390, height: 844 })
    await expect.poll(async () => (await drawer.boundingBox())!.width).toBeLessThanOrEqual(390)
    expect(calls).toBe(1)
  })
}

test('题解加载失败可重试，空题解有说明', async ({ page }) => {
  let attempts = 0
  await page.addInitScript(() => sessionStorage.setItem('cyberlab-token', 'writeup-test'))
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const url = new URL(route.request().url()).pathname
    if (url.endsWith('/auth/me')) return route.fulfill({ json: { data: { id: 'student', username: 'student01', role: 'STUDENT' } } })
    if (url.endsWith('/writeup')) {
      if (++attempts === 1) return route.fulfill({ status: 503, json: { error: { message: 'Unavailable' } } })
      return route.fulfill({ json: { data: { content: '' } } })
    }
    return route.fulfill({ json: { data: lab } })
  })
  await page.goto('/labs/reference-lab')
  await page.getByRole('button', { name: '查看参考解答' }).click()
  await expect(page.getByRole('alert')).toContainText('参考解答加载失败')
  await page.getByRole('button', { name: '重新加载' }).click()
  await expect(page.getByText('本实验暂未配置参考解答')).toBeVisible()
})

test('管理员编辑并预览参考解答', async ({ page }) => {
  let saved: any
  await page.addInitScript(() => sessionStorage.setItem('cyberlab-token', 'writeup-admin-test'))
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const url = new URL(route.request().url()).pathname
    let data: unknown = []
    if (url.endsWith('/auth/me')) data = { id: 'admin', username: 'admin', role: 'ADMIN' }
    if (url.endsWith('/labs')) data = [lab]
    if (url.endsWith('/images')) data = [{ id: 'image', display_name: '教学镜像', status: 'READY' }]
    if (url.endsWith('/labs/reference-lab')) data = { ...lab, flag: 'test-only', writeup: content }
    if (route.request().method() === 'PUT') saved = route.request().postDataJSON()
    return route.fulfill({ json: { data } })
  })
  await page.goto('/admin/labs')
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const input = page.getByRole('textbox', { name: '参考解答 / 解题思路（Markdown）', exact: true })
  await expect(input).toHaveValue(content)
  await input.fill('# 教师修订\n\n补充结果证据。')
  await page.getByRole('button', { name: '预览参考解答' }).click()
  await expect(page.getByRole('heading', { name: '教师修订' })).toBeVisible()
  await page.getByRole('button', { name: '保存实验' }).click()
  await expect.poll(() => saved?.writeup).toBe('# 教师修订\n\n补充结果证据。')
})
