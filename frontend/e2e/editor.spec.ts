import { expect, test } from '@playwright/test'
import { createConfiguration, openPreviewTab, previewText, uniqueName } from './helpers'

test('FR-013: the preview shows a change no later than 1 second after the last input', async ({ page }) => {
  await page.goto('/configurations/new')
  await openPreviewTab(page, 'meta-data')
  await page.getByLabel('Hostname (local-hostname)').fill('fast-preview')
  const started = Date.now()
  await expect.poll(() => previewText(page), { timeout: 1000, intervals: [50] }).toContain(
    'local-hostname: fast-preview',
  )
  expect(Date.now() - started).toBeLessThan(1000)
})

test('FR-013: tabs without content are greyed out', async ({ page }) => {
  await page.goto('/configurations/new')
  const preview = page.locator('.yaml-preview')
  await expect(preview.getByRole('tab', { name: 'user-data' })).toBeEnabled()
  await expect(preview.getByRole('tab', { name: 'meta-data' })).toBeEnabled()
  await expect(preview.getByRole('tab', { name: 'network-config' })).toBeDisabled()
  await expect(preview.getByRole('tab', { name: 'vendor-data' })).toBeDisabled()
})

test('FR-004: an invalid value is shown at the field once the field is left', async ({ page }) => {
  await page.goto('/configurations/new')
  const hostname = page.getByLabel('Hostname (local-hostname)')
  await hostname.fill('web_01')
  const input = page.locator('.v-input.v-text-field').filter({ has: page.locator('#field-basics-hostname') })
  // The preview already knows the error, but it is not shown at the field while typing ...
  await expect(page.locator('.yaml-preview')).toContainText('must be a host name')
  await expect(input).not.toContainText('must be a host name')
  // ... only once the field is left.
  await hostname.blur()
  await expect(input).toContainText('must be a host name')
})

test('FR-013: clicking an error in the preview jumps to the affected field', async ({ page }) => {
  await page.goto('/configurations/new')
  await page.getByLabel('Hostname (local-hostname)').fill('web_01')
  await page.getByLabel('Configuration name').click()
  const error = page.locator('.yaml-preview').getByText('basics › hostname')
  await expect(error).toBeVisible()
  // Collapse the section, then use the error link to get back to the field.
  await page.getByRole('button', { name: /^Basics/ }).click()
  await expect(page.getByLabel('Hostname (local-hostname)')).toBeHidden()
  await error.click()
  await expect(page.getByLabel('Hostname (local-hostname)')).toBeFocused()
})

test('FR-013: Copy puts the content of the active file into the clipboard', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await page.goto('/configurations/new')
  await page.getByLabel('Hostname (local-hostname)').fill('copy-me')
  await openPreviewTab(page, 'meta-data')
  await expect.poll(() => previewText(page)).toContain('local-hostname: copy-me')
  await page.locator('.yaml-preview').getByRole('button', { name: 'Copy' }).click()
  const clipboard = await page.evaluate(() => navigator.clipboard.readText())
  expect(clipboard).toContain('local-hostname: copy-me')
  expect(clipboard).toContain('instance-id: iid-copy-me-')
})

test('FR-005: the instance-id is suggested from the hostname', async ({ page }) => {
  await page.goto('/configurations/new')
  await page.getByLabel('Hostname (local-hostname)').fill('web-07')
  await expect(page.getByLabel('Instance ID')).toHaveValue(/^iid-web-07-[0-9a-f]{8}$/)
  // Once edited by hand, it no longer follows the hostname.
  await page.getByLabel('Instance ID').fill('my-own-id')
  await page.getByLabel('Hostname (local-hostname)').fill('web-08')
  await expect(page.getByLabel('Instance ID')).toHaveValue('my-own-id')
})

test('FR-015: a new configuration is saved and stays open in the editor', async ({ page }) => {
  const name = uniqueName('Saved')
  await page.goto('/configurations/new')
  await page.getByLabel('Configuration name').fill(name)
  await page.getByLabel('Hostname (local-hostname)').fill('saved-01')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page).toHaveURL(/\/configurations\/[0-9a-f-]{36}$/)
  await expect(page.getByText('Unsaved changes')).toBeHidden()
  await page.reload()
  await expect(page.getByLabel('Hostname (local-hostname)')).toHaveValue('saved-01')
})

test('FR-015: leaving the editor with unsaved changes asks first', async ({ page, request }) => {
  const config = await createConfiguration(request, { name: uniqueName('Unsaved') })
  await page.goto(`/configurations/${config.id}`)
  await page.getByLabel('Hostname (local-hostname)').fill('changed')
  await page.getByRole('link', { name: 'Back to the list' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('Discard unsaved changes?')
  await dialog.getByRole('button', { name: 'Stay' }).click()
  await expect(page).toHaveURL(new RegExp(config.id))
  await page.getByRole('link', { name: 'Back to the list' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Discard changes' }).click()
  await expect(page).toHaveURL(/\/$/)
})

test('FR-015: saving over a concurrent change shows a conflict instead of overwriting', async ({ page, request }) => {
  const config = await createConfiguration(request, { name: uniqueName('Conflict') })
  await page.goto(`/configurations/${config.id}`)
  await expect(page.getByLabel('Configuration name')).toHaveValue(config.name)
  // Someone else saves in the meantime.
  await request.put(`/api/configurations/${config.id}`, {
    data: { name: 'Changed elsewhere', revision: config.revision },
  })
  await page.getByLabel('Hostname (local-hostname)').fill('mine')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('dialog')).toContainText('Changed in the meantime')
  await page.getByRole('button', { name: 'Reload latest version' }).click()
  await expect(page.getByLabel('Configuration name')).toHaveValue('Changed elsewhere')
})

test('FR-003: the download offers ISO, RAW and QCOW2 with matching file names', async ({ page, request }) => {
  const config = await createConfiguration(request, { name: 'Download Test', basics: { hostname: 'dl-01' } })
  await page.goto(`/configurations/${config.id}`)
  for (const [format, extension] of [
    ['ISO', '.iso'],
    ['RAW', '.img'],
    ['QCOW2', '.qcow2'],
  ]) {
    await page.getByRole('button', { name: 'Download', exact: true }).click()
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('listitem').filter({ hasText: format }).first().click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe(`download-test-cidata${extension}`)
  }
})

test('FR-013: the downloaded image is built from the same YAML as the preview', async ({ page, request }) => {
  const config = await createConfiguration(request, { name: uniqueName('Same'), basics: { hostname: 'same-01' } })
  await page.goto(`/configurations/${config.id}`)
  await openPreviewTab(page, 'meta-data')
  await expect.poll(() => previewText(page)).toContain('local-hostname: same-01')
  const shown = await previewText(page)
  const files = await (await request.get(`/api/configurations/${config.id}/files`)).json()
  expect(shown.trim()).toBe(files['meta-data'].trim())
})

test('FR-015: a new configuration starts with its name selected for editing', async ({ page }) => {
  await page.goto('/configurations/new')
  const name = page.getByLabel('Configuration name')
  await expect(name).toBeFocused()
  await page.keyboard.type('web-42')
  await expect(name).toHaveValue('web-42')
})

test('FR-015: the pencil next to the title focuses the name field', async ({ page, request }) => {
  const config = await createConfiguration(request, { name: uniqueName('Pencil') })
  await page.goto(`/configurations/${config.id}`)
  await expect(page.getByLabel('Configuration name')).toHaveValue(config.name)
  await page.getByRole('button', { name: 'Rename configuration' }).click()
  await expect(page.getByLabel('Configuration name')).toBeFocused()
  await page.keyboard.type('renamed-in-editor')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByText('Unsaved changes')).toBeHidden()
  const stored = await (await request.get(`/api/configurations/${config.id}`)).json()
  expect(stored.name).toBe('renamed-in-editor')
})
