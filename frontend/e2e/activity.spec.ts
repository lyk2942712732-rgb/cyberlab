import { test, expect } from '@playwright/test'

test('管理员查看操作日志、分页、切换代次和中断状态', async ({ page }) => {
  const requests: string[] = []
  await page.addInitScript(() => sessionStorage.setItem('cyberlab-token', 'activity-ui-test'))
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const url = new URL(route.request().url())
    let data: unknown = []
    if (url.pathname.endsWith('/auth/me')) data = { id: 'admin', role: 'ADMIN', username: 'admin', real_name: '验收管理员' }
    if (url.pathname.endsWith('/admin/lab-sessions')) data = [{ id: 'qa', status: 'READY', lab_name: '操作记录验收', student: {real_name: '测试学生'}, instances: [], started_at: new Date().toISOString(), expires_at: new Date(Date.now()+3600000).toISOString() }]
    if (url.pathname.endsWith('/activity')) {
      requests.push(url.search)
      const after = Number(url.searchParams.get('after') || 0), generation = Number(url.searchParams.get('generation') || 2)
      data = {state: {status: generation === 1 ? 'interrupted' : 'running', generation, complete: false, providers: generation === 2 ? {browser: {status: 'partial'}} : {}, error: generation === 1 ? '操作采集心跳中断' : undefined},
        generations: [1,2], next: after === 0 ? 100 : null,
        events: [{seq: after+1,timestamp: Date.now()/1000,source:'shell',type:'terminal.submit',data:{cwd:'/home/student',command: after ? 'printf page_two' : 'echo <script>window.pwned=true</script>'}}]}
    }
    return route.fulfill({json:{data}})
  })
  await page.goto('/admin/sessions')
  await page.getByRole('button',{name:'操作记录',exact:true}).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('提交命令',{exact:true})).toBeVisible()
  await expect(dialog.getByRole('alert')).toHaveText('部分操作未能完整记录，请结合实验结果核查。')
  await expect(dialog.locator('pre')).toContainText('<script>window.pwned=true</script>')
  expect(await page.evaluate(() => (window as unknown as Record<string,unknown>).pwned)).toBeUndefined()
  await dialog.getByRole('button',{name:'下一页'}).click()
  await expect(dialog.locator('pre')).toContainText('page_two')
  await expect(dialog.getByRole('button',{name:'下一页'})).toBeDisabled()
  await dialog.getByRole('button',{name:'上一页'}).click()
  await expect(dialog.locator('pre')).toContainText('<script>')
  await dialog.locator('.el-select').click()
  await page.getByRole('option',{name:'实验代次 1'}).click()
  await expect(dialog.getByRole('alert')).toHaveText('操作采集心跳中断')
  expect(requests.some(query => query.includes('after=100'))).toBeTruthy()
  expect(requests.at(-1)).toContain('generation=1')
  await page.screenshot({path:'test-results/activity-log.png',fullPage:true})
})
