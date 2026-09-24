import fs from 'node:fs'
import { test, expect } from '@playwright/test'

// Run against a dedicated READY SQL lab on an explicitly selected deployment.
// The fixture file contains { session_id, token }; never commit that file.
const fixturePath = process.env.CYBERLAB_DESKTOP_FIXTURE
test.use({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 1000 } })
test('真实桌面在窗口缩放、侧栏切换、全屏及重连后保持固定分辨率', async ({ page }) => {
  test.skip(!fixturePath, 'Requires a dedicated live desktop fixture')
  test.setTimeout(120000)
  const fixture = JSON.parse(fs.readFileSync(fixturePath!, 'utf8'))
  await page.addInitScript(token => sessionStorage.setItem('cyberlab-token', token), fixture.token)
  await page.goto(`/sessions/${fixture.session_id}`)
  const desktop = page.frameLocator('iframe[title="Kali 在线实验桌面"]')
  const canvas = desktop.locator('canvas')
  async function checkDesktop() {
    await expect(desktop.locator('.novnc-toolbar')).toBeVisible()
    // Wait past noVNC's resize debounce to detect a remote resize, not just
    // the original ServerInit dimensions before SetDesktopSize is processed.
    await page.waitForTimeout(1800)
    await expect(canvas).toHaveAttribute('width', '1440')
    await expect(canvas).toHaveAttribute('height', '900')
    const size = await canvas.boundingBox()
    expect(size).not.toBeNull()
    expect(size!.width).toBeGreaterThan(0)
  }
  await checkDesktop()
  const initial = await canvas.boundingBox()
  await page.setViewportSize({ width: 1050, height: 768 })
  await checkDesktop()
  const smaller = await canvas.boundingBox()
  expect(smaller!.width).toBeLessThan(initial!.width)
  await page.getByRole('button', { name: '收起侧栏', exact: true }).click()
  await checkDesktop()
  await page.getByRole('button', { name: '全屏', exact: true }).click()
  await checkDesktop()
  await page.getByRole('button', { name: '退出全屏', exact: true }).click()
  await page.setViewportSize({ width: 1920, height: 1080 })
  await checkDesktop()
  await page.reload()
  await checkDesktop()
})
