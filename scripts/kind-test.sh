#!/usr/bin/env bash
# Deployment test (DEP-001 to DEP-006) in a throwaway kind cluster.
#
#   scripts/kind-test.sh
#
# Scenarios:
#   1. Plain manifests (deploy/k8s): TinyDB on a PVC; data survives a pod restart.
#   2. Helm chart with CouchDB installed alongside and 2 app replicas; the generated
#      password survives `helm upgrade`, CouchDB data survives a pod restart.
#   3. Helm chart with an external CouchDB (existingSecret).
#   4. TinyDB with 2 replicas is rejected.
#
# Requires: kind, kubectl, helm, docker, curl. The image is pulled from ghcr.io unless
# IMAGE_REPOSITORY / IMAGE_TAG are set; set LOAD_LOCAL_IMAGE=1 to load a local image into kind.
# The cluster is deleted at the end unless KEEP_CLUSTER=1.
set -euo pipefail

cd "$(dirname "$0")/.."
CLUSTER="${CLUSTER:-cnc-test}"
CHART=deploy/helm/cloudinit-nocloud-configurator
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-ghcr.io/alirionx/cloudinit-nocloud-configurator}"
IMAGE_TAG="${IMAGE_TAG:-main}"
PF_PID=""

log() { echo "==> $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

cleanup() {
  [ -n "$PF_PID" ] && kill "$PF_PID" 2>/dev/null || true
  if [ "${KEEP_CLUSTER:-0}" != 1 ]; then kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

# port_forward <namespace> <service> <local-port>
port_forward() {
  [ -n "$PF_PID" ] && kill "$PF_PID" 2>/dev/null || true
  kubectl -n "$1" port-forward "svc/$2" "$3:80" >/dev/null 2>&1 &
  PF_PID=$!
  for _ in $(seq 1 30); do curl -sf "http://127.0.0.1:$3/readyz" >/dev/null && return 0; sleep 1; done
  fail "port-forward to $1/$2 not ready"
}

# create_config <port> <name> -> prints the ID
create_config() {
  curl -sf -X POST "http://127.0.0.1:$1/api/configurations" -H 'content-type: application/json' \
    -d "{\"name\":\"$2\",\"basics\":{\"hostname\":\"k8s-test\"}}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'
}

# assert_config <port> <id>: the configuration exists and an image can be built
assert_config() {
  curl -sf "http://127.0.0.1:$1/api/configurations/$2" >/dev/null || fail "configuration $2 missing"
  curl -sf -o /dev/null "http://127.0.0.1:$1/api/configurations/$2/image?format=iso" || fail "image download"
}

# assert_hardened <namespace> <pod-selector> <container>
assert_hardened() {
  local pod uid
  pod="$(kubectl -n "$1" get pod -l "$2" -o jsonpath='{.items[0].metadata.name}')"
  uid="$(kubectl -n "$1" exec "$pod" -c "$3" -- id -u)"
  [ "$uid" != 0 ] || fail "$3 runs as root"
  if kubectl -n "$1" exec "$pod" -c "$3" -- sh -c 'touch /probe-ro' 2>/dev/null; then
    fail "$3 root filesystem is writable"
  fi
  echo "    $3: uid $uid, read-only root filesystem"
}

log "Creating kind cluster $CLUSTER"
kind create cluster --name "$CLUSTER" --wait 120s >/dev/null
if [ "${LOAD_LOCAL_IMAGE:-0}" = 1 ]; then
  kind load docker-image "$IMAGE_REPOSITORY:$IMAGE_TAG" --name "$CLUSTER" >/dev/null
fi
IMAGE_SET=(--set "image.repository=$IMAGE_REPOSITORY" --set "image.tag=$IMAGE_TAG")
[ "${LOAD_LOCAL_IMAGE:-0}" = 1 ] && IMAGE_SET+=(--set image.pullPolicy=IfNotPresent)

# --- 1. Plain manifests ---
log "1. Plain manifests (TinyDB on PVC)"
NS=cloudinit-nocloud-configurator
if [ "$IMAGE_REPOSITORY:$IMAGE_TAG" = "ghcr.io/alirionx/cloudinit-nocloud-configurator:main" ]; then
  kubectl apply -f deploy/k8s/ >/dev/null
else
  helm template "$NS" "$CHART" --namespace "$NS" --set namespace.create=true "${IMAGE_SET[@]}" \
    | kubectl apply -f - >/dev/null
fi
kubectl -n "$NS" rollout status deploy/"$NS" --timeout=180s >/dev/null
port_forward "$NS" "$NS" 18081
id="$(create_config 18081 manifests)"
assert_hardened "$NS" app.kubernetes.io/component=app app
kubectl -n "$NS" delete pod -l app.kubernetes.io/component=app --wait >/dev/null
kubectl -n "$NS" rollout status deploy/"$NS" --timeout=180s >/dev/null
port_forward "$NS" "$NS" 18081
assert_config 18081 "$id"
echo "    ok: data survived the pod restart (PVC), image download works"
kubectl delete namespace "$NS" --wait >/dev/null

# --- 2. Helm chart with CouchDB installed alongside ---
log "2. Helm chart: CouchDB installed alongside, 2 app replicas"
NS=cnc-couch
helm install cnc "$CHART" -n "$NS" --create-namespace --set couchdb.enabled=true --set replicaCount=2 \
  "${IMAGE_SET[@]}" --wait --timeout 5m >/dev/null
[ "$(kubectl -n "$NS" get deploy cnc-cloudinit-nocloud-configurator -o jsonpath='{.status.readyReplicas}')" = 2 ] \
  || fail "expected 2 ready replicas"
port_forward "$NS" cnc-cloudinit-nocloud-configurator 18082
id="$(create_config 18082 couchdb)"
assert_hardened "$NS" app.kubernetes.io/component=couchdb couchdb
password_before="$(kubectl -n "$NS" get secret cnc-cloudinit-nocloud-configurator-couchdb -o jsonpath='{.data.password}')"
helm upgrade cnc "$CHART" -n "$NS" --reuse-values --set logLevel=debug --wait --timeout 5m >/dev/null
password_after="$(kubectl -n "$NS" get secret cnc-cloudinit-nocloud-configurator-couchdb -o jsonpath='{.data.password}')"
[ "$password_before" = "$password_after" ] || fail "generated password changed on upgrade"
echo "    ok: generated password stable across helm upgrade"
kubectl -n "$NS" delete pod cnc-cloudinit-nocloud-configurator-couchdb-0 --wait >/dev/null
kubectl -n "$NS" rollout status statefulset/cnc-cloudinit-nocloud-configurator-couchdb --timeout=180s >/dev/null
kubectl -n "$NS" rollout status deploy/cnc-cloudinit-nocloud-configurator --timeout=180s >/dev/null
port_forward "$NS" cnc-cloudinit-nocloud-configurator 18082
for _ in $(seq 1 30); do curl -sf http://127.0.0.1:18082/readyz >/dev/null && break; sleep 2; done
assert_config 18082 "$id"
echo "    ok: CouchDB data survived the pod restart, image download works"

# --- 3. External CouchDB (reuses the CouchDB of scenario 2) ---
log "3. Helm chart: external CouchDB via existingSecret"
NS_EXT=cnc-external
kubectl create namespace "$NS_EXT" >/dev/null
kubectl -n "$NS_EXT" create secret generic couchdb-credentials \
  --from-literal=username=admin \
  --from-literal=password="$(echo "$password_after" | base64 -d)" >/dev/null
helm install ext "$CHART" -n "$NS_EXT" --set datastore.backend=couchdb \
  --set datastore.couchdb.url="http://cnc-cloudinit-nocloud-configurator-couchdb.$NS.svc:5984" \
  --set datastore.couchdb.database=external \
  --set datastore.couchdb.existingSecret=couchdb-credentials --set replicaCount=2 \
  "${IMAGE_SET[@]}" --wait --timeout 5m >/dev/null
port_forward "$NS_EXT" ext-cloudinit-nocloud-configurator 18083
id="$(create_config 18083 external)"
assert_config 18083 "$id"
echo "    ok: external CouchDB (database 'external' created by the app)"

# --- 4. Validation ---
log "4. TinyDB with 2 replicas is rejected"
if helm template x "$CHART" --set replicaCount=2 >/dev/null 2>&1; then
  fail "replicaCount=2 with TinyDB was accepted"
fi
echo "    ok: rejected"

echo "All deployment tests passed."
