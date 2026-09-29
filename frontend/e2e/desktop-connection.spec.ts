import fs from 'node:fs'
import { test, expect } from '@playwright/test'

// Use only an explicitly prepared disposable READY session; no mocked transport.
const fixturePath = process.env.CYBERLAB_DESKTOP_FIXTURE
test.use({ ignoreHTTPSErrors: true, viewport: { width: 1500, height: 1040 }, trace: 'off' })

test('真实桌面协商 binary、显示画面、重连，并拒绝票据重放', async ({ page }, testInfo) => {
  test.skip(!fixturePath, 'Requires an owned disposable desktop fixture {session_id,token}')
  test.setTimeout(120000)
  const fixture = JSON.parse(fs.readFileSync(fixturePath!, 'utf8'))
  await page.addInitScript(token => {
    sessionStorage.setItem('cyberlab-token', token)
    const NativeSocket = window.WebSocket
    ;(window as any).__desktopSockets = []
    window.WebSocket = class extends NativeSocket {
      constructor(url: string | URL, protocols?: string | string[]) {
        super(url, protocols)
        if (String(url).endsWith('/desktop')) (window as any).__desktopSockets.push(this)
      }
    }
  }, fixture.token)
  let usedTicket = ''
  let issued = 0
  page.on('response', async response => {
    if (response.url().endsWith('/desktop-ticket') && response.ok()) {
      usedTicket = (await response.json()).data.ticket
      issued++
    }
  })
  await page.goto(`/desktop/${fixture.session_id}`)
  await expect(page.locator('.novnc-toolbar')).toBeVisible({ timeout: 25000 })
  expect(await page.evaluate(() => (window as any).__desktopSockets.at(-1).protocol)).toBe('binary')
  await page.waitForFunction(() => {
    const canvas = document.querySelector('canvas')
    const ctx = canvas?.getContext('2d')
    if (!ctx || canvas?.width !== 1440 || canvas.height !== 900) return false
    const pixels = ctx.getImageData(0, 0, canvas.width, 60).data
    const colors = new Set<string>()
    for (let i = 0; i < pixels.length; i += 40) colors.add(`${pixels[i]},${pixels[i + 1]},${pixels[i + 2]}`)
    return colors.size > 10
  })
  await page.evaluate(() => (window as any).__desktopSockets.at(-1).close())
  await expect(page.getByText('桌面连接已断开，可尝试重新连接。')).toBeVisible()
  await page.getByRole('button', { name: '重新连接' }).click()
  await expect(page.locator('.novnc-toolbar')).toBeVisible({ timeout: 25000 })
  expect(issued).toBe(2)
  expect(await page.evaluate(() => (window as any).__desktopSockets.at(-1).protocol)).toBe('binary')

  // Never log tickets or save traces containing the short-lived credentials.
  for (const ticket of [usedTicket, 'invalid-ticket']) {
    const opened = await page.evaluate(({ id, ticket }) => new Promise<boolean>(resolve => {
      const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/lab-sessions/${id}/desktop`, ['binary', ticket])
      socket.onopen = () => { socket.close(); resolve(true) }
      socket.onerror = () => resolve(false)
    }), { id: fixture.session_id, ticket })
    expect(opened).toBe(false)
  }
  await page.goto(`/sessions/${fixture.session_id}`)
  await expect(page.frameLocator('iframe[title="Kali 在线实验桌面"]').locator('.novnc-toolbar')).toBeVisible({ timeout: 25000 })
  await page.screenshot({ path: testInfo.outputPath('desktop-connected.png'), fullPage: true })
})
