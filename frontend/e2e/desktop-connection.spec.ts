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
    // Return native instances: noVNC checks properties on the immediate prototype.
    window.WebSocket = new Proxy(NativeSocket, {
      construct(target, args) {
        const socket = Reflect.construct(target, args)
        if (String(args[0]).endsWith('/desktop')) (window as any).__desktopSockets.push(socket)
        return socket
      },
    })
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
  if (fixture.terminal_ready) {
    // Optional: the fixture owner opened a maximized disposable QA terminal.
    // Two visible updates are enough to check input/output without a long soak.
    await page.locator('canvas').click({ position: { x: 400, y: 300 } })
    const latencies: number[] = []
    for (const key of ['m', 'w']) {
      await page.evaluate(() => {
        const ctx = document.querySelector('canvas')!.getContext('2d')!
        ;(window as any).__beforeTyping = ctx.getImageData(0, 40, 1200, 200).data
      })
      const started = Date.now()
      await page.keyboard.press(key)
      await page.waitForFunction(() => {
        const pixels = document.querySelector('canvas')!.getContext('2d')!.getImageData(0, 40, 1200, 200).data
        const before = (window as any).__beforeTyping
        let changed = 0
        for (let i = 0; i < pixels.length; i += 4) {
          if (pixels[i] !== before[i] || pixels[i + 1] !== before[i + 1] || pixels[i + 2] !== before[i + 2]) changed++
        }
        return changed > 30
      }, undefined, { polling: 'raf', timeout: 5000 })
      latencies.push(Date.now() - started)
    }
    await page.keyboard.press('Control+u')
    await page.keyboard.type('exit')
    await page.keyboard.press('Enter')
    console.log(JSON.stringify({ typing_to_frame_ms: latencies }))
    expect(Math.max(...latencies)).toBeLessThan(2000)
  }
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
