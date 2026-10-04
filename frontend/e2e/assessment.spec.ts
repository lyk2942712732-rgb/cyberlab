import { test, expect } from '@playwright/test'

const completed = {
  status: 'COMPLETED', enabled: true, model: 'deepseek-flash', completed_at: new Date().toISOString(),
  evidence: { flag_correct: false, events_used: 1, events_read: 1, capture_complete: true, truncated: false,
    events: [{ id: 'g1:e1', type: 'web.change', timestamp: Date.now() / 1000, data: { value: '<script>window.pwned=true</script>' } }], submissions: [] },
  report: { summary: '你尝试修改输入，实际结果需要进一步验证。', approach: [{ title: '调整输入', kind: 'inferred', text: '可能在调整查询边界。', evidence_ids: ['g1:e1'] }],
    criteria: ['baseline', 'method', 'verification', 'understanding'].map(key => ({ key, verdict: 'insufficient_evidence', text: '缺少对应结果证据。', evidence_ids: [] })),
    strengths: [], improvements: [], next_steps: ['对照实际响应验证结果。'], limitations: ['没有网页响应正文。'] }
}

test('结束后自动显示复盘，依据可展开，历史入口可访问', async ({ page }) => {
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
  await expect(page.getByText('可能的思路', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '查看依据' }).click()
  await expect(page.getByRole('dialog')).toContainText('<script>window.pwned=true</script>')
  expect(await page.evaluate(() => (window as any).pwned)).toBeUndefined()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: '收起侧栏', exact: true }).click()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
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
