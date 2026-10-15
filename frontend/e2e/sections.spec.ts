import { type Page, expect, test } from '@playwright/test'
import { createConfiguration, openPreviewTab, previewText, uniqueName } from './helpers'

const KEY = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl test'

async function openSection(page: Page, title: string) {
  await page.getByRole('button', { name: new RegExp(`^${title}`) }).click()
}

const chips = (page: Page, label: string) =>
  page.locator('.tag-input').filter({ has: page.getByLabel(label, { exact: true }) }).locator('.v-chip')

test('FR-007: "git, wget docker.io" + Enter creates three entries', async ({ page }) => {
  await page.goto('/configurations/new')
  await openSection(page, 'Packages')
  const input = page.getByLabel('Packages', { exact: true })
  await input.pressSequentially('git, wget docker.io')
  await input.press('Enter')
  await expect(chips(page, 'Packages')).toHaveText(['git', 'wget', 'docker.io'])
  await expect.poll(() => previewText(page)).toContain('- docker.io')
})

test('FR-007: an entry already in the list is not added twice', async ({ page }) => {
  await page.goto('/configurations/new')
  await openSection(page, 'Packages')
  const input = page.getByLabel('Packages', { exact: true })
  await input.pressSequentially('git ')
  await input.pressSequentially('git ')
  await expect(chips(page, 'Packages')).toHaveText(['git'])
})

test('FR-007: several packages can be pasted at once', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await page.goto('/configurations/new')
  await openSection(page, 'Packages')
  await page.evaluate(() => navigator.clipboard.writeText('curl\nvim\njq'))
  const input = page.getByLabel('Packages', { exact: true })
  await input.focus()
  await page.keyboard.press('ControlOrMeta+V')
  await input.press('Enter')
  await expect(chips(page, 'Packages')).toHaveText(['curl', 'vim', 'jq'])
})

test('FR-008: an uploaded binary file is included Base64-encoded', async ({ page }) => {
  await page.goto('/configurations/new')
  await openSection(page, 'Files')
  await page.getByRole('button', { name: 'Add file' }).click()
  await page.getByLabel('Target path').fill('/opt/blob.bin')
  const chooser = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: 'Upload file' }).click()
  await (await chooser).setFiles({ name: 'blob.bin', mimeType: 'application/octet-stream', buffer: Buffer.from([0, 1, 2, 255]) })
  await expect(page.getByText('Binary file (4 bytes)')).toBeVisible()
  await expect.poll(() => previewText(page)).toContain('encoding: b64')
  expect(await previewText(page)).toContain('content: AAEC/w==')
})

test('FR-008: a relative target path is marked as an error', async ({ page }) => {
  await page.goto('/configurations/new')
  await openSection(page, 'Files')
  await page.getByRole('button', { name: 'Add file' }).click()
  await page.getByLabel('Target path').fill('etc/motd')
  await page.getByLabel('Target path').blur()
  await expect(page.getByText('must be an absolute path').first()).toBeVisible()
})

test('FR-008: defer is suggested for files owned by created users', async ({ page }) => {
  await page.goto('/configurations/new')
  await openSection(page, 'Users and groups')
  await page.getByRole('button', { name: 'Add user' }).click()
  await page.getByLabel('User name').fill('app')
  await openSection(page, 'Files')
  await page.getByRole('button', { name: 'Add file' }).click()
  await page.getByLabel('Target path').fill('/home/app/.env')
  await page.getByLabel('Owner').fill('app:app')
  await expect(page.locator('.yaml-preview')).toContainText("enable 'defer'")
  await page.getByLabel('Defer (write after users are created)').check()
  await expect(page.locator('.yaml-preview')).not.toContainText("enable 'defer'")
})

test('FR-009: reordering runcmd entries changes the YAML order', async ({ page, request }) => {
  const config = await createConfiguration(request, {
    name: uniqueName('Order'),
    commands: { runcmd: ['echo one', 'echo two', 'echo three'] },
  })
  await page.goto(`/configurations/${config.id}`)
  await openSection(page, 'Commands')
  // Drag the third entry onto the first. Native drag events are dispatched in the page
  // because simulated mouse drags are unreliable in the headless test runner.
  await page.evaluate(() => {
    const source = document.querySelector('[aria-label="Drag runcmd entry 3"]')!
    const target = [...document.querySelectorAll('.item-card')].find((c) => c.textContent?.includes('#1 echo one'))!
    const data = new DataTransfer()
    source.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: data }))
    target.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: data }))
    target.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: data }))
    source.dispatchEvent(new DragEvent('dragend', { bubbles: true, dataTransfer: data }))
  })
  await expect.poll(() => previewText(page)).toMatch(/- echo three\s+- echo one\s+- echo two/)
  // ... and move it back down with the keyboard-accessible buttons.
  await page.getByRole('button', { name: 'Move #1 echo three down' }).click()
  await expect.poll(() => previewText(page)).toMatch(/- echo one\s+- echo three\s+- echo two/)
})

test('FR-009: the UI explains that bootcmd runs on every boot', async ({ page }) => {
  await page.goto('/configurations/new')
  await openSection(page, 'Commands')
  await expect(page.getByText('runs very early on every boot', { exact: false })).toBeVisible()
})

test('FR-010: a stored password is only shown as "set"', async ({ page, request }) => {
  const config = await createConfiguration(request, {
    name: uniqueName('Password'),
    users: { users: [{ name: 'alice', password: 'Sup3r-Secret!', lock_passwd: false }] },
    ssh: { authorized_keys: [KEY] },
  })
  await page.goto(`/configurations/${config.id}`)
  await openSection(page, 'Users and groups')
  await expect(page.getByText('Password set')).toBeVisible()
  await expect(page.locator('body')).not.toContainText('Sup3r-Secret!')
  // The preview masks the hash by default (FR-013).
  await expect.poll(() => previewText(page)).toContain('passwd: ********')
  await page.getByRole('button', { name: 'Remove password' }).click()
  await expect(page.getByText('No password', { exact: true })).toBeVisible()
  await expect.poll(() => previewText(page)).not.toMatch(/^\s+passwd:/m)
})

test('FR-010: marking a user as administrator adds the group sudo', async ({ page }) => {
  await page.goto('/configurations/new')
  await openSection(page, 'Users and groups')
  await page.getByRole('button', { name: 'Add user' }).click()
  await page.getByLabel('User name').fill('ops')
  await page.getByLabel('Administrator (group sudo)').check()
  await expect.poll(() => previewText(page)).toMatch(/groups:\s+- sudo/)
})

test('FR-010: an invalid SSH key is marked as an error', async ({ page }) => {
  await page.goto('/configurations/new')
  await openSection(page, 'SSH')
  const keys = page.getByLabel('Authorized keys for the default user (one per line)')
  await keys.fill('ssh-ed25519 not-a-key')
  await keys.blur()
  await expect(page.getByText('Line 1: must be an SSH public key').first()).toBeVisible()
})

test('FR-011: the SSH warning disappears once a key is added', async ({ page }) => {
  await page.goto('/configurations/new')
  await expect(page.locator('.yaml-preview')).toContainText('not be reachable via SSH')
  await openSection(page, 'SSH')
  await page.getByLabel('Authorized keys for the default user (one per line)').fill(KEY)
  await expect(page.locator('.yaml-preview')).not.toContainText('not be reachable via SSH')
  await expect.poll(() => previewText(page)).toContain('ssh_pwauth: false')
})

test('FR-012: "force overwrite" requires confirming a data-loss warning', async ({ page }) => {
  await page.goto('/configurations/new')
  await openSection(page, 'Disks')
  await page.getByRole('button', { name: 'Add disk' }).click()
  const overwrite = page.getByLabel('Force overwrite')
  await overwrite.click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('All data on this disk will be lost')
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(overwrite).not.toBeChecked()
  await overwrite.click()
  await page.getByRole('dialog').getByRole('button', { name: /Overwrite/ }).click()
  await expect(overwrite).toBeChecked()
  await expect.poll(() => previewText(page)).toContain('overwrite: true')
})

test('FR-006: bridge with member NIC renders the expected network-config', async ({ page }) => {
  await page.goto('/configurations/new')
  await openSection(page, 'Network')
  await page.getByRole('button', { name: 'Add NIC' }).click()
  await page.getByRole('button', { name: 'Add bridge' }).click()
  await page.locator('.v-select').filter({ has: page.getByLabel('Member NICs') }).click()
  await page.getByRole('option', { name: 'eth0' }).click()
  await page.keyboard.press('Escape')
  const bridge = page.locator('.item-card').filter({ hasText: 'br0' })
  await bridge.getByLabel('Static addresses (CIDR)').fill('192.168.1.10/24')
  await bridge.getByLabel('Static addresses (CIDR)').press('Enter')
  await openPreviewTab(page, 'network-config')
  await expect.poll(() => previewText(page)).toMatch(/eth0: \{\}[\s\S]*br0:\s+interfaces:\s+- eth0\s+addresses:\s+- 192.168.1.10\/24/)
})
