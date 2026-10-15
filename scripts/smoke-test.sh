#!/usr/bin/env sh
# Container smoke test: builds the image and checks NFR-001, NFR-002, NFR-004, NFR-005,
# DS-005 and DS-006 (TinyDB and CouchDB backends).
#
# Container engine: ENGINE=docker|podman|buildah (default: first working one found).
# With buildah, the read-only root filesystem and CouchDB checks are skipped.
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

# api_round_trip <base-url>: create a configuration, render it and download all image formats
# (FR-001, FR-002, FR-003, FR-015).
api_round_trip() {
  id="$(curl -sf -X POST "$1/api/configurations" -H 'content-type: application/json' \
    -d '{"name":"smoke","basics":{"hostname":"smoke-01"}}' | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')"
  [ -n "$id" ] || { echo "FAIL: could not create a configuration"; return 1; }
  curl -sf "$1/api/configurations/$id/files" | grep -q 'local-hostname: smoke-01' \
    || { echo "FAIL: rendered meta-data is wrong"; return 1; }
  for format in iso raw qcow2; do
    curl -sf -D - -o /dev/null "$1/api/configurations/$id/image?format=$format" \
      | grep -qi "content-disposition: attachment" \
      || { echo "FAIL: $format download"; return 1; }
  done
  echo "ok"
}

# wait_for <url>: poll until the URL answers with HTTP 2xx (max. 60 s).
wait_for() {
  for _ in $(seq 1 60); do
    curl -sf "$1" >/dev/null && return 0
    sleep 1
  done
  echo "FAIL: $1 did not become available"
  return 1
}

echo "==> NFR-002 / NFR-005: starting the app (TinyDB)"
if [ "$ENGINE" = "buildah" ]; then
  echo "note: buildah cannot enforce a read-only root filesystem; check skipped"
  ctr="$(buildah from -q "$IMAGE")"
  buildah run --network host --env "PORT=$PORT" "$ctr" python -m app >/dev/null 2>&1 &
  cleanup() {
    pkill -f "buildah run --network host --env PORT=$PORT" 2>/dev/null || true
    buildah rm "$ctr" >/dev/null 2>&1 || true
  }
else
  suffix="cnc-smoke-test-$$"
  cleanup() {
    "$ENGINE" rm -f "$suffix-tinydb" "$suffix-couchdb-app" "$suffix-couchdb" >/dev/null 2>&1 || true
    "$ENGINE" network rm "$suffix" >/dev/null 2>&1 || true
  }
  # Read-only root filesystem; /app/data stands in for the PersistentVolumeClaim (DEP-001).
  "$ENGINE" run -d --name "$suffix-tinydb" --read-only --tmpfs /tmp \
    --tmpfs /app/data:uid=10001,gid=10001 \
    --cap-drop ALL --security-opt no-new-privileges \
    -p "127.0.0.1:$PORT:8000" "$IMAGE" >/dev/null
fi
trap cleanup EXIT

wait_for "http://127.0.0.1:$PORT/healthz"

echo "==> NFR-004 / DS-006: health endpoints"
curl -sf "http://127.0.0.1:$PORT/healthz" && echo
curl -sf "http://127.0.0.1:$PORT/readyz" | tee /dev/stderr | grep -q '"datastore":"ok"'
echo

echo "==> Section 8.1: frontend is served"
curl -sf "http://127.0.0.1:$PORT/" | grep -q '<div id="app">'
echo "ok"

echo "==> FR-001 / FR-015: configuration API (TinyDB)"
api_round_trip "http://127.0.0.1:$PORT"

if [ "$ENGINE" != "buildah" ]; then
  echo "==> DS-005 / DS-006: CouchDB backend"
  app_port=$((PORT + 1))
  "$ENGINE" network create "$suffix" >/dev/null
  "$ENGINE" run -d --name "$suffix-couchdb" --network "$suffix" \
    -e COUCHDB_USER=admin -e COUCHDB_PASSWORD=smoke-test "${COUCHDB_IMAGE:-couchdb:3}" >/dev/null
  "$ENGINE" run -d --name "$suffix-couchdb-app" --network "$suffix" --read-only --tmpfs /tmp \
    --cap-drop ALL --security-opt no-new-privileges \
    -e DATASTORE_BACKEND=couchdb -e "COUCHDB_URL=http://$suffix-couchdb:5984" \
    -e COUCHDB_USER=admin -e COUCHDB_PASSWORD=smoke-test \
    -p "127.0.0.1:$app_port:8000" "$IMAGE" >/dev/null
  # Becomes ready once CouchDB is up and the database has been created.
  wait_for "http://127.0.0.1:$app_port/readyz"
  curl -sf "http://127.0.0.1:$app_port/readyz" | tee /dev/stderr | grep -q '"datastore":"ok"'
  echo
  echo "==> FR-001 / FR-015: configuration API (CouchDB)"
  api_round_trip "http://127.0.0.1:$app_port"
else
  echo "note: CouchDB check needs docker or podman; skipped"
fi

echo "All smoke tests passed."
