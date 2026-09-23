import { test, expect } from '@playwright/test'

test('资源面板按需采集、失败提示、后台暂停与窄屏布局', async ({ page }) => {
  let calls = 0, fail = false
  await page.addInitScript(() => sessionStorage.setItem('cyberlab-token', 'test-token'))
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/auth/me')) return route.fulfill({ json: { data: { id: 'student', username: 'student01', real_name: '测试学生', role: 'STUDENT' } } })
    if (path.endsWith('/metrics')) {
      calls++
      if (fail) return route.fulfill({ status: 503, json: { error: { message: '资源监控暂时不可用' } } })
      return route.fulfill({ json: { data: { sampled_at: new Date().toISOString(), instances: ['KALI', 'TARGET'].map((instance_type, index) => ({ instance_type, available: true, status: 'running', health: index ? 'not_configured' : 'healthy', cpu_percent: calls === 1 ? null : 80, cpu_limit: 2, cpu_limit_percent: calls === 1 ? null : 40, memory_bytes: 384 * 1024 ** 2, memory_limit_bytes: 1536 * 1024 ** 2, memory_percent: 25, pids: 93, pids_limit: 512, uptime_seconds: 123, network_rx_bytes: 1024, network_tx_bytes: 2048, network_rx_bytes_per_second: 30, network_tx_bytes_per_second: 50 })) } } })
    }
    return route.fulfill({ json: { data: { id: 'demo', status: 'READY', lab_name: '资源监控验证实验', expires_at: new Date(Date.now() + 3600000).toISOString(), instances: [{ runtime_id: 'kali' }, { runtime_id: 'target' }], target_ip: '172.20.0.2', lab: { target_port: 8000, objective: '监控资源与健康状态', steps: '观察 CPU、内存与健康检查。' } } } })
  })
  await page.route('**/desktop/demo', route => route.fulfill({ contentType: 'text/html', body: '<body style="background:#213b35;color:white">桌面占位 · 监控组件独立测试</body>' }))
  await page.goto('/sessions/demo')
  const toggle = page.getByRole('button', { name: /资源与健康状态/ })
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  expect(calls).toBe(0)
  await toggle.click()
  await expect(page.getByText('未配置健康检查', { exact: true })).toBeVisible()
  await expect(page.locator('.resource-card').first()).toContainText('采样中')
  await expect.poll(() => calls, { timeout: 8000 }).toBe(2)
  await expect(page.locator('.resource-card').first()).toContainText('80.0%')
  await page.screenshot({ path: 'test-results/resources-desktop.png', fullPage: true })
  await toggle.click()
  const collapsedCalls = calls
  await page.waitForTimeout(5500)
  expect(calls).toBe(collapsedCalls)
  await toggle.click()
  await expect.poll(() => calls).toBe(collapsedCalls + 1)
  await page.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, value: true }); document.dispatchEvent(new Event('visibilitychange')) })
  const hiddenCalls = calls
  await page.waitForTimeout(5500)
  expect(calls).toBe(hiddenCalls)
  await page.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, value: false }); document.dispatchEvent(new Event('visibilitychange')) })
  await expect.poll(() => calls).toBe(hiddenCalls + 1)
  fail = true
  await expect(page.getByRole('status').filter({ hasText: '暂时无法更新' })).toBeVisible({ timeout: 8000 })
  await expect(page.locator('.el-message')).toHaveCount(0)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: '收起侧栏', exact: true }).click()
  await page.screenshot({ path: 'test-results/resources-mobile.png', fullPage: true })
  const panel = page.getByRole('region', { name: '实验资源监控' })
  const bounds = await panel.boundingBox()
  expect(bounds!.width).toBeLessThanOrEqual(390)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
})
