import { type APIRequestContext, type Page, expect } from '@playwright/test'

let counter = 0

/** A name unique to this test run, so tests do not see each other's data. */
export function uniqueName(prefix: string): string {
  counter += 1
  return `${prefix} ${Date.now().toString(36)}${counter}`
}

export async function createConfiguration(
  request: APIRequestContext,
  body: Record<string, unknown>,
): Promise<{ id: string; name: string; revision: string; basics: Record<string, unknown> }> {
  const response = await request.post('/api/configurations', { data: body })
  expect(response.status()).toBe(201)
  return response.json()
}

/** The text of the YAML preview editor. */
export async function previewText(page: Page): Promise<string> {
  return (await page.locator('.yaml-preview .cm-content').innerText()).replace(/ /g, ' ')
}

export async function openPreviewTab(page: Page, name: string) {
  await page.locator('.yaml-preview').getByRole('tab', { name, exact: true }).click()
}
