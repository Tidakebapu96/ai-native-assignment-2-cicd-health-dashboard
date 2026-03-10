# Project Structure

```
assignment-2/
│
├── backend/                          # FastAPI Python backend
│   ├── Dockerfile                    # Python 3.11-slim, non-root user
│   ├── init.sql                      # PostgreSQL schema (tables + indexes)
│   ├── requirements.txt              # Python dependencies
│   └── app/
│       ├── main.py                   # FastAPI app, lifespan, background sync
│       ├── api/
│       │   └── routes/
│       │       ├── __init__.py
│       │       ├── health.py         # GET /api/health — DB + GitHub status
│       │       ├── metrics.py        # GET /api/metrics/?period=24h|7d|30d
│       │       └── pipelines.py      # GET/POST /api/pipelines/
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py             # Pydantic Settings (env vars, DB URL)
│       │   └── database.py           # SQLAlchemy async engine + session
│       ├── models/
│       │   ├── __init__.py
│       │   └── pipeline.py           # Pipeline, Workflow, Alert ORM models
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── pipeline.py           # Pydantic request/response schemas
│       └── services/
│           ├── __init__.py
│           ├── github_service.py     # GitHub Actions API client (httpx)
│           └── email_service.py      # SMTP email alerting (optional, disabled by default)
│
├── frontend/                         # Static dashboard UI
│   ├── Dockerfile                    # nginxinc/nginx-unprivileged:alpine
│   ├── nginx.conf                    # Non-root nginx config, listens on 8080
│   ├── .dockerignore
│   └── static/
│       └── index.html                # Chart.js dashboard (pipeline metrics UI)
│
├── k8s/                              # Kubernetes manifests
│   ├── namespace.yaml                # Namespace: cicd-dashboard
│   ├── configmap.yaml                # Non-secret app config (DB host, port)
│   ├── networkpolicy.yaml            # Deny-all + explicit allow rules
│   ├── ingress.yaml                  # Nginx Ingress → backend (/api) + frontend
│   ├── secrets-reference.yaml        # Reference doc for required K8s secrets
│   ├── backend/
│   │   ├── deployment.yaml           # Backend deployment (security context, probes)
│   │   └── service.yaml              # ClusterIP service on port 8000
│   ├── frontend/
│   │   ├── deployment.yaml           # Frontend deployment (non-root, port 8080)
│   │   └── service.yaml              # ClusterIP service on port 8080
│   └── postgres/
│       ├── statefulset.yaml          # PostgreSQL 15 StatefulSet
│       ├── service.yaml              # ClusterIP service on port 5432
│       └── pvc.yaml                  # PersistentVolumeClaim (2Gi)
│
├── docs/
│   ├── REQUIREMENT_ANALYSIS.md           # Feature requirements, functional/non-functional specs
│   └── TECH_DESIGN.md                    # Architecture, API reference, DB schema, UI layout
├── minikube-setup.sh                 # One-command setup (minikube + k8s deploy)
├── Makefile                          # kubectl-based dev/ops commands
├── env.example                       # Environment variable template
├── .gitignore                        # Excludes .env, backups, caches
├── README.md                         # Full setup and usage guide
├── PROJECT_STRUCTURE.md              # This file
└── PRODUCTION_GRADE_SUMMARY.md       # Security and production-readiness notes
```

---

## Key Design Decisions

### Backend
- **URL-encoded DB password** — `quote_plus()` in `config.py` handles special characters (e.g. `@`) in PostgreSQL passwords
- **Background sync** — `asyncio` task polls GitHub Actions API every 5 minutes; also triggerable via `POST /api/pipelines/sync`
- **Non-root** — Dockerfile sets `USER 1000`, K8s `securityContext` enforces `runAsNonRoot: true`

### Frontend
- **`nginxinc/nginx-unprivileged`** — Required to run nginx as non-root on port 8080 (standard `nginx:alpine` requires root for `/var/cache/nginx`)
- Single static `index.html` with Chart.js — no build step needed

### Kubernetes
- **`imagePullPolicy: Never`** — images are built directly inside Minikube's Docker daemon, no registry required
- **Secrets** — Created imperatively with `kubectl create secret`, never stored in YAML
- **StatefulSet for Postgres** — Ensures stable pod name (`postgres-0`) and stable PVC binding
- **NetworkPolicy** — Default-deny namespace isolation; only explicit traffic is allowed

### Ingress
- `configuration-snippet` annotation is **disabled** by Minikube's ingress controller by default — not used
- Trailing slash matters for some routes: use `/api/metrics/` not `/api/metrics`
