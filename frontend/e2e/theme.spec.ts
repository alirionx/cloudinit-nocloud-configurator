import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { createConfiguration, uniqueName } from './helpers'

const LIGHT_BG = 'rgb(255, 255, 255)'
const DARK_BG = 'rgb(18, 18, 18)'

test('FR-016: light theme is active on the first visit', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.locator('.v-application')).toHaveClass(/v-theme--light/)
  await expect(page.getByRole('button', { name: 'Switch to dark theme' })).toBeVisible()
})

test('FR-016: dark theme is remembered and applied before the first render', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Switch to dark theme' }).click()
  await expect(page.locator('.v-application')).toHaveClass(/v-theme--dark/)

  await page.reload()
  await expect(page.locator('.v-application')).toHaveClass(/v-theme--dark/)

  // Without the app bundle nothing is rendered by Vue: the page must already be dark,
  // which proves there is no light flash before the app starts.
  await page.route('**/assets/*.js', (route) => route.abort())
  await page.goto('/')
  const background = await page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor)
  expect(background).toBe(DARK_BG)
})

test('FR-016: switching back to light is remembered too', async ({ page }) => {
  await page.goto('/')
  await page.evaluate(() => localStorage.setItem('cnc-theme', 'dark'))
  await page.reload()
  await page.getByRole('button', { name: 'Switch to light theme' }).click()
  await page.route('**/assets/*.js', (route) => route.abort())
  await page.reload()
  const background = await page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor)
  expect(background).toBe(LIGHT_BG)
})

for (const theme of ['light', 'dark'] as const) {
  test(`FR-016, NFR-013: contrast meets WCAG 2.1 AA in the ${theme} theme`, async ({ page, request }) => {
    const config = await createConfiguration(request, {
      name: uniqueName('Contrast'),
      basics: { hostname: 'web-01', fqdn: 'db.example.com', timezone: 'UTC' },
    })
    await page.addInitScript((name) => localStorage.setItem('cnc-theme', name), theme)

    for (const url of ['/', `/configurations/${config.id}`]) {
      await page.goto(url)
      await page.waitForLoadState('networkidle')
      // Produce an error message too, so its colors are checked as well.
      if (url !== '/') {
        await page.getByLabel('Hostname (local-hostname)').fill('bad_host')
        await page.getByLabel('Hostname (local-hostname)').blur()
        await expect(page.getByText('must be a host name').first()).toBeVisible()
      }
      await page.waitForTimeout(500) // let transitions finish
      const results = await new AxeBuilder({ page }).withTags(['wcag2aa']).withRules(['color-contrast']).analyze()
      const violations = results.violations.flatMap((v) => v.nodes.map((n) => `${n.target}: ${n.failureSummary}`))
      expect(violations, violations.join('\n')).toEqual([])
    }
  })
}
