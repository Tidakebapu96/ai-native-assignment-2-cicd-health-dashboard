# CI/CD Pipeline Health Dashboard

A production-grade CI/CD pipeline monitoring dashboard deployed on **Minikube (Kubernetes)**. Tracks GitHub Actions workflow runs, displays real-time metrics, success/failure rates, and build durations via a clean web UI.

---

## Architecture

```
Browser
  │
  ▼
Nginx Ingress Controller (dashboard.local)
  │
  ├─── /          ──► Frontend Pod  (nginxinc/nginx-unprivileged:alpine, port 8080)
  │                   Static HTML + Chart.js dashboard
  │
  └─── /api/*     ──► Backend Pod   (FastAPI + uvicorn, port 8000)
                      │
                      ├── Polls GitHub Actions API every 5 min
                      │
                      └── PostgreSQL StatefulSet  (postgres:15, port 5432)
```

**Kubernetes Namespace:** `cicd-dashboard`

---

## Security Primitives

| Feature | Implementation |
|---------|---------------|
| Non-root containers | `runAsNonRoot: true`, `runAsUser: 1000` (backend), `101` (frontend) |
| Read-only filesystem | `readOnlyRootFilesystem: true` on all containers |
| Dropped capabilities | `drop: [ALL]` — no Linux capabilities granted |
| Secrets management | `kubectl create secret` — never committed to git |
| Network isolation | NetworkPolicy: deny-all ingress/egress by default, explicit allow rules |
| Resource limits | CPU/Memory requests and limits on every pod |
| Health probes | Liveness + Readiness probes on all deployments |
| Ingress TLS-ready | Nginx Ingress with host-based routing |

---

## Prerequisites

- [Minikube](https://minikube.sigs.k8s.io/docs/start/) v1.20+
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Docker](https://docs.docker.com/get-docker/)
- A GitHub Personal Access Token with `repo` scope

---

## Quick Start

### 1. Configure credentials

```bash
cp env.example .env
# Edit .env with your real values:
#   GITHUB_TOKEN  — classic PAT from https://github.com/settings/tokens
#   GITHUB_OWNER  — your GitHub username
#   GITHUB_REPO   — repository to monitor
#   POSTGRES_USER / POSTGRES_PASSWORD
```

### 2. Run setup (one command)

```bash
./minikube-setup.sh
```

This script:
- Starts Minikube with `ingress` and `metrics-server` addons
- Builds Docker images inside Minikube's daemon
- Creates Kubernetes Secrets from your `.env`
- Deploys all manifests (namespace → postgres → backend → frontend → ingress)
- Adds `dashboard.local` to `/etc/hosts`

### 3. Access the dashboard

| URL | Description |
|-----|-------------|
| **http://dashboard.local** | Dashboard UI |
| http://dashboard.local/api/docs | Swagger API docs |
| http://dashboard.local/api/health | Health check |
| http://dashboard.local/api/metrics/?period=24h | Metrics (24h/7d/30d) |
| http://dashboard.local/api/pipelines/ | Pipeline run list |

> **WSL / Windows users:** Run `make port-forward` then access via `http://dashboard.local:8080`  
> Add `127.0.0.1 dashboard.local` to `C:\Windows\System32\drivers\etc\hosts` (as Administrator)

---

## Makefile Commands

```bash
make setup          # Full one-command setup
make build          # Rebuild Docker images
make deploy         # Re-apply all K8s manifests
make status         # Show pods, services, ingress
make logs           # Stream all logs
make logs-backend   # Stream backend logs only
make health         # Hit /api/health endpoint
make sync           # Trigger manual GitHub data sync
make restart        # Rolling restart (zero downtime)
make port-forward   # Expose on localhost:8080 (WSL/remote)
make backup-db      # Dump PostgreSQL to local SQL file
make clean          # Delete all K8s resources
make clean-all      # Delete resources + stop Minikube
```

---

## Project Structure

```
assignment-2/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── api/routes/       # health.py, metrics.py, pipelines.py
│   │   ├── core/             # config.py, database.py
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # github_service.py
│   │   └── main.py
│   ├── Dockerfile
│   ├── init.sql              # DB schema
│   └── requirements.txt
├── frontend/                 # Static dashboard
│   ├── static/index.html     # Chart.js dashboard UI
│   ├── nginx.conf            # Non-root nginx config (port 8080)
│   └── Dockerfile
├── k8s/                      # Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── networkpolicy.yaml
│   ├── ingress.yaml
│   ├── backend/              # deployment.yaml, service.yaml
│   ├── frontend/             # deployment.yaml, service.yaml
│   └── postgres/             # statefulset.yaml, service.yaml, pvc.yaml
├── docs/
│   ├── REQUIREMENT_ANALYSIS.md  # Feature specs and requirements
│   └── TECH_DESIGN.md           # Architecture, API, DB schema
├── minikube-setup.sh         # One-command setup script
├── Makefile                  # kubectl-based dev commands
├── env.example               # Template — copy to .env
└── .gitignore
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | System health (DB + GitHub) |
| GET | `/api/metrics/?period=24h` | Aggregated metrics (24h / 7d / 30d) |
| GET | `/api/pipelines/` | List all pipeline runs |
| POST | `/api/pipelines/sync` | Trigger manual GitHub sync |
| GET | `/api/docs` | Interactive Swagger UI |

---

## Restarting After Minikube Stop

```bash
minikube start
eval $(minikube docker-env)
docker build -t cicd-backend:latest ./backend/
docker build -t cicd-frontend:latest ./frontend/
make restart
```

> Images must be rebuilt because `imagePullPolicy: Never` requires them present in Minikube's Docker daemon.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Minikube v1.38+, Kubernetes 1.32 |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, httpx |
| Database | PostgreSQL 15 (StatefulSet + PVC) |
| Frontend | Static HTML, Chart.js, Nginx (unprivileged) |
| Ingress | nginx-ingress-controller |
| Monitoring | GitHub Actions API polling (5 min interval) |
