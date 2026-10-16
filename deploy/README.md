# Deploying cloudinit-nocloud-configurator on Kubernetes

Two ways to deploy (section 8.4 of `docs/requirements.md`):

| | When to use | Datastore |
|---|---|---|
| **Plain manifests** (`deploy/k8s/`) | Quick start with fixed defaults | TinyDB on a PersistentVolumeClaim, 1 replica |
| **Helm chart** (`deploy/helm/cloudinit-nocloud-configurator`) | Everything else | TinyDB, CouchDB installed alongside, or an external CouchDB |

The image is `ghcr.io/alirionx/cloudinit-nocloud-configurator:main`, built on every push to `main`.
The containers run as non-root with a read-only root filesystem and need no special privileges.

## Plain manifests

Two variants, both in the namespace `cloudinit-nocloud-configurator`:

**TinyDB** (`deploy/k8s/tinydb/`): a Deployment with one replica (strategy `Recreate`), a Service,
a ConfigMap and a 1 GiB PersistentVolumeClaim for the TinyDB file.

```sh
kubectl apply -f deploy/k8s/tinydb/
```

**CouchDB** (`deploy/k8s/couchdb/`): a single-node CouchDB StatefulSet with its own volume and
two app replicas. The manifests contain no credentials; create the Secret first:

```sh
kubectl create namespace cloudinit-nocloud-configurator
kubectl -n cloudinit-nocloud-configurator create secret generic cloudinit-nocloud-configurator-couchdb \
  --from-literal=username=admin \
  --from-literal=password="$(openssl rand -hex 24)" \
  --from-literal=cookieSecret="$(openssl rand -hex 24)"
kubectl apply -f deploy/k8s/couchdb/
```

Then open the app:

```sh
kubectl -n cloudinit-nocloud-configurator port-forward svc/cloudinit-nocloud-configurator 8080:80
# http://localhost:8080   (API docs: /docs)
```

The manifests are generated from the Helm chart and labelled `app.kubernetes.io/managed-by: kubectl`;
do not edit them by hand (see below). They cannot be taken over by `helm install` later: to switch
to Helm, delete the namespace (or the resources) and install the chart.

## Helm chart

From a GitHub release (DEP-009), without cloning the repository:

```sh
helm install cnc \
  https://github.com/alirionx/cloudinit-nocloud-configurator/releases/download/chart-v0.1.1/cloudinit-nocloud-configurator-0.1.1.tgz \
  -n cloudinit --create-namespace
```

Released charts use the image tag `main`, i.e. the latest build of the main branch. For a
reproducible installation pin the image: `--set image.tag=sha-<commit>` (R-10).

From the repository:

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

## Releasing the chart

`.github/workflows/chart-release.yml` runs on every push to `main` that changes the chart. If the
`version` in `Chart.yaml` has no release yet, it lints and packages the chart and creates the
GitHub release `chart-v<version>` with the `.tgz` and its SHA-256 checksum. To publish chart
changes, bump `version` in `Chart.yaml` (semantic versioning) in the same commit.

## Maintaining the manifests

The manifests in `deploy/k8s/tinydb/` and `deploy/k8s/couchdb/` are rendered from the chart:

```sh
deploy/generate-manifests.sh          # after every chart change; commit the result
deploy/generate-manifests.sh --check  # CI: fails if they are outdated
```

## Testing

`scripts/kind-test.sh` installs all variants in a throwaway [kind](https://kind.sigs.k8s.io)
cluster and checks persistence, the stable generated password, the security context and the
TinyDB replica limit.
