#!/usr/bin/env bash
# =============================================================================
# minikube-setup.sh — CI/CD Pipeline Health Dashboard on Minikube
#
# Usage:
#   chmod +x minikube-setup.sh
#   ./minikube-setup.sh
#
# Prerequisites:  minikube, kubectl, docker
# =============================================================================

set -euo pipefail

# ── Colour helpers ─────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
header()  { echo -e "\n${BOLD}${CYAN}══════════════════════════════════════════${NC}"; \
            echo -e "${BOLD}${CYAN}  $*${NC}"; \
            echo -e "${BOLD}${CYAN}══════════════════════════════════════════${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
K8S_DIR="${SCRIPT_DIR}/k8s"
MINIKUBE_MEMORY="2200"   # MB
MINIKUBE_CPUS="2"
DASHBOARD_HOST="dashboard.local"

# ── Prerequisite checks ────────────────────────────────────────────────────
header "Step 1 — Checking prerequisites"

for cmd in minikube kubectl docker; do
  if ! command -v "$cmd" &>/dev/null; then
    error "$cmd is not installed. Please install it first."
  fi
  success "$cmd found: $(command -v "$cmd")"
done

# ── Load .env file ─────────────────────────────────────────────────────────
header "Step 2 — Loading configuration"

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "${SCRIPT_DIR}/env.example" ]]; then
    warn ".env not found — copying from env.example"
    cp "${SCRIPT_DIR}/env.example" "$ENV_FILE"
    warn "Please edit .env and fill in GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO, and DB credentials."
    warn "Re-run this script after editing .env"
    exit 0
  else
    error ".env file not found. Copy env.example to .env and fill in the values."
  fi
fi

# Source env (safely, ignoring comments; strip Windows carriage returns)
set -a
# shellcheck disable=SC1090
source <(sed 's/\r//' "$ENV_FILE" | grep -v '^\s*#' | grep '=')
set +a

# Set defaults for DB if not in .env
POSTGRES_DB="${POSTGRES_DB:-cicd_dashboard}"
POSTGRES_USER="${POSTGRES_USER:-cicd_user}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-secure_password_change_me}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
GITHUB_OWNER="${GITHUB_OWNER:-}"
GITHUB_REPO="${GITHUB_REPO:-}"

success "Configuration loaded from .env"

# ── Start Minikube ─────────────────────────────────────────────────────────
header "Step 3 — Starting Minikube"

if minikube status --profile minikube 2>/dev/null | grep -q "Running"; then
  success "Minikube is already running"
else
  info "Starting Minikube with ${MINIKUBE_CPUS} CPUs, ${MINIKUBE_MEMORY}MB RAM …"
  minikube start \
    --driver=docker \
    --cpus="${MINIKUBE_CPUS}" \
    --memory="${MINIKUBE_MEMORY}" \
    --addons=ingress \
    --addons=metrics-server
  success "Minikube started"
fi

# Enable ingress addon if not already enabled
minikube addons enable ingress 2>/dev/null || true
minikube addons enable metrics-server 2>/dev/null || true
success "Addons enabled: ingress, metrics-server"

# ── Point Docker to Minikube's daemon ──────────────────────────────────────
header "Step 4 — Configuring Docker context"

info "Switching Docker context to Minikube's daemon …"
eval "$(minikube docker-env)"
success "Docker is now pointing at Minikube's daemon"

# ── Build Docker images inside Minikube ───────────────────────────────────
header "Step 5 — Building Docker images"

info "Building backend image (cicd-backend:latest) …"
docker build -t cicd-backend:latest "${SCRIPT_DIR}/backend/"
success "Backend image built"

info "Building frontend image (cicd-frontend:latest) …"
docker build -t cicd-frontend:latest "${SCRIPT_DIR}/frontend/"
success "Frontend image built"

# ── Apply Kubernetes manifests ─────────────────────────────────────────────
header "Step 6 — Applying Kubernetes manifests"

# Namespace
kubectl apply -f "${K8S_DIR}/namespace.yaml"
success "Namespace applied"

# Secrets — created imperatively so values never touch yaml files in git
info "Creating Kubernetes Secrets …"
kubectl create secret generic cicd-db-secret \
  --from-literal=POSTGRES_DB="${POSTGRES_DB}" \
  --from-literal=POSTGRES_USER="${POSTGRES_USER}" \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  --namespace=cicd-dashboard \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic cicd-app-secret \
  --from-literal=GITHUB_TOKEN="${GITHUB_TOKEN}" \
  --from-literal=GITHUB_OWNER="${GITHUB_OWNER}" \
  --from-literal=GITHUB_REPO="${GITHUB_REPO}" \
  --namespace=cicd-dashboard \
  --dry-run=client -o yaml | kubectl apply -f -
success "Secrets created/updated"

# ConfigMap
kubectl apply -f "${K8S_DIR}/configmap.yaml"
success "ConfigMap applied"

# Postgres init SQL as a ConfigMap (loaded from file)
kubectl create configmap postgres-init-sql \
  --from-file=init.sql="${SCRIPT_DIR}/backend/init.sql" \
  --namespace=cicd-dashboard \
  --dry-run=client -o yaml | kubectl apply -f -
success "Postgres init SQL ConfigMap applied"

# Postgres
kubectl apply -f "${K8S_DIR}/postgres/pvc.yaml"
kubectl apply -f "${K8S_DIR}/postgres/statefulset.yaml"
kubectl apply -f "${K8S_DIR}/postgres/service.yaml"
success "Postgres manifests applied"

# Backend
kubectl apply -f "${K8S_DIR}/backend/deployment.yaml"
kubectl apply -f "${K8S_DIR}/backend/service.yaml"
success "Backend manifests applied"

# Frontend
kubectl apply -f "${K8S_DIR}/frontend/deployment.yaml"
kubectl apply -f "${K8S_DIR}/frontend/service.yaml"
success "Frontend manifests applied"

# Ingress
kubectl apply -f "${K8S_DIR}/ingress.yaml"
success "Ingress applied"

# NetworkPolicies
kubectl apply -f "${K8S_DIR}/networkpolicy.yaml"
success "NetworkPolicies applied"

# ── Wait for pods to be ready ──────────────────────────────────────────────
header "Step 7 — Waiting for pods to be ready"

info "Waiting for Postgres to be ready (up to 120s) …"
kubectl rollout status statefulset/postgres -n cicd-dashboard --timeout=120s
success "Postgres is ready"

info "Waiting for Backend to be ready (up to 120s) …"
kubectl rollout status deployment/backend -n cicd-dashboard --timeout=120s
success "Backend is ready"

info "Waiting for Frontend to be ready (up to 60s) …"
kubectl rollout status deployment/frontend -n cicd-dashboard --timeout=60s
success "Frontend is ready"

# ── Configure /etc/hosts ───────────────────────────────────────────────────
header "Step 8 — Configuring /etc/hosts"

MINIKUBE_IP="$(minikube ip)"
info "Minikube IP: ${MINIKUBE_IP}"

if grep -q "${DASHBOARD_HOST}" /etc/hosts; then
  info "${DASHBOARD_HOST} already in /etc/hosts, updating …"
  sudo sed -i "s/.*${DASHBOARD_HOST}.*/${MINIKUBE_IP} ${DASHBOARD_HOST}/" /etc/hosts
else
  info "Adding ${DASHBOARD_HOST} → ${MINIKUBE_IP} to /etc/hosts (requires sudo) …"
  echo "${MINIKUBE_IP} ${DASHBOARD_HOST}" | sudo tee -a /etc/hosts > /dev/null
fi
success "/etc/hosts updated: ${MINIKUBE_IP} ${DASHBOARD_HOST}"

# ── Wait for Ingress to be assigned ───────────────────────────────────────
header "Step 9 — Verifying Ingress"

info "Waiting for Ingress controller (up to 90s) …"
for i in $(seq 1 18); do
  INGRESS_IP=$(kubectl get ingress cicd-ingress -n cicd-dashboard \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
  if [[ -n "$INGRESS_IP" ]]; then
    success "Ingress is live at ${INGRESS_IP}"
    break
  fi
  sleep 5
  info "  … still waiting (${i}/18)"
done

# ── Summary ────────────────────────────────────────────────────────────────
header "Setup Complete!"

echo ""
echo -e "  ${GREEN}${BOLD}Dashboard URL:${NC}  http://${DASHBOARD_HOST}"
echo -e "  ${GREEN}${BOLD}API Docs:${NC}       http://${DASHBOARD_HOST}/docs"
echo -e "  ${GREEN}${BOLD}Health check:${NC}   http://${DASHBOARD_HOST}/api/health"
echo ""
echo -e "  ${CYAN}Pod status:${NC}"
kubectl get pods -n cicd-dashboard
echo ""
echo -e "  ${YELLOW}Useful commands:${NC}"
echo "    kubectl get pods -n cicd-dashboard"
echo "    kubectl logs -f deploy/backend -n cicd-dashboard"
echo "    kubectl logs -f deploy/frontend -n cicd-dashboard"
echo "    minikube dashboard"
echo "    minikube stop"
echo ""
echo -e "  ${YELLOW}Tear down:${NC}"
echo "    kubectl delete namespace cicd-dashboard"
echo "    minikube stop"
echo ""
