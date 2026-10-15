import { expect, test } from '@playwright/test'
import { createConfiguration, uniqueName } from './helpers'

test('FR-015: the list shows name, hostname and last modified date', async ({ page, request }) => {
  const prefix = uniqueName('List')
  await createConfiguration(request, { name: `${prefix} A`, basics: { hostname: 'list-a' } })
  await createConfiguration(request, { name: `${prefix} B`, basics: { hostname: 'list-b' } })
  await page.goto('/')
  await page.getByRole('textbox', { name: 'Search name or hostname' }).fill(prefix)
  const rows = page.locator('tbody tr')
  await expect(rows).toHaveCount(2)
  await expect(rows.filter({ hasText: `${prefix} A` })).toContainText('list-a')
  await expect(rows.filter({ hasText: `${prefix} B` })).toContainText(String(new Date().getFullYear()))
})

test('FR-015: the list is filterable by hostname and sortable by name', async ({ page, request }) => {
  const prefix = uniqueName('Sort')
  for (const [suffix, host] of [
    ['b', 'zeta-host'],
    ['a', 'alpha-host'],
    ['c', 'gamma-host'],
  ]) {
    await createConfiguration(request, { name: `${prefix} ${suffix}`, basics: { hostname: host } })
  }
  await page.goto('/')
  await page.getByRole('textbox', { name: 'Search name or hostname' }).fill('alpha-host')
  await expect(page.locator('tbody tr')).toHaveCount(1)
  await expect(page.locator('tbody tr')).toContainText(`${prefix} a`)

  await page.getByRole('textbox', { name: 'Search name or hostname' }).fill(prefix)
  await page.getByRole('columnheader', { name: 'Name', exact: true }).click()
  await expect(page.locator('tbody tr td:first-child')).toHaveText([`${prefix} a`, `${prefix} b`, `${prefix} c`])
})

test('FR-015: duplicating creates "<name> (copy)" with a new instance-id and opens it', async ({ page, request }) => {
  const name = uniqueName('Original')
  const original = await createConfiguration(request, { name, basics: { hostname: 'dup-01' } })
  await page.goto('/')
  await page.getByRole('textbox', { name: 'Search name or hostname' }).fill(name)
  await page.getByRole('button', { name: `Duplicate ${name}` }).click()
  await expect(page).toHaveURL(/\/configurations\/[0-9a-f-]{36}$/)
  expect(page.url()).not.toContain(original.id)
  await expect(page.getByLabel('Configuration name')).toHaveValue(`${name} (copy)`)
  const instanceId = await page.getByLabel('Instance ID').inputValue()
  expect(instanceId).toMatch(/^iid-dup-01-/)
  expect(instanceId).not.toBe(original.basics.instance_id)
})

test('FR-015: deleting after confirmation removes the configuration', async ({ page, request }) => {
  const name = uniqueName('Delete me')
  const config = await createConfiguration(request, { name })
  await page.goto('/')
  await page.getByRole('textbox', { name: 'Search name or hostname' }).fill(name)
  await page.getByRole('button', { name: `Delete ${name}` }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Delete' }).click()
  await expect(page.locator('tbody')).toContainText('No configurations')
  expect((await request.get(`/api/configurations/${config.id}`)).status()).toBe(404)
})

test('FR-015: renaming directly in the list', async ({ page, request }) => {
  const name = uniqueName('Rename me')
  const config = await createConfiguration(request, { name, basics: { hostname: 'keep-me' } })
  await page.goto('/')
  await page.getByRole('textbox', { name: 'Search name or hostname' }).fill(name)
  await page.getByRole('button', { name: `Rename ${name}` }).click()
  await page.getByRole('dialog').getByLabel('Name').fill(`${name} renamed`)
  await page.getByRole('dialog').getByRole('button', { name: 'Rename' }).click()
  await expect(page.locator('tbody')).toContainText(`${name} renamed`)
  const stored = await (await request.get(`/api/configurations/${config.id}`)).json()
  expect(stored.name).toBe(`${name} renamed`)
  expect(stored.basics.hostname).toBe('keep-me')
})

test('UI-02: a new configuration is started from the list', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'New configuration' }).click()
  await expect(page).toHaveURL(/\/configurations\/new$/)
  await expect(page.getByLabel('Configuration name')).toHaveValue('New configuration')
})
