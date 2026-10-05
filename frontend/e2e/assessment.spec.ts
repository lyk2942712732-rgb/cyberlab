import { test, expect } from '@playwright/test'

const completed = {
  status: 'COMPLETED', enabled: true, model: 'deepseek-flash', completed_at: new Date().toISOString(),
  evidence: { flag_correct: false, events_used: 1, events_read: 1, capture_complete: true, truncated: false,
    events: [{ id: 'g1:e1', type: 'web.change', timestamp: Date.now() / 1000, data: { value: '<script>window.pwned=true</script>' } }], submissions: [] },
  report: { schema_version: 2, summary: '你调整输入后完成了实验目标。',
    path: ['打开实验登录页', '首次尝试', '调整引号', '提交判题'].map(title => ({ title, text: title + '的具体操作说明。', evidence_ids: ['g1:e1'] })),
    reasoning: { text: '从两次输入的差异看，你可能在尝试找到字符串的闭合位置，再通过页面反馈核对修改效果。', evidence_ids: ['g1:e1'] },
    criteria: ['method', 'verification', 'strategy'].map(key => ({ key, verdict: 'achieved', text: '这项表现有操作依据。', evidence_ids: ['g1:e1'] })),
    suggestions: [{ text: '对照两次查询中引号的位置，说明条件发生了什么变化。', evidence_ids: [] }], limitations: [] }

}

test('结束后自动显示复盘，依据可展开，历史入口可访问', async ({ page }, testInfo) => {
  let reads = 0
  await page.addInitScript(() => sessionStorage.setItem('cyberlab-token', 'assessment-ui-test'))
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    let data: unknown = []
    if (path.endsWith('/auth/me')) data = { id: 'student', username: 'student01', role: 'STUDENT' }
    if (path.endsWith('/lab-sessions/qa')) data = { id: 'qa', lab_template_id: 'lab', lab_name: '复盘验收', status: 'DESTROYED', instances: [], lab: { objective: '理解原理', steps: '操作步骤', target_port: 8000 } }
    if (path.endsWith('/assessment')) data = ++reads === 1 ? { status: 'RUNNING', enabled: true } : completed
    if (path.endsWith('/me/assessments')) data = [{ session_id: 'qa', lab_name: '复盘验收', status: 'COMPLETED', started_at: new Date().toISOString() }]
    return route.fulfill({ json: { data } })
  })
  await page.goto('/sessions/qa')
  await expect(page.getByRole('status')).toContainText('正在分析')
  await expect(page.getByText(completed.report.summary)).toBeVisible({ timeout: 10000 })
  await expect(page.getByRole('heading', { name: '可能思路', exact: true })).toBeVisible()
  await expect(page.getByText(completed.report.reasoning.text)).toBeVisible()
  const stops = page.locator('.path-stop')
  await expect(stops).toHaveCount(4)
  await expect(page.locator('.path-links > path')).toHaveCount(3)
  const boxes = await stops.evaluateAll(nodes => nodes.map(node => ({ x: node.getBoundingClientRect().x, y: node.getBoundingClientRect().y })))
  expect(boxes[0]!.x).toBeLessThan(boxes[1]!.x)
  expect(boxes[2]!.x).toBeGreaterThan(boxes[3]!.x)
  expect(boxes[2]!.y).toBeGreaterThan(boxes[1]!.y)
  await stops.first().hover()
  await expect(stops.first().getByRole('tooltip')).toContainText('打开实验登录页的具体操作说明。')
  await page.locator('.journey-toggle').click()
  await expect(stops.first()).not.toBeVisible()
  await page.locator('.journey-toggle').click()
  await expect(stops.first()).toBeVisible()
  await page.locator('.assessment-panel').screenshot({ path: testInfo.outputPath('desktop.png') })
  await page.getByRole('button', { name: '打开实验登录页：查看依据', exact: true }).click()
  await expect(page.getByRole('dialog')).toContainText('<script>window.pwned=true</script>')
  expect(await page.evaluate(() => (window as any).pwned)).toBeUndefined()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: '收起侧栏', exact: true }).click()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.locator('.assessment-panel').screenshot({ path: testInfo.outputPath('mobile.png') })
  await page.goto('/scores')
  await page.getByRole('link', { name: '查看实验复盘' }).click()
  await expect(page).toHaveURL(/sessions\/qa/)
})

test('历史实验手动生成以及失败重试', async ({ page }) => {
  let state = 'NOT_REQUESTED', posts = 0
  await page.addInitScript(() => sessionStorage.setItem('cyberlab-token', 'assessment-ui-test'))
  await page.route(/^https?:\/\/[^/]+\/api\//, route => {
    const path = new URL(route.request().url()).pathname
    let data: unknown = []
    if (path.endsWith('/auth/me')) data = { id: 'student', username: 'student01', role: 'STUDENT' }
    if (path.endsWith('/lab-sessions/qa')) data = { id: 'qa', lab_name: '复盘验收', status: 'DESTROYED', instances: [], lab: {} }
    if (path.endsWith('/assessment')) {
      if (route.request().method() === 'POST') state = ++posts === 1 ? 'FAILED' : 'COMPLETED'
      data = state === 'COMPLETED' ? completed : { status: state, enabled: true, error: state === 'FAILED' ? '模型服务暂时不可用' : null }
    }
    return route.fulfill({ json: { data } })
  })
  await page.goto('/sessions/qa')
  await page.getByRole('button', { name: '生成实验复盘' }).click()
  await expect(page.getByRole('alert')).toContainText('模型服务暂时不可用')
  await page.getByRole('button', { name: '重试生成' }).click()
  await expect(page.getByText(completed.report.summary)).toBeVisible()
  expect(posts).toBe(2)
})
