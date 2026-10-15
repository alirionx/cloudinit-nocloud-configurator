import { expect, test } from '@playwright/test'
import { createConfiguration, uniqueName } from './helpers'

test('NFR-012: no assets are loaded from other hosts (app and Swagger UI)', async ({ page, request, baseURL }) => {
  const config = await createConfiguration(request, { name: uniqueName('Privacy') })
  const external: string[] = []
  page.on('request', (req) => {
    const url = new URL(req.url())
    if (!['http:', 'https:'].includes(url.protocol)) return
    if (url.origin !== new URL(baseURL!).origin) external.push(req.url())
  })
  for (const path of ['/', `/configurations/${config.id}`, '/configurations/new', '/docs']) {
    await page.goto(path)
    await page.waitForLoadState('networkidle')
  }
  await expect(page.locator('.swagger-ui')).toBeVisible()
  await expect(page.getByText('/api/configurations', { exact: true }).first()).toBeVisible()
  expect(external).toEqual([])
})
