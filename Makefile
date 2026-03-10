# CI/CD Pipeline Health Dashboard — Makefile
# Kubernetes/Minikube operations

NS = cicd-dashboard

.PHONY: help setup build deploy status logs health sync restart clean port-forward stop-forward

# Default target
help:
	@echo ""
	@echo "CI/CD Pipeline Health Dashboard"
	@echo "================================"
	@echo "  setup          - Full one-command setup (start minikube + deploy all)"
	@echo "  build          - Build Docker images inside Minikube daemon"
	@echo "  deploy         - Apply all Kubernetes manifests"
	@echo "  status         - Show pod, service, and ingress status"
	@echo "  logs           - Tail logs for all pods"
	@echo "  logs-backend   - Tail backend pod logs"
	@echo "  logs-frontend  - Tail frontend pod logs"
	@echo "  health         - Check application health endpoint"
	@echo "  sync           - Trigger manual pipeline data sync"
	@echo "  restart        - Rolling restart of backend and frontend"
	@echo "  port-forward   - Expose dashboard on localhost:8080 (for WSL/remote)"
	@echo "  stop-forward   - Stop port-forwarding"
	@echo "  backup-db      - Dump PostgreSQL database to a local SQL file"
	@echo "  clean          - Delete all Kubernetes resources (keeps Minikube)"
	@echo "  clean-all      - Delete all resources AND stop Minikube"
	@echo ""

# Full one-command setup
setup:
	@echo "Running full Minikube setup..."
	./minikube-setup.sh

# Build Docker images inside Minikube's daemon
build:
	@echo "Building images inside Minikube daemon..."
	eval $$(minikube docker-env) && \
	  docker build -t cicd-backend:latest ./backend/ && \
	  docker build -t cicd-frontend:latest ./frontend/
	@echo "Build complete."

# Apply all K8s manifests
deploy:
	@echo "Applying Kubernetes manifests..."
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/networkpolicy.yaml
	kubectl apply -f k8s/postgres/
	kubectl apply -f k8s/backend/
	kubectl apply -f k8s/frontend/
	kubectl apply -f k8s/ingress.yaml
	@echo "Deploy complete. Run 'make status' to check pods."

# Show cluster status
status:
	@echo "\n--- Pods ---"
	kubectl get pods -n $(NS)
	@echo "\n--- Services ---"
	kubectl get svc -n $(NS)
	@echo "\n--- Ingress ---"
	kubectl get ingress -n $(NS)

# Tail logs for all pods
logs:
	kubectl logs -n $(NS) -l app=backend --tail=50 -f &
	kubectl logs -n $(NS) -l app=frontend --tail=20 -f

# Tail backend logs only
logs-backend:
	kubectl logs -n $(NS) -l app=backend --tail=100 -f

# Tail frontend logs only
logs-frontend:
	kubectl logs -n $(NS) -l app=frontend --tail=50 -f

# Health check
health:
	@MINIKUBE_IP=$$(minikube ip); \
	curl -s "http://$$MINIKUBE_IP/api/health" -H "Host: dashboard.local" | python3 -m json.tool

# Manual sync
sync:
	@MINIKUBE_IP=$$(minikube ip); \
	curl -s -X POST "http://$$MINIKUBE_IP/api/pipelines/sync" -H "Host: dashboard.local" | python3 -m json.tool

# Rolling restart
restart:
	kubectl rollout restart deployment/backend deployment/frontend -n $(NS)
	kubectl rollout status deployment/backend -n $(NS)
	kubectl rollout status deployment/frontend -n $(NS)

# Expose via port-forward (WSL / remote access)
port-forward:
	@echo "Forwarding http://dashboard.local:8080 → ingress:80"
	@pkill -f "kubectl port-forward.*ingress-nginx" 2>/dev/null || true
	kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80 --address 0.0.0.0 &
	@echo "Dashboard available at: http://dashboard.local:8080"

# Stop port-forward
stop-forward:
	@pkill -f "kubectl port-forward.*ingress-nginx" 2>/dev/null && echo "Port-forward stopped" || echo "No port-forward running"

# Dump PostgreSQL database
backup-db:
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	kubectl exec -n $(NS) postgres-0 -- pg_dump -U root cicd_dashboard > backup_$$TIMESTAMP.sql && \
	echo "Backup saved to backup_$$TIMESTAMP.sql"

# Delete all K8s resources for this project
clean:
	@echo "Deleting all resources in namespace $(NS)..."
	kubectl delete namespace $(NS) --ignore-not-found
	@echo "Done."

# Stop everything including Minikube
clean-all: clean
	@echo "Stopping Minikube..."
	minikube stop
