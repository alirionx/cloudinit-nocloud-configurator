# syntax=docker/dockerfile:1

# Stage 1: build the Vue frontend. Node is not part of the final image.
FROM node:24-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: resolve Python dependencies from the lock file into a virtualenv.
FROM python:3.13-alpine AS backend
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Stage 3: runtime image.
FROM python:3.13-alpine
# Image tools for seed drive generation without root or mounts (NFR-002, FR-002)
# and openssl for SHA-512-crypt password hashing (FR-010).
RUN apk upgrade --no-cache \
    && apk add --no-cache xorriso dosfstools mtools qemu-img openssl \
    && addgroup -S -g 10001 app \
    && adduser -S -D -H -u 10001 -G app app

WORKDIR /app
COPY --from=backend /opt/venv /opt/venv
COPY backend/app ./app
COPY --from=frontend /src/dist ./static
RUN python -m compileall -q app \
    && mkdir -p /app/data \
    && chown 10001:10001 /app/data

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STATIC_DIR=/app/static

# Numeric UID so that Kubernetes can verify runAsNonRoot (NFR-002).
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD wget -q -O /dev/null http://127.0.0.1:8000/healthz || exit 1
CMD ["python", "-m", "app"]
