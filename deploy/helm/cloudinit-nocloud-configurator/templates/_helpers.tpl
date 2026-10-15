{{/* Names */}}
{{- define "cnc.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "cnc.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else if contains (include "cnc.name" .) .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name (include "cnc.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "cnc.couchdbName" -}}
{{- printf "%s-couchdb" (include "cnc.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Labels */}}
{{- define "cnc.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/part-of: {{ include "cnc.name" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{- define "cnc.selectorLabels" -}}
app.kubernetes.io/name: {{ include "cnc.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: app
{{- end }}

{{- define "cnc.couchdbSelectorLabels" -}}
app.kubernetes.io/name: {{ include "cnc.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: couchdb
{{- end }}

{{/* Effective datastore: the bundled CouchDB wins over datastore.backend. */}}
{{- define "cnc.backend" -}}
{{- if .Values.couchdb.enabled }}couchdb{{ else }}{{ .Values.datastore.backend }}{{ end }}
{{- end }}

{{/* Secret with the CouchDB credentials used by the app (DEP-004). */}}
{{- define "cnc.couchdbSecretName" -}}
{{- if .Values.couchdb.enabled }}
{{- default (include "cnc.couchdbName" .) .Values.couchdb.existingSecret }}
{{- else }}
{{- .Values.datastore.couchdb.existingSecret }}
{{- end }}
{{- end }}

{{- define "cnc.couchdbUrl" -}}
{{- if .Values.couchdb.enabled }}
{{- printf "http://%s:5984" (include "cnc.couchdbName" .) }}
{{- else }}
{{- .Values.datastore.couchdb.url }}
{{- end }}
{{- end }}

{{/*
Validation with clear error messages (DEP-004, DEP-005). Included by the deployment.
*/}}
{{- define "cnc.validate" -}}
{{- $backend := include "cnc.backend" . }}
{{- if and (eq $backend "tinydb") (gt (int .Values.replicaCount) 1) }}
{{- fail "replicaCount > 1 is not possible with datastore.backend=tinydb: TinyDB supports only one instance (R-02). Use CouchDB (couchdb.enabled=true or datastore.backend=couchdb) for more replicas." }}
{{- end }}
{{- if and (eq $backend "couchdb") (not .Values.couchdb.enabled) }}
{{- if not .Values.datastore.couchdb.url }}
{{- fail "datastore.backend=couchdb needs datastore.couchdb.url (external CouchDB) or couchdb.enabled=true (CouchDB installed alongside)." }}
{{- end }}
{{- if not .Values.datastore.couchdb.existingSecret }}
{{- fail "datastore.backend=couchdb needs datastore.couchdb.existingSecret: a Secret with the CouchDB credentials (keys: username, password). Passwords are never set in values (DEP-004)." }}
{{- end }}
{{- end }}
{{- end }}
