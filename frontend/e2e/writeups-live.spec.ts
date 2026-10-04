import fs from 'node:fs'
import { test, expect } from '@playwright/test'

const fixturePath = process.env.CYBERLAB_WRITEUP_FIXTURE
test.use({ ignoreHTTPSErrors: true, trace: 'off', viewport: { width: 1440, height: 1000 } })

test('正式站点全部实验可读题解，管理员可预览已有内容', async ({ page }, testInfo) => {
  test.skip(!fixturePath, 'Requires deployment verification tokens; never records credentials in traces')
  const fixture = JSON.parse(fs.readFileSync(fixturePath!, 'utf8'))
  await page.addInitScript(token => sessionStorage.setItem('cyberlab-token', token), fixture.student_token)
  await page.goto('/labs')
  const labs = await page.evaluate(async () => {
    const response = await fetch('/api/labs', { headers: { Authorization: `Bearer ${sessionStorage.getItem('cyberlab-token')}` } })
    return (await response.json()).data as { id: string; name: string }[]
  })
  expect(labs.length).toBeGreaterThanOrEqual(13)
  for (const lab of labs) {
    await page.goto(`/labs/${lab.id}`)
    await page.getByRole('button', { name: '查看参考解答' }).click()
    const drawer = page.getByRole('dialog', { name: '参考解答与解题思路' })
    await expect(drawer.getByRole('heading', { name: '本实验评估要点', exact: true })).toBeVisible()
    await expect(drawer.getByRole('heading', { name: '学习验收与评估约定', exact: true })).toBeVisible()
  }
  await page.screenshot({ path: testInfo.outputPath('writeup-student.png'), fullPage: true })
  if (fixture.session_id) {
    await page.goto(`/sessions/${fixture.session_id}`)
    await page.getByRole('button', { name: '查看参考解答' }).click()
    await expect(page.getByRole('dialog').getByRole('heading', { name: '本实验评估要点', exact: true })).toBeVisible()
  }
  await page.addInitScript(token => sessionStorage.setItem('cyberlab-token', token), fixture.admin_token)
  await page.goto('/admin/labs')
  await page.getByRole('row').filter({ hasText: 'SQL 注入基础实验' }).getByRole('button', { name: '编辑', exact: true }).click()
  await expect(page.getByRole('textbox', { name: '参考解答 / 解题思路（Markdown）', exact: true })).toHaveValue(/SQL 注入基础实验/)
  await page.getByRole('button', { name: '预览参考解答' }).click()
  await expect(page.getByRole('heading', { name: 'SQL 注入基础实验 · 参考解答', exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('writeup-admin.png'), fullPage: true })
})
