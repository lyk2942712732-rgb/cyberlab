import fs from 'node:fs'
import { test, expect } from '@playwright/test'

// Dedicated QA terminal must be maximized and focused. Never run in a student session.
// Local bridge: CYBERLAB_VNC_QA=1, Vite on localhost:5174.
// Deployment: CYBERLAB_DESKTOP_FIXTURE points at {session_id,token} for an owned QA session.
const fixturePath = process.env.CYBERLAB_DESKTOP_FIXTURE
const bridge = process.env.CYBERLAB_VNC_QA === '1'
test.use({ ignoreHTTPSErrors: true, viewport: { width: 1500, height: 1040 } })
test('真实桌面首帧、重连和十次键盘到画面响应', async ({ page }, testInfo) => {
  test.skip(!bridge && !fixturePath, 'Requires an explicitly prepared disposable QA desktop')
  test.setTimeout(120000)
  let path = '/e2e/fixtures/vnc.html'
  if (!bridge) {
    const fixture = JSON.parse(fs.readFileSync(fixturePath!, 'utf8'))
    await page.addInitScript(token => sessionStorage.setItem('cyberlab-token', token), fixture.token)
    path = `/desktop/${fixture.session_id}`
  }
  const canvas = page.locator('canvas')
  const connections: number[] = []
  for (let attempt = 0; attempt < 3; attempt++) {
    const started = Date.now()
    await page.goto(path)
    await expect(canvas).toHaveAttribute('width', '1440')
    await expect(canvas).toHaveAttribute('height', '900')
    await page.waitForFunction(() => {
      const c = document.querySelector('canvas')
      const ctx = c?.getContext('2d')
      if (!ctx || !c?.width) return false
      // Real desktop pixels, beyond merely receiving ServerInit dimensions.
      const p = ctx.getImageData(0, 0, c.width, 60).data
      const colors = new Set<string>()
      for (let i = 0; i < p.length; i += 40) colors.add(`${p[i]},${p[i+1]},${p[i+2]}`)
      return colors.size > 10
    })
    connections.push(Date.now() - started)
  }
  await canvas.click({ position: { x: 400, y: 300 } })
  const responses: number[] = []
  for (let index = 0; index < 10; index++) {
    const red = index % 2 === 0
    await page.keyboard.type(`printf '\\033[${red ? 41 : 42}m\\033[2J\\033[H'`, { delay: 2 })
    const started = Date.now()
    await page.keyboard.press('Enter')
    await page.waitForFunction(wantRed => {
      const c = document.querySelector('canvas')!
      const [r, g, b] = c.getContext('2d')!.getImageData(500, 400, 1, 1).data
      return wantRed ? r > g * 1.5 && r > b * 1.5 : g > r * 1.5 && g > b * 1.5
    }, red, { polling: 'raf', timeout: 10000 })
    responses.push(Date.now() - started)
  }
  await page.keyboard.type("printf '\\033[0m\\033[2J\\033[H'", { delay: 2 })
  await page.keyboard.press('Enter')
  const report = { transport: bridge ? 'SSH/Docker exec QA bridge' : 'deployed HTTPS/WebSocket/Docker exec', connection_ms: connections, input_to_frame_ms: responses }
  const artifact = testInfo.outputPath('desktop-performance.json')
  fs.writeFileSync(artifact, JSON.stringify(report, null, 2))
  await testInfo.attach('desktop-performance.json', { path: artifact, contentType: 'application/json' })
  console.log(JSON.stringify(report))
  expect(Math.max(...connections)).toBeLessThan(10000)
  expect(Math.max(...responses)).toBeLessThan(2000)
})
