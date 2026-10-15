# Dependencies

Overview of all direct dependencies with purpose and license (LIB-006). Every entry was checked
against the criteria LIB-001 to LIB-005 in section 8.5 of `requirements.md` when it was added.
Exact versions are pinned in `backend/uv.lock` and `frontend/package-lock.json`.

Review this list for every release.

## Python runtime (`backend/pyproject.toml`)

| Package | Purpose | License | Maintained by |
|---------|---------|---------|---------------|
| fastapi | Web framework, REST API, OpenAPI docs (NFR-010) | MIT | FastAPI organization |
| uvicorn | ASGI server | BSD-3-Clause | Encode / Kludex |
| pydantic-settings | Settings from environment variables (NFR-003) | MIT | Pydantic organization |
| anyio | Runs blocking TinyDB calls in worker threads; async test support | MIT | agronholm / community |
| tinydb | Datastore backend for development and single instances (section 8.3) | MIT | msiemens (see exceptions) |
| pyyaml | Rendering the NoCloud YAML files (FR-001, FR-004) | MIT | YAML organization |
| jsonschema | Validation against the cloud-init JSON schemas (NFR-008, FR-014) | MIT | python-jsonschema organization |
| httpx2 | Async HTTP client for the CouchDB API; also used by FastAPI's `TestClient` (successor of `httpx` recommended by Starlette) | BSD-3-Clause | Pydantic organization |

Notable transitive dependencies: `pydantic` (MIT), `starlette` (BSD-3-Clause).

CouchDB is accessed via its documented HTTP API instead of a client library: the only
async Python client, `aiocouch`, had no release within the last 12 months (LIB-002).

PyYAML: last release 6.0.3 (2025-09); LIB-002 is met through ongoing commits, including a
security fix (DoS via merge keys, 2026-06) that is not released yet. Relevant once user YAML is
parsed (FR-014): limit the input size there. `ruamel.yaml` was not chosen: effectively a single
maintainer (LIB-003).

Vendored data: the cloud-init JSON schemas in `backend/app/schemas/` (cloud-init 25.1.4 from
Debian 13), used under Apache-2.0 (cloud-init is dual-licensed GPL-3 / Apache-2.0); see
`backend/app/schemas/NOTICE.md`.

## Python development

| Package | Purpose | License | Maintained by |
|---------|---------|---------|---------------|
| pytest | Test runner | MIT | pytest-dev |
| ruff | Linter and formatter | MIT | Astral |
| uv | Package manager and lock files (NFR-016); used at build time only, not in the runtime image | MIT OR Apache-2.0 | Astral |

## JavaScript runtime (`frontend/package.json`)

| Package | Purpose | License | Maintained by |
|---------|---------|---------|---------------|
| vue | UI framework (section 8.1) | MIT | Vue.js team |
| vue-router | Routing between list (UI-02) and editor (UI-01) | MIT | Vue.js team |
| vuetify | Component library with light/dark themes (section 7.2, FR-016) | MIT | Vuetify LLC |
| @lucide/vue | Icons | ISC | Lucide (lucide-icons organization) |
| @fontsource-variable/inter | Font Inter, bundled with the frontend instead of loaded from a CDN (section 7.2, NFR-012) | OFL-1.1 (font), MIT (package) | Fontsource |
| @codemirror/state, view, commands, language, lint | Code editor with line numbers and error markers (FR-008, FR-013, FR-014) | MIT | CodeMirror (Marijn Haverbeke, Adrian Heine) |
| @codemirror/lang-yaml, lang-json, legacy-modes | Syntax highlighting for YAML, JSON, shell, ini/conf, TOML, Python (FR-008) | MIT | CodeMirror |
| @codemirror/theme-one-dark | Dark editor theme (FR-016) | MIT | CodeMirror |
| swagger-ui-dist | Swagger UI for /docs, served locally instead of from a CDN (NFR-010, NFR-012); copied to `dist/swagger/` at build time | Apache-2.0 | SmartBear (swagger-api) |

Notes on the selection:

- **PrimeVue was rejected:** since version 5 PrimeVue, PrimeIcons and @primeuix/themes are
  released under the commercial "PrimeUI License" (free tier with restrictions), which is not
  an OSI-approved license (LIB-001).
- **Icons:** `@mdi/js` was rejected (own non-OSI license, no release since 2023, LIB-001/002).
  Vuetify's built-in icons use its embedded `mdi-svg` set; app icons come from Lucide.
- **CodeMirror** is published by one npm account, but has a second regular committer on
  GitHub and very broad usage (LIB-003). Monaco was not chosen because of its size.

## JavaScript development

| Package | Purpose | License | Maintained by |
|---------|---------|---------|---------------|
| vite | Build tool and dev server | MIT | Vite team (VoidZero) |
| @vitejs/plugin-vue | Vue single-file component support for Vite | MIT | Vite team |
| vite-plugin-vuetify | Tree-shaking and auto-import of Vuetify components | MIT | Vuetify LLC |
| typescript | Type checking | Apache-2.0 | Microsoft |
| vue-tsc | Type checking of `.vue` files | MIT | Vue.js team |
| @vue/tsconfig | Shared TypeScript config for Vue | MIT | Vue.js team |
| @types/node | Node.js type definitions for the Vite config | MIT | DefinitelyTyped |
| vitest | Unit tests | MIT | Vitest team (VoidZero) |
| jsdom | DOM environment for unit tests | MIT | jsdom organization |
| @playwright/test | End-to-end tests in a real browser | Apache-2.0 | Microsoft |
| @axe-core/playwright | Automated WCAG contrast checks in end-to-end tests (FR-016, NFR-013) | MPL-2.0 | Deque Systems |

`@axe-core/playwright` (MPL-2.0, file-level copyleft) is only used in tests and is not
distributed with the application.

## Container image

| Component | Purpose | License | Source |
|-----------|---------|---------|--------|
| `python:3.13-alpine` | Runtime base image | PSF-2.0 (Python), MIT (Alpine base) | Docker Official Images |
| `node:24-alpine` | Frontend build stage only, not in the final image | MIT | Docker Official Images |
| openssl | SHA-512-crypt password hashing via `openssl passwd -6` (FR-010) | Apache-2.0 | Alpine repository (OpenSSL project) |
| `debian:stable` | Tests only: manual validation with the `cloud-init schema` CLI | Various (DFSG) | Docker Official Images |
| Debian 13 genericcloud image, QEMU, OVMF | Tests only: `scripts/boot-test.sh` (FR-002); not part of the app | Various (DFSG), GPL-2.0, BSD-2-Clause-Patent | Debian, QEMU, TianoCore |
| `couchdb:3` | Tests (contract tests, smoke test, compose); `couchdb:3.5` is deployed by the Helm chart when `couchdb.enabled=true` (DEP-003) | Apache-2.0 | Docker Official Images (Apache CouchDB) |
| kind | Tests only: `scripts/kind-test.sh` (throwaway Kubernetes cluster) | Apache-2.0 | Kubernetes SIGs |
| Helm | Chart, manifest generation (DEP-007), lint (DEP-008) | Apache-2.0 | CNCF |
| xorriso | ISO 9660 seed image (FR-002) | GPL-3.0-or-later | Alpine repository (GNU xorriso) |
| dosfstools | `mkfs.vfat` for RAW seed images (FR-002) | GPL-3.0-or-later | Alpine repository |
| mtools | Copy files into VFAT images without mounting (FR-002, NFR-002) | GPL-3.0-or-later | Alpine repository (GNU mtools) |
| qemu-img | Convert RAW to QCOW2 (FR-002) | GPL-2.0-only | Alpine repository (QEMU) |

The GPL-licensed tools are invoked as separate executables and are not linked into the
application; they are distributed alongside it in the container image (mere aggregation), so the
application itself stays MIT-licensed (LIB-001, NFR-017).

## CI (GitHub Actions)

| Action | Purpose | License | Maintained by |
|--------|---------|---------|---------------|
| actions/checkout | Check out the repository | MIT | GitHub |
| docker/setup-buildx-action | Buildx builder with GitHub Actions cache | Apache-2.0 | Docker |
| docker/login-action | Log in to ghcr.io with the workflow token | Apache-2.0 | Docker |
| docker/metadata-action | Image tags (`main`, `sha-<commit>`) and OCI labels | Apache-2.0 | Docker |
| docker/build-push-action | Build and push the image | Apache-2.0 | Docker |
| azure/setup-helm | Install Helm for chart checks | MIT | Microsoft (Azure) |

## Documented exceptions

| Dependency | Criterion not met | Rationale |
|------------|-------------------|-----------|
| TinyDB | LIB-003 | See section 8.5 of `requirements.md` |
