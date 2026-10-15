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
| httpx2 | Async HTTP client for the CouchDB API; also used by FastAPI's `TestClient` (successor of `httpx` recommended by Starlette) | BSD-3-Clause | Pydantic organization |

Notable transitive dependencies: `pydantic` (MIT), `starlette` (BSD-3-Clause).

CouchDB is accessed via its documented HTTP API instead of a client library: the only
async Python client, `aiocouch`, had no release within the last 12 months (LIB-002).

PyYAML: last release 6.0.3 (2025-09); LIB-002 is met through ongoing commits, including a
security fix (DoS via merge keys, 2026-06) that is not released yet. Relevant once user YAML is
parsed (FR-014): limit the input size there. `ruamel.yaml` was not chosen: effectively a single
maintainer (LIB-003).

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

## JavaScript development

| Package | Purpose | License | Maintained by |
|---------|---------|---------|---------------|
| vite | Build tool and dev server | MIT | Vite team (VoidZero) |
| @vitejs/plugin-vue | Vue single-file component support for Vite | MIT | Vite team |
| typescript | Type checking | Apache-2.0 | Microsoft |
| vue-tsc | Type checking of `.vue` files | MIT | Vue.js team |
| @vue/tsconfig | Shared TypeScript config for Vue | MIT | Vue.js team |
| @types/node | Node.js type definitions for the Vite config | MIT | DefinitelyTyped |

## Container image

| Component | Purpose | License | Source |
|-----------|---------|---------|--------|
| `python:3.13-alpine` | Runtime base image | PSF-2.0 (Python), MIT (Alpine base) | Docker Official Images |
| `node:24-alpine` | Frontend build stage only, not in the final image | MIT | Docker Official Images |
| `couchdb:3` | Tests only: contract tests and smoke test (DS-007); not part of the app image | Apache-2.0 | Docker Official Images (Apache CouchDB) |
| xorriso | ISO 9660 seed image (FR-002) | GPL-3.0-or-later | Alpine repository (GNU xorriso) |
| dosfstools | `mkfs.vfat` for RAW seed images (FR-002) | GPL-3.0-or-later | Alpine repository |
| mtools | Copy files into VFAT images without mounting (FR-002, NFR-002) | GPL-3.0-or-later | Alpine repository (GNU mtools) |
| qemu-img | Convert RAW to QCOW2 (FR-002) | GPL-2.0-only | Alpine repository (QEMU) |

The GPL-licensed tools are invoked as separate executables and are not linked into the
application; they are distributed alongside it in the container image (mere aggregation), so the
application itself stays MIT-licensed (LIB-001, NFR-017).

## Documented exceptions

| Dependency | Criterion not met | Rationale |
|------------|-------------------|-----------|
| TinyDB | LIB-003 | See section 8.5 of `requirements.md` |
