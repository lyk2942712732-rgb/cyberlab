import fs from 'node:fs'
import { test, expect } from '@playwright/test'

const fixturePath = process.env.CYBERLAB_DESKTOP_FIXTURE
test.use({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 1000 } })
test('正式管理员页面显示专用验收会话的最终输入', async ({ page }, testInfo) => {
  test.skip(!fixturePath, 'Requires an owned QA session with browser submission evidence')
  const fixture = JSON.parse(fs.readFileSync(fixturePath!, 'utf8'))
  await page.addInitScript(token => sessionStorage.setItem('cyberlab-token', token), fixture.admin_token)
  await page.goto('/admin/sessions')
  await page.locator('.el-switch').click()
  const row = page.getByRole('row').filter({ hasText: fixture.session_id })
  await row.getByRole('button', { name: '操作记录', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('LIVE_FINAL_ANSWER', { exact: false }).first()).toBeVisible()
  await expect(dialog).not.toContainText('LIVE_DRAFT_NOT_SAVED')
  await expect(dialog).not.toContainText('LIVE_PASSWORD_HIDDEN')
  await expect(dialog).toContainText('[隐藏]')
  await expect(dialog).toContainText('提交命令')
  await page.screenshot({ path: testInfo.outputPath('activity-live.png'), fullPage: true })
})
