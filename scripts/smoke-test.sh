#!/usr/bin/env sh
# Container smoke test: builds the image and checks NFR-001, NFR-002, NFR-004 and NFR-005.
#
# Container engine: ENGINE=docker|podman|buildah (default: first working one found).
# With buildah there is no read-only root filesystem; that check is skipped.
set -eu

IMAGE="${IMAGE:-localhost/cloudinit-nocloud-configurator:smoke-test}"
PORT="${PORT:-18000}"

cd "$(dirname "$0")/.."

if [ -z "${ENGINE:-}" ]; then
  for candidate in docker podman buildah; do
    if "$candidate" version >/dev/null 2>&1; then ENGINE="$candidate"; break; fi
  done
fi
[ -n "${ENGINE:-}" ] || { echo "FAIL: no working docker, podman or buildah found"; exit 1; }
echo "==> Using $ENGINE"

# run_in_image <command...>: run a command in a fresh container of the image.
if [ "$ENGINE" = "buildah" ]; then
  run_in_image() {
    ctr="$(buildah from -q "$IMAGE")"
    buildah run "$ctr" "$@"
    status=$?
    buildah rm "$ctr" >/dev/null
    return $status
  }
else
  run_in_image() { "$ENGINE" run --rm "$IMAGE" "$@"; }
fi

echo "==> Building $IMAGE"
if [ "$ENGINE" = "buildah" ]; then
  buildah bud --layers --format docker -t "$IMAGE" .
else
  "$ENGINE" build -t "$IMAGE" .
fi

echo "==> NFR-002: container runs as a non-root user"
uid="$(run_in_image id -u)"
[ "$uid" != "0" ] || { echo "FAIL: container runs as root"; exit 1; }
echo "ok (uid $uid)"

echo "==> FR-002 / NFR-002: seed images can be built without root or mounts"
run_in_image sh -euc '
  cd /tmp && mkdir seed
  printf "#cloud-config\n" > seed/user-data
  printf "instance-id: iid-smoke\n" > seed/meta-data
  xorriso -as mkisofs -quiet -o seed.iso -V cidata -J -R seed 2>/dev/null
  truncate -s 2M seed.img
  mkfs.vfat -n CIDATA seed.img >/dev/null
  mcopy -i seed.img seed/user-data seed/meta-data ::/
  qemu-img convert -f raw -O qcow2 seed.img seed.qcow2
  qemu-img info seed.qcow2 | grep -q "file format: qcow2"
'
echo "ok"

echo "==> NFR-002 / NFR-005: starting the app"
if [ "$ENGINE" = "buildah" ]; then
  echo "note: buildah cannot enforce a read-only root filesystem; check skipped"
  ctr="$(buildah from -q "$IMAGE")"
  buildah run --network host --env "PORT=$PORT" "$ctr" python -m app >/dev/null 2>&1 &
  cleanup() {
    pkill -f "buildah run --network host --env PORT=$PORT" 2>/dev/null || true
    buildah rm "$ctr" >/dev/null 2>&1 || true
  }
else
  name="cnc-smoke-test-$$"
  "$ENGINE" run -d --name "$name" --read-only --tmpfs /tmp \
    --cap-drop ALL --security-opt no-new-privileges \
    -p "127.0.0.1:$PORT:8000" "$IMAGE" >/dev/null
  cleanup() { "$ENGINE" rm -f "$name" >/dev/null 2>&1 || true; }
fi
trap cleanup EXIT

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
