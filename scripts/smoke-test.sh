#!/usr/bin/env sh
# Container smoke test: builds the image and checks NFR-001, NFR-002, NFR-004 and NFR-005.
set -eu

IMAGE="${IMAGE:-cloudinit-nocloud-configurator:smoke-test}"
NAME="cnc-smoke-test-$$"
PORT="${PORT:-18000}"

cd "$(dirname "$0")/.."

echo "==> Building $IMAGE"
docker build -t "$IMAGE" .

echo "==> NFR-002: container runs as a non-root user"
uid="$(docker run --rm "$IMAGE" id -u)"
[ "$uid" != "0" ] || { echo "FAIL: container runs as root"; exit 1; }
echo "ok (uid $uid)"

echo "==> FR-002: image tools are available"
for tool in xorriso mkfs.vfat mcopy qemu-img; do
  docker run --rm "$IMAGE" sh -c "command -v $tool" >/dev/null \
    || { echo "FAIL: $tool not found"; exit 1; }
done
echo "ok"

echo "==> NFR-002 / NFR-005: app starts with a read-only root filesystem"
docker run -d --name "$NAME" --read-only --tmpfs /tmp \
  --cap-drop ALL --security-opt no-new-privileges \
  -p "127.0.0.1:$PORT:8000" "$IMAGE" >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT

for _ in $(seq 1 30); do
  curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null && break
  sleep 1
done

echo "==> NFR-004: health endpoints"
curl -sf "http://127.0.0.1:$PORT/healthz" && echo
curl -sf "http://127.0.0.1:$PORT/readyz" && echo

echo "==> Section 8.1: frontend is served"
curl -sf "http://127.0.0.1:$PORT/" | grep -q '<div id="app">'
echo "ok"

echo "All smoke tests passed."
