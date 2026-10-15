import { type Page, expect, test } from '@playwright/test'
import { createConfiguration, openPreviewTab, previewText, uniqueName } from './helpers'

const KEY = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl test'

async function editAsYaml(page: Page, file: string) {
  await page.locator('.yaml-preview').getByRole('button', { name: 'Edit as YAML' }).click()
  await page.getByRole('listitem').filter({ hasText: new RegExp(`(Edit|Add) ${file}$`) }).click()
  await expect(page.getByText(`Editing ${file} as YAML`)).toBeVisible()
}

/** Replace the content of the YAML editor (CodeMirror). */
async function setYaml(page: Page, text: string) {
  const editor = page.locator('.yaml-preview .cm-content')
  await editor.click()
  await page.keyboard.press('ControlOrMeta+A')
  await page.keyboard.press('Delete')
  // insertText adds the text in one input operation (no auto-indentation per line).
  await page.keyboard.insertText(text)
  await expect.poll(() => previewText(page)).toContain(text.split('\n').filter(Boolean).slice(-1)[0]!.trim())
}

async function apply(page: Page) {
  await page.getByRole('button', { name: 'Apply to form' }).click()
}

test('FR-014: a hostname changed in the YAML editor shows up in the form', async ({ page, request }) => {
  const config = await createConfiguration(request, { name: uniqueName('Yaml host'), basics: { hostname: 'web-01', instance_id: 'iid-y1' } })
  await page.goto(`/configurations/${config.id}`)
  await editAsYaml(page, 'meta-data')
  await setYaml(page, 'instance-id: iid-y1\nlocal-hostname: web-02\n')
  await apply(page)
  await expect(page.getByLabel('Hostname (local-hostname)')).toHaveValue('web-02')
  await expect(page.getByText('Unsaved changes')).toBeVisible()
})

test('FR-014: an unknown key added as YAML survives saving and reloading', async ({ page, request }) => {
  const config = await createConfiguration(request, { name: uniqueName('Yaml ntp'), ssh: { authorized_keys: [KEY] } })
  await page.goto(`/configurations/${config.id}`)
  await editAsYaml(page, 'user-data')
  await setYaml(page, `#cloud-config\nssh_pwauth: false\ndisable_root: true\nssh_authorized_keys:\n- ${KEY}\nntp:\n  enabled: true\n`)
  await apply(page)
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByText('Unsaved changes')).toBeHidden()
  await page.reload()
  await expect.poll(() => previewText(page)).toContain('ntp:')
  await page.getByRole('button', { name: /^Additional settings/ }).click()
  await expect(page.locator('#section-additional')).toContainText('ntp')
})

test('FR-014: YAML with a syntax error is not applied; the error shows its line', async ({ page }) => {
  await page.goto('/configurations/new')
  await editAsYaml(page, 'user-data')
  await setYaml(page, '#cloud-config\npackages:\n- git\n bad: [unclosed\n')
  await apply(page)
  await expect(page.getByText('Line 4')).toBeVisible()
  await expect(page.getByText(/YAML syntax error/)).toBeVisible()
  await expect(page.getByText('Editing user-data as YAML')).toBeVisible()
  // Saving is prevented as well.
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page).toHaveURL(/\/configurations\/new$/)
})

test('FR-014: a schema violation is a located hint; saving works, the download warns', async ({ page, request }) => {
  const config = await createConfiguration(request, { name: uniqueName('Yaml schema'), ssh: { authorized_keys: [KEY] } })
  await page.goto(`/configurations/${config.id}`)
  await editAsYaml(page, 'user-data')
  await setYaml(page, `#cloud-config\nssh_authorized_keys:\n- ${KEY}\nntp:\n  enabled: maybe\n`)
  await apply(page)
  const hint = page.locator('.yaml-preview').getByText(/cloud-init schema: user-data, line \d+ \(ntp.enabled\)/)
  await expect(hint).toBeVisible()
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByText('Unsaved changes')).toBeHidden()
  await page.getByRole('button', { name: 'Download', exact: true }).click()
  await page.getByRole('listitem').filter({ hasText: 'ISO' }).first().click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('does not match the cloud-init schema')
  const download = page.waitForEvent('download')
  await dialog.getByRole('button', { name: 'Download anyway' }).click()
  expect((await download).suggestedFilename()).toMatch(/\.iso$/)
})

test('FR-014: the UI points out that comments are not preserved', async ({ page }) => {
  await page.goto('/configurations/new')
  await editAsYaml(page, 'user-data')
  await expect(page.getByText('Comments are not preserved')).toBeHidden()
  await setYaml(page, '#cloud-config\n# my comment\nssh_pwauth: false\n')
  await expect(page.getByText('Comments are not preserved')).toBeVisible()
})

test('FR-014: a plain-text password in the YAML gives a warning', async ({ page }) => {
  await page.goto('/configurations/new')
  await editAsYaml(page, 'user-data')
  await setYaml(page, '#cloud-config\nchpasswd:\n  users:\n  - {name: root, password: secret, type: text}\n')
  await apply(page)
  await expect(page.locator('.yaml-preview')).toContainText('contains a plain-text password')
})

test('FR-014: discarding YAML changes and reverting to the saved state', async ({ page, request }) => {
  const config = await createConfiguration(request, { name: uniqueName('Yaml revert'), basics: { hostname: 'orig', instance_id: 'iid-r' } })
  await page.goto(`/configurations/${config.id}`)
  await editAsYaml(page, 'meta-data')
  // The form is locked while editing.
  await expect(page.getByText('The form is locked while')).toBeVisible()
  await expect(page.locator('.v-expansion-panels')).toHaveAttribute('inert')
  await setYaml(page, 'instance-id: iid-r\nlocal-hostname: changed\n')
  await page.getByRole('button', { name: 'Discard YAML changes' }).click()
  await expect(page.getByLabel('Hostname (local-hostname)')).toHaveValue('orig')
  // Revert to the last saved state after changes in the form.
  await page.getByLabel('Hostname (local-hostname)').fill('other')
  await page.getByRole('button', { name: 'Revert to saved' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Revert' }).click()
  await expect(page.getByLabel('Hostname (local-hostname)')).toHaveValue('orig')
  await expect(page.getByText('Unsaved changes')).toBeHidden()
})

test('FR-014: settings the form cannot show are kept and marked in the section', async ({ page }) => {
  await page.goto('/configurations/new')
  await editAsYaml(page, 'user-data')
  await setYaml(page, '#cloud-config\nusers:\n- default\n- name: bob\n  homedir: /srv/bob\n')
  await apply(page)
  await expect(page.locator('.yaml-preview')).toContainText("'users' contains settings the form does not support")
  await page.getByRole('button', { name: /^Users and groups/ }).click()
  await expect(page.locator('#section-users')).toContainText('Kept as YAML in the additional settings')
  await openPreviewTab(page, 'user-data')
  await expect.poll(() => previewText(page)).toContain('homedir: /srv/bob')
})

test('FR-006, FR-014: network-config can be added as YAML', async ({ page }) => {
  await page.goto('/configurations/new')
  await editAsYaml(page, 'network-config')
  await setYaml(page, 'network:\n  version: 2\n  ethernets:\n    eth0:\n      dhcp4: true\n')
  await apply(page)
  await page.getByRole('button', { name: /^Network/ }).click()
  await expect(page.locator('#section-network').getByLabel('Name', { exact: true })).toHaveValue('eth0')
})
