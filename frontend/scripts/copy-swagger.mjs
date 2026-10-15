// NFR-012: Swagger UI (/docs) is served from local files instead of a CDN.
import { copyFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const source = join(root, 'node_modules', 'swagger-ui-dist')
const target = join(root, 'dist', 'swagger')
mkdirSync(target, { recursive: true })
for (const file of ['swagger-ui-bundle.js', 'swagger-ui.css', 'LICENSE', 'NOTICE']) {
  copyFileSync(join(source, file), join(target, file))
}
console.log(`Swagger UI copied to ${target}`)
