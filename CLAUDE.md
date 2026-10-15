# cloudinit-nocloud-configurator

Web app to build cloud-init **NoCloud** seed drives (ISO / RAW / QCOW2) from a guided form with live YAML preview.

## Source of truth

`docs/requirements.md` is the binding requirements specification. Read the relevant requirements before implementing anything.

## Working rules

- **Requirement IDs** (`FR-`, `NFR-`, `DS-`, `DEP-`, `LIB-`, `UI-`, `OQ-`, `R-`) are stable and never reused. Reference them in commit messages, PR descriptions and tests (test name or docstring), e.g. `FR-007: tag input for packages`.
- **Acceptance criteria** (Given/When/Then) are the basis for tests. Every implemented criterion gets at least one automated test.
- **Don't guess.** If a requirement is unclear or contradicts another, stop and ask. Record the question as a new `OQ-xx` in section 10 of the requirements.
- **New features or changed behavior go into `docs/requirements.md` first:** new ID, bump the version, add a change history entry.
- **Dependencies** must meet the criteria in section 8.5 (LIB-001 to LIB-006) and be listed in `docs/dependencies.md` with purpose and license. Documented exceptions only (currently: TinyDB).
- **Language:** English everywhere (UI, API messages, logs, docs, code comments) – NFR-014.
- **License:** MIT – NFR-017.

## Stack (see requirements section 8)

- Backend: Python 3.13, FastAPI, Pydantic model as single source of truth (FR-004); YAML is rendered in the backend only.
- Frontend: Vue 3 + Vite, served as static files by FastAPI.
- Datastore: repository interface with TinyDB (dev, default) and CouchDB (prod), selected via `DATASTORE_BACKEND` (section 8.3). Contract tests run against both (DS-007).
- Image generation without root or mounts: `xorriso`, `mkfs.vfat` + `mtools`, `qemu-img` (NFR-002).
- Container: Docker multi-stage build, `python:3.13-alpine` (fallback `python:3.13-slim`), non-root.
- Kubernetes: manifests in `deploy/k8s/` generated from the Helm chart in `deploy/helm/` (section 8.4).

## Suggested repository layout

```
backend/        FastAPI app, Pydantic models, renderers, image builders, repositories
frontend/       Vue 3 app
deploy/k8s/     Plain manifests (generated from the chart)
deploy/helm/    Helm chart
docs/           requirements.md, dependencies.md
Dockerfile
LICENSE
```

## Implementation order (MVP = all "Must" requirements, section 11)

Work in small, reviewable steps. Plan first, then implement step by step:

1. Project skeleton, Dockerfile (multi-stage, non-root), health endpoints (NFR-001 to NFR-004), `LICENSE`.
2. Repository interface with TinyDB and CouchDB plus contract tests (DS-001 to DS-007).
3. Pydantic model, YAML rendering and REST API for configurations (FR-001, FR-004, FR-005, FR-015).
4. Seed image generation and download (FR-002, FR-003).
5. Frontend: list (UI-02), editor with sections and live preview (UI-01, FR-013), theme switch (FR-016).
6. Form sections one by one: FR-006 to FR-012.
7. YAML editing round trip (FR-014).
8. Helm chart and generated manifests (DEP-001 to DEP-005).

## Commands

Backend (Python 3.13, managed with [uv](https://docs.astral.sh/uv/)), run in `backend/`:

```sh
uv sync                                    # install dependencies from uv.lock
uv run pytest                              # tests; CouchDB contract tests start a couchdb:3
                                           # container via Docker, or use COUCHDB_TEST_URL/_USER/_PASSWORD;
                                           # skipped without either (COUCHDB_TEST_REQUIRED=1 makes them fail)
uv run ruff check . && uv run ruff format --check .   # lint
uv run python -m app                       # run API on :8000 (config via env vars, NFR-003)
STATIC_DIR=../frontend/dist uv run python -m app      # also serve the built frontend
uv add <pkg>                               # new dependency -> also update docs/dependencies.md
```

Frontend (Node 24), run in `frontend/`:

```sh
npm ci                # install from package-lock.json
npm run dev           # Vite dev server; proxies /api, /healthz, /readyz to :8000
npm run build         # type check + production build to dist/
npm test              # unit tests (Vitest)
npm run test:e2e      # end-to-end tests (Playwright, Chromium); needs `npm run build` and uv
                      # (starts the backend on :8124 with a fresh TinyDB); incl. WCAG contrast checks
```

Container, run in the repository root:

```sh
buildah bud --layers --format docker -t cloudinit-nocloud-configurator .   # or: docker build
docker run --rm -p 8000:8000 cloudinit-nocloud-configurator                # needs docker or podman
scripts/smoke-test.sh   # build + non-root, seed image tools, read-only rootfs, health, TinyDB + CouchDB
ENGINE=buildah scripts/smoke-test.sh   # without docker/podman; skips read-only rootfs and CouchDB checks
```

Acceptance test with a real VM (FR-002): boots the Debian 13 cloud image with seeds in all three
formats (QEMU/KVM + OVMF, sudo if not in group kvm) and checks what cloud-init applied:

```sh
APP_URL=http://127.0.0.1:8000 scripts/boot-test.sh [iso|raw|qcow2]
```
