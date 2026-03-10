# Tech Design Document — CI/CD Pipeline Health Dashboard

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                    │
│                 Namespace: cicd-dashboard                │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │           Nginx Ingress Controller               │   │
│  │         Host: dashboard.local → :80              │   │
│  └──────────┬────────────────────┬─────────────────┘   │
│             │ /                  │ /api/*               │
│             ▼                    ▼                       │
│  ┌──────────────────┐  ┌──────────────────────────┐    │
│  │  Frontend Pod    │  │      Backend Pod          │    │
│  │  nginx:unprivil. │  │   FastAPI + uvicorn       │    │
│  │  port: 8080      │  │   port: 8000              │    │
│  │  static HTML     │  │                           │    │
│  │  Chart.js UI     │  │  ┌─────────────────────┐  │    │
│  └──────────────────┘  │  │  Background Sync     │  │    │
│                        │  │  (every 5 min)       │  │    │
│                        │  │  GitHub API → DB     │  │    │
│                        │  │  Email on failure    │  │    │
│                        │  │  (if SMTP enabled)   │  │    │
│                        │  └─────────────────────┘  │    │
│                        └────────────┬──────────────┘    │
│                                     │                    │
│                                     ▼                    │
│                        ┌──────────────────────┐         │
│                        │   PostgreSQL 15       │         │
│                        │   StatefulSet         │         │
│                        │   port: 5432          │         │
│                        │   PVC: 2Gi            │         │
│                        └──────────────────────┘         │
└─────────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
  Windows Browser             GitHub Actions API
  http://dashboard.local:8080  api.github.com
```

**Data Flow:**
1. Backend background task polls GitHub Actions API every 5 minutes
2. New workflow runs are stored in PostgreSQL `pipelines` table
3. If a run has `conclusion = failure` and SMTP is configured, an email alert is sent; otherwise the event is logged in the `alerts` table as `disabled`
4. Frontend fetches `/api/metrics/` and `/api/pipelines/` on load + every 30s
5. Chart.js renders the data — no SSR, pure client-side

---

## 2. API Structure

### Base URL: `http://dashboard.local/api`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/health` | System health check | None |
| GET | `/metrics/` | Aggregated pipeline metrics | None |
| GET | `/pipelines/` | List pipeline runs (paginated) | None |
| POST | `/pipelines/sync` | Trigger manual GitHub sync | None |
| GET | `/docs` | Swagger UI | None |
| GET | `/redoc` | ReDoc UI | None |

---

### `GET /api/health`

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-10T12:00:00Z",
  "version": "1.0.0",
  "uptime": 3600.5,
  "database": "healthy",
  "github": "healthy",
  "slack": "disabled",
  "email": "disabled"
}
```

---

### `GET /api/metrics/?period=24h`

**Query params:** `period` = `1h` | `24h` | `7d` | `30d`

**Response:**
```json
{
  "period": "24h",
  "total_executions": 18,
  "success_count": 14,
  "failure_count": 4,
  "success_rate": 77.78,
  "average_build_time": 231.39,
  "min_build_time": 70,
  "max_build_time": 540,
  "last_execution": {
    "id": 19,
    "github_run_id": 3006,
    "workflow_name": "Health Check & Monitoring",
    "status": "completed",
    "conclusion": "success",
    "branch": "main",
    "commit_sha": "b3c4d5e6f7a2",
    "commit_message": "chore: scheduled health check",
    "actor": "github-actions[bot]",
    "created_at": "2026-03-10T11:17:51Z",
    "duration": 120,
    "html_url": "https://github.com/..."
  },
  "workflows": [
    {
      "name": "CI Pipeline",
      "executions": 7,
      "success_rate": 71.43,
      "average_time": 211.43
    }
  ]
}
```

---

### `GET /api/pipelines/`

**Query params:** `skip` (default 0), `limit` (default 50), `status`, `workflow_name`

**Response:**
```json
[
  {
    "id": 1,
    "github_run_id": 1001,
    "workflow_name": "CI Pipeline",
    "status": "completed",
    "conclusion": "success",
    "branch": "main",
    "commit_sha": "a1b2c3d4e5f6",
    "commit_message": "feat: initial project structure",
    "actor": "Tidakebapu96",
    "started_at": "2026-03-03T12:00:00Z",
    "completed_at": "2026-03-03T12:04:00Z",
    "duration": 240,
    "html_url": "https://github.com/..."
  }
]
```

---

### `POST /api/pipelines/sync`

**Response:**
```json
{
  "success": true,
  "message": "Successfully synced 3 pipeline executions",
  "new_executions": 3,
  "total_executions": 21,
  "sync_time": "2026-03-10T12:00:00Z"
}
```

---

## 3. Database Schema

### Table: `pipelines`

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL PK | Internal ID |
| `github_run_id` | BIGINT UNIQUE | GitHub Actions run ID |
| `workflow_name` | VARCHAR(255) | Workflow display name |
| `status` | VARCHAR(50) | `queued` / `in_progress` / `completed` |
| `conclusion` | VARCHAR(50) | `success` / `failure` / `cancelled` / `skipped` |
| `created_at` | TIMESTAMPTZ | Run creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |
| `started_at` | TIMESTAMPTZ | Execution start time |
| `completed_at` | TIMESTAMPTZ | Execution end time |
| `duration` | INTEGER | Duration in seconds |
| `branch` | VARCHAR(255) | Git branch name |
| `commit_sha` | VARCHAR(40) | Git commit SHA |
| `commit_message` | TEXT | Git commit message |
| `actor` | VARCHAR(255) | GitHub username that triggered the run |
| `html_url` | TEXT | Link to GitHub Actions run page |
| `logs_url` | TEXT | API URL for run logs |

**Indexes:** `status`, `created_at`, `workflow_name`, `created_date` (generated column)

---

### Table: `workflows`

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Internal ID |
| `name` | VARCHAR(255) UNIQUE | Workflow name |
| `description` | TEXT | Human-readable description |
| `is_active` | BOOLEAN | Whether workflow is tracked |
| `created_at` | TIMESTAMPTZ | Record creation time |
| `updated_at` | TIMESTAMPTZ | Last update time |

---

### Table: `alerts`

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Internal ID |
| `pipeline_id` | BIGINT FK → pipelines.id | Associated pipeline run |
| `alert_type` | VARCHAR(50) | `email` |
| `message` | TEXT | Alert message body |
| `sent_at` | TIMESTAMPTZ | When alert was sent |
| `status` | VARCHAR(50) | `sent` / `failed` |

---

### Table: `metrics_cache`

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Internal ID |
| `metric_key` | VARCHAR(255) UNIQUE | Cache key (e.g. `metrics_24h`) |
| `metric_value` | TEXT | Serialised JSON payload |
| `period` | VARCHAR(20) | Time window |
| `calculated_at` | TIMESTAMPTZ | When computed |
| `expires_at` | TIMESTAMPTZ | TTL expiry (5 min) |

---

### Views

| View | Description |
|------|-------------|
| `daily_metrics` | Per-day aggregates for last 30 days |
| `workflow_metrics` | Per-workflow aggregates for last 24h |

---

## 4. UI Layout

```
┌──────────────────────────────────────────────────────────────┐
│  CI/CD Pipeline Health Dashboard          [Last synced: 12s] │
├──────────────┬──────────────┬──────────────┬─────────────────┤
│  Total Runs  │ Success Rate │ Avg Build    │  Last Build      │
│     18       │   77.78%     │   3m 51s     │  ✅ success      │
├──────────────┴──────────────┴──────────────┴─────────────────┤
│                                                              │
│  Success vs Failure [Bar Chart]   │  By Workflow [Doughnut]  │
│  (last 7 days, per workflow)      │  CI / Deploy / Health    │
│                                   │                          │
├───────────────────────────────────┴──────────────────────────┤
│  Recent Pipeline Runs                                        │
│  ┌────────────────┬──────────┬────────┬────────┬───────────┐ │
│  │ Workflow       │ Branch   │ Status │  Time  │  Actor    │ │
│  ├────────────────┼──────────┼────────┼────────┼───────────┤ │
│  │ CI Pipeline    │ main     │ ✅     │  4m    │ user123   │ │
│  │ Deploy Staging │ main     │ ✅     │  6m    │ user123   │ │
│  │ Health Check   │ main     │ ❌     │  1m    │ bot       │ │
│  └────────────────┴──────────┴────────┴────────┴───────────┘ │
│  [Showing 10 of 18]                            [Sync Now]    │
└──────────────────────────────────────────────────────────────┘
```

**UI Components:**
- **Metric Cards** — 4 KPI cards at top (total runs, success rate, avg build time, last build)
- **Bar Chart** — Success vs failure count per workflow (Chart.js)
- **Doughnut Chart** — Proportion of runs by workflow
- **Pipeline Table** — Latest runs with status badge, duration, branch, actor, link to GitHub
- **Period Selector** — Dropdown to switch between 1h / 24h / 7d / 30d
- **Sync Button** — Triggers `POST /api/pipelines/sync` manually
- **Auto-refresh** — Polls `/api/metrics/` and `/api/pipelines/` every 30 seconds

---

## 5. Kubernetes Architecture

### Resources in `cicd-dashboard` namespace

```
Deployments:
  backend   (replicas: 1)  — FastAPI app
  frontend  (replicas: 1)  — nginx static server

StatefulSet:
  postgres  (replicas: 1)  — PostgreSQL 15

Services (ClusterIP):
  backend-service   → port 8000
  frontend-service  → port 8080
  postgres-service  → port 5432

Ingress:
  cicd-ingress → dashboard.local
    /       → frontend-service:8080
    /api/*  → backend-service:8000

Secrets:
  app-secret      — GITHUB_TOKEN, POSTGRES_USER, POSTGRES_PASSWORD
  postgres-secret — POSTGRES_USER, POSTGRES_PASSWORD

ConfigMap:
  app-config      — POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT

NetworkPolicies:
  deny-all-default            — blocks all ingress/egress by default
  allow-ingress-to-backend    — ingress controller → backend:8000
  allow-ingress-to-frontend   — ingress controller → frontend:8080
  allow-backend-to-postgres   — backend → postgres:5432

PVC:
  postgres-pvc  (2Gi, ReadWriteOnce)
```

### Security Context (all pods)

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000          # 101 for frontend (nginx-unprivileged)
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: [ALL]
  seccompProfile:
    type: RuntimeDefault
```

---

## 6. Email Alert Flow

> **Optional feature** — email alerting is disabled by default. To enable, set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `ALERT_EMAIL_TO` in your `.env` and K8s secret. The `/api/health` endpoint reports `"email": "enabled"` or `"email": "disabled"` accordingly.

```
GitHub API sync
    │
    ▼
New run detected with conclusion = "failure"
    │
    ▼
email_service.enabled? (all 4 SMTP vars set)
    │
    ├── YES → send_failure_alert(pipeline)
    │           ├── Connects to SMTP_HOST:SMTP_PORT with STARTTLS
    │           ├── Authenticates with SMTP_USER / SMTP_PASSWORD
    │           ├── Sends HTML email to ALERT_EMAIL_TO
    │           └── Records alert: type="email", status="sent"
    │
    └── NO  → Records alert: type="email", status="disabled" (no-op)
```

**Email content includes:**
- Workflow name and run ID
- Branch and commit message
- Actor (who triggered it)
- Direct link to GitHub Actions run page
- Timestamp

---

## 7. Key Technical Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Async vs sync | Async FastAPI + asyncio background task | Non-blocking GitHub API polling without extra workers |
| Password special chars | `quote_plus()` in DATABASE_URL | `@` in passwords breaks SQLAlchemy URL parsing |
| nginx variant | `nginx-unprivileged` | Standard `nginx:alpine` requires root to create cache dirs — incompatible with K8s `runAsNonRoot` |
| PVC for postgres | StatefulSet + PVC | Ensures stable pod name + data persistence across restarts |
| Metrics caching | `metrics_cache` table | Avoids expensive aggregation queries on every dashboard refresh |
| Image pull policy | `Never` | Builds locally inside Minikube daemon — no registry needed |
| Ingress snippets | Not used | `configuration-snippet` annotation is disabled in Minikube's ingress controller |
