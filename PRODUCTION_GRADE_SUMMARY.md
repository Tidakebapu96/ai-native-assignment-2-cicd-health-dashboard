# Production-Grade Summary

This document outlines the security primitives, reliability patterns, and operational practices applied to this Kubernetes deployment.

---

## Security Primitives

### Container Security

| Control | Configuration |
|---------|--------------|
| Non-root user | `runAsNonRoot: true` + `runAsUser: 1000` (backend), `101` (frontend) |
| Read-only filesystem | `readOnlyRootFilesystem: true` on all containers |
| Privilege escalation | `allowPrivilegeEscalation: false` |
| Linux capabilities | `capabilities: drop: [ALL]` |
| Seccomp profile | `seccompProfile: type: RuntimeDefault` |

### Secrets Management

- All credentials stored as Kubernetes Secrets (base64-encoded, etcd-backed)
- Secrets created **imperatively** — no YAML with secret values committed to git
- `.env` is excluded from git via `.gitignore`
- `env.example` contains only placeholder values

```bash
# Secrets created at deploy time:
kubectl create secret generic app-secret -n cicd-dashboard \
  --from-literal=GITHUB_TOKEN=... \
  --from-literal=POSTGRES_USER=... \
  --from-literal=POSTGRES_PASSWORD=...

kubectl create secret generic postgres-secret -n cicd-dashboard \
  --from-literal=POSTGRES_USER=... \
  --from-literal=POSTGRES_PASSWORD=...
```

### Network Policies

Default-deny namespace isolation with explicit allow rules:

```
Internet ──► Ingress Controller ──► frontend (port 8080)
                                └──► backend  (port 8000)
                                         └──► postgres (port 5432)
```

- Frontend can only receive traffic from the ingress controller
- Backend can only receive from ingress; can only reach postgres and GitHub API
- Postgres can only receive from backend
- All other ingress/egress blocked

### Image Security

- Base images: `python:3.11-slim` (backend), `nginxinc/nginx-unprivileged:alpine` (frontend), `postgres:15` (DB)
- `nginx-unprivileged` used to avoid root requirement for nginx cache dirs
- `imagePullPolicy: Never` — images built locally, no external registry exposure

---

## Reliability Patterns

### Health Probes (all pods)

```yaml
livenessProbe:
  httpGet: { path: /api/health, port: 8000 }
  initialDelaySeconds: 30
  periodSeconds: 30

readinessProbe:
  httpGet: { path: /api/health, port: 8000 }
  initialDelaySeconds: 10
  periodSeconds: 10
```

### Resource Limits

| Pod | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-----|-------------|-----------|----------------|--------------|
| backend | 100m | 500m | 256Mi | 512Mi |
| frontend | 10m | 100m | 32Mi | 64Mi |
| postgres | 100m | 500m | 256Mi | 512Mi |

### Rolling Updates

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0   # Zero downtime deployments
```

### Data Persistence

- PostgreSQL uses a `StatefulSet` for stable pod identity (`postgres-0`)
- `PersistentVolumeClaim` (2Gi) ensures data survives pod restarts
- StatefulSet guarantees ordered, graceful scaling

---

## Operational Runbook

### Check overall health
```bash
make health
# Expected: {"status": "healthy", "database": "healthy", "github": "healthy"}
```

### Rolling restart (zero downtime)
```bash
make restart
```

### Trigger manual data sync
```bash
make sync
```

### View logs
```bash
make logs-backend    # Backend API + sync logs
make logs-frontend   # Nginx access logs
```

### Backup database
```bash
make backup-db
# Creates backup_YYYYMMDD_HHMMSS.sql in project root
```

### Add /etc/hosts entry (Linux)
```bash
echo "$(minikube ip) dashboard.local" | sudo tee -a /etc/hosts
```

### Rebuild after Minikube restart
```bash
minikube start
eval $(minikube docker-env)
docker build -t cicd-backend:latest ./backend/
docker build -t cicd-frontend:latest ./frontend/
make restart
```

---

## Kubernetes Resources Summary

```
Namespace:    cicd-dashboard
Deployments:  backend (1 replica), frontend (1 replica)
StatefulSet:  postgres (1 replica)
Services:     backend-service (ClusterIP:8000)
              frontend-service (ClusterIP:8080)
              postgres-service (ClusterIP:5432)
Ingress:      cicd-ingress (dashboard.local → nginx-ingress-controller)
Secrets:      app-secret, postgres-secret
ConfigMap:    app-config
NetworkPolicy: deny-all-default, allow-backend-to-postgres,
               allow-ingress-to-backend, allow-ingress-to-frontend
PVC:          postgres-pvc (2Gi)
```

---

## Known Constraints (Minikube)

| Constraint | Reason | Workaround |
|-----------|--------|------------|
| `imagePullPolicy: Never` | No image registry | Build inside Minikube daemon (`eval $(minikube docker-env)`) |
| No `configuration-snippet` in Ingress | Disabled by Minikube's ingress controller | Use standard annotations only |
| PVC not wiped on delete | Minikube hostpath provisioner reuses paths | `minikube ssh "sudo rm -rf /tmp/hostpath-provisioner/cicd-dashboard/postgres-pvc"` |
| WSL port-forward needed | Windows browser can't reach Minikube IP directly | `make port-forward` + Windows hosts file entry |
