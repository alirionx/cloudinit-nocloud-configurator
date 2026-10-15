# Deploying cloudinit-nocloud-configurator on Kubernetes

Two ways to deploy (section 8.4 of `docs/requirements.md`):

| | When to use | Datastore |
|---|---|---|
| **Plain manifests** (`deploy/k8s/`) | Quick start with fixed defaults | TinyDB on a PersistentVolumeClaim, 1 replica |
| **Helm chart** (`deploy/helm/cloudinit-nocloud-configurator`) | Everything else | TinyDB, CouchDB installed alongside, or an external CouchDB |

The image is `ghcr.io/alirionx/cloudinit-nocloud-configurator:main`, built on every push to `main`.
The containers run as non-root with a read-only root filesystem and need no special privileges.

## Plain manifests

```sh
kubectl apply -f deploy/k8s/
kubectl -n cloudinit-nocloud-configurator port-forward svc/cloudinit-nocloud-configurator 8080:80
# http://localhost:8080   (API docs: /docs)
```

This creates the namespace `cloudinit-nocloud-configurator`, a Deployment with one replica
(strategy `Recreate`), a Service, a ConfigMap and a 1 GiB PersistentVolumeClaim for the TinyDB
file. The manifests are generated from the Helm chart; do not edit them by hand (see below).

## Helm chart

```sh
helm install cnc deploy/helm/cloudinit-nocloud-configurator -n cloudinit --create-namespace
```

### Datastore variants

**TinyDB (default).** One file on a PersistentVolumeClaim. Only one replica is possible; the chart
rejects `replicaCount > 1` with TinyDB.

**CouchDB installed alongside.** A single-node CouchDB as StatefulSet with its own volume. The
admin password is generated on the first install and kept on every upgrade. Allows several app
replicas.

```sh
helm install cnc deploy/helm/cloudinit-nocloud-configurator -n cloudinit --create-namespace \
  --set couchdb.enabled=true --set replicaCount=2
```

To provide the credentials yourself, create a Secret with the keys `username`, `password` and
`cookieSecret` and set `couchdb.existingSecret=<name>`.

**External CouchDB.** Credentials always come from a Secret (never from values):

```sh
kubectl -n cloudinit create secret generic couchdb-credentials \
  --from-literal=username=cnc --from-literal=password='...'
helm install cnc deploy/helm/cloudinit-nocloud-configurator -n cloudinit \
  --set datastore.backend=couchdb \
  --set datastore.couchdb.url=https://couchdb.example.com:6984 \
  --set datastore.couchdb.existingSecret=couchdb-credentials
```

The app creates its database (`cloudinit` by default) if it does not exist; the user needs the
permission to do so, or create the database beforehand.

### Ingress and access control

The app has no login. Expose it only in a trusted network or behind an authenticating proxy
(R-03). Example with the NGINX ingress controller and Basic Auth:

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    nginx.ingress.kubernetes.io/auth-type: basic
    nginx.ingress.kubernetes.io/auth-secret: cloudinit-basic-auth
    # Seed images are a few MB; allow larger uploads in the file editor.
    nginx.ingress.kubernetes.io/proxy-body-size: 16m
  hosts:
    - host: cloudinit.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: cloudinit-tls
      hosts: [cloudinit.example.com]
```

### Important values

| Value | Default | Description |
|---|---|---|
| `replicaCount` | `1` | App replicas; > 1 only with CouchDB |
| `image.repository` / `image.tag` | `ghcr.io/alirionx/cloudinit-nocloud-configurator` / `main` | |
| `datastore.backend` | `tinydb` | `tinydb` or `couchdb` (external) |
| `datastore.tinydb.persistence.*` | enabled, 1Gi | PVC for the TinyDB file (`existingClaim` possible) |
| `datastore.couchdb.url` / `.existingSecret` | – | External CouchDB |
| `couchdb.enabled` | `false` | CouchDB installed alongside |
| `couchdb.persistence.size` | `2Gi` | Volume of the bundled CouchDB |
| `ingress.*` | disabled | Ingress with class, annotations, hosts, TLS |
| `resources`, `tmpSizeLimit` | 128Mi–512Mi, 512Mi | Seed images are built in `/tmp` per request |
| `podSecurityContext`, `securityContext` | non-root, read-only root FS | |
| `commonLabels`, `podLabels`, `podAnnotations` | – | |

See `values.yaml` for all options.

## Maintaining the manifests

The manifests in `deploy/k8s/` are rendered from the chart with default values:

```sh
deploy/generate-manifests.sh          # after every chart change; commit the result
deploy/generate-manifests.sh --check  # CI: fails if they are outdated
```

## Testing

`scripts/kind-test.sh` installs all variants in a throwaway [kind](https://kind.sigs.k8s.io)
cluster and checks persistence, the stable generated password, the security context and the
TinyDB replica limit.
