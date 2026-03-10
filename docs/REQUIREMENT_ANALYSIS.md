# Requirement Analysis — CI/CD Pipeline Health Dashboard

## 1. Problem Statement

Modern engineering teams run many CI/CD pipelines across multiple repositories and workflows. Without a centralised observability layer, teams are blind to:
- Which pipelines are failing and how often
- Whether build times are degrading over time
- The current health of the overall delivery system

This project builds a **CI/CD Pipeline Health Dashboard** that addresses all of these pain points by aggregating GitHub Actions data, computing key metrics, and surfacing them through a clean UI — with email alerts on failure.

---

## 2. Key Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Pipeline data collection** | Poll GitHub Actions API every 5 minutes to collect workflow run data (status, conclusion, duration, branch, actor, commit) |
| 2 | **Success / failure rate** | Aggregate success and failure counts over configurable time windows (1h, 24h, 7d, 30d) |
| 3 | **Average build time** | Calculate mean, min, and max build durations per workflow and overall |
| 4 | **Last build status** | Show most recent run with commit message, actor, branch, and conclusion |
| 5 | **Email alerts** | Send email notification when a pipeline run fails during sync (optional — requires SMTP configuration) |
| 6 | **Pipeline list view** | Table of all recent runs with status, workflow name, branch, duration |
| 7 | **Per-workflow breakdown** | Metrics split by workflow name (CI Pipeline, Deploy, Health Check, etc.) |
| 8 | **Manual sync trigger** | `POST /api/pipelines/sync` to force an immediate data refresh |
| 9 | **Health endpoint** | `/api/health` reports DB and GitHub API connectivity status |
| 10 | **Kubernetes deployment** | All components containerised and deployed on Minikube with full security primitives |

---

## 3. Stakeholders & Use Cases

| Stakeholder | Use Case |
|-------------|----------|
| Developer | See if the last commit broke CI before reviewing a PR |
| Engineering Lead | Monitor team-wide pipeline health and failure trends |
| DevOps Engineer | Get alerted immediately when a deployment pipeline fails |
| QA Engineer | Track test pipeline pass rates over time |

---

## 4. Functional Requirements

### FR-1: Data Collection
- System shall poll GitHub Actions Workflow Runs API (`GET /repos/{owner}/{repo}/actions/runs`)
- Polling interval: configurable (default 5 minutes)
- Data stored: `github_run_id`, `workflow_name`, `status`, `conclusion`, `started_at`, `completed_at`, `duration`, `branch`, `commit_sha`, `commit_message`, `actor`
- No duplicate storage (unique constraint on `github_run_id`)

### FR-2: Metrics Computation
- System shall compute for any given time period (1h / 24h / 7d / 30d):
  - Total executions
  - Success count, failure count, success rate (%)
  - Average, min, max build duration (seconds)
  - Per-workflow breakdown of all above

### FR-3: Alerting
- System supports email notification when a pipeline run with `conclusion = failure` is detected during sync
- Email alerting is **optional** — enabled only when `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `ALERT_EMAIL_TO` are configured
- When disabled, failure events are still logged in the `alerts` table with `status = disabled`
- Email must include: workflow name, branch, commit message, actor, run URL
- Alert status is reported via `/api/health` → `"email": "enabled" | "disabled"`

### FR-4: Frontend UI
- Display key metric cards: success rate, total runs, avg build time, last build status
- Chart showing success vs failure over time (Chart.js bar/doughnut)
- Table of latest pipeline runs (sortable by date)
- Auto-refreshes every 30 seconds

### FR-5: API
- RESTful JSON API on `/api/*`
- Interactive Swagger docs at `/api/docs`
- CORS configured for frontend origin

---

## 5. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Security** | No credentials in code or committed YAML; K8s Secrets only |
| **Security** | Non-root containers, read-only filesystem, dropped Linux capabilities |
| **Security** | NetworkPolicy: default-deny with explicit allow rules |
| **Reliability** | Liveness + Readiness probes on all pods |
| **Reliability** | PostgreSQL StatefulSet with PVC — data persists across pod restarts |
| **Performance** | Metrics responses cached (5-minute TTL) in `metrics_cache` table |
| **Scalability** | Stateless backend — horizontally scalable (replicas: increase deployment count) |
| **Observability** | Structured JSON-like logs via uvicorn; `/api/health` for monitoring |
| **Portability** | Docker images built inside Minikube — no external registry needed |

---

## 6. Technology Choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Backend** | Python 3.11 + FastAPI | Async-native, automatic OpenAPI docs, excellent type safety via Pydantic |
| **ORM** | SQLAlchemy 2.0 | Industry-standard Python ORM, supports async sessions |
| **HTTP client** | httpx | Async HTTP client for GitHub API calls |
| **Database** | PostgreSQL 15 | ACID compliant, excellent JSON support, views for analytics |
| **Frontend** | Static HTML + Chart.js | Zero build step, fast, no Node.js toolchain dependency |
| **Web server** | nginx-unprivileged | Runs as non-root (UID 101), required for K8s security context |
| **Container runtime** | Docker + Minikube | Local Kubernetes cluster without cloud dependency |
| **Orchestration** | Kubernetes (Minikube) | Real-world K8s primitives: Secrets, NetworkPolicy, StatefulSet, Ingress |
| **Ingress** | nginx-ingress-controller | Standard K8s ingress with host-based routing |
| **Email** | Python smtplib (SMTP) | Standard library, no extra dependencies, works with any SMTP relay; auto-disables if not configured |

---

## 7. APIs / External Integrations Required

| API | Endpoint | Usage |
|-----|----------|-------|
| GitHub Actions | `GET /repos/{owner}/{repo}/actions/runs` | Fetch workflow run list |
| GitHub Actions | `GET /repos/{owner}/{repo}/actions/runs/{run_id}` | Fetch individual run details |
| GitHub API (auth check) | `GET /api.github.com/user` | Validate token in health check |
| SMTP Server | Port 587 (TLS) | Send failure alert emails (optional — only used when SMTP vars are set) |

---

## 8. Assumptions

1. The monitored GitHub repository is public or the PAT has `repo` read scope.
2. Email alerting uses an SMTP relay (e.g. Gmail with app password) — configurable via `.env`.
3. Minikube is running on the same machine as the browser (or WSL with port-forward for Windows).
4. A single repository is monitored (multi-repo support is a future enhancement).
5. The dashboard is internal — no authentication layer is required for this KRA submission.
