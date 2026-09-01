ENVFILE ?= .env.example
COMPOSE = docker compose -f docker-compose.yml
COMPOSE_OBS = docker compose -f docker-compose.yml -f docker-compose.observability.yml

.PHONY: help clear-infra start-infra backend-lint backend-test-full backend-test-unit \
        backend-test-integration backend-format frontend-test run-app migrate observability-up \
        observability-down observability-logs check-rules load-test smoke-test

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-26s\033[0m %s\n", $$1, $$2}'

clear-infra:
	docker rm -f postgres || true
	docker volume rm postgres_data || true
	docker rm -f redis || true

start-infra: ## Start Postgres and Redis only
	docker compose --env-file $(ENVFILE) up -d postgres redis

# BACKEND

backend-lint: ## Lint the backend
	cd backend && uv run ruff check src/ tests/

# `ruff format --check` is not part of the CI gate yet: the existing codebase
# predates the formatter, and reformatting 32 files belongs in its own commit
# rather than hidden inside an unrelated change. Run this deliberately:
backend-format: ## Reformat the backend with ruff (one-off, review the diff)
	cd backend && uv run ruff format src/ tests/

backend-test-full: clear-infra start-infra
	cd backend && uv run --env-file ../$(ENVFILE) pytest

backend-test-unit: clear-infra start-infra
	cd backend && uv run --env-file ../$(ENVFILE) pytest tests/unit

backend-test-integration: clear-infra start-infra
	cd backend && uv run --env-file ../$(ENVFILE) pytest tests/integration

# FRONTEND

frontend-test:
	cd frontend && npm run test

# APP

migrate: ## Apply database migrations as a separate deploy step
	$(COMPOSE) --env-file $(ENVFILE) run --rm \
		-e RUN_MIGRATIONS_ON_STARTUP=false \
		backend uv run python -m alembic upgrade head

run-app: clear-infra start-infra ## Run the application stack
	ENVFILE=$(ENVFILE) $(COMPOSE) --env-file $(ENVFILE) up

# OBSERVABILITY

observability-up: ## Run app + Prometheus/Grafana/Loki/Alertmanager
	ENVFILE=$(ENVFILE) GIT_COMMIT=$$(git rev-parse --short HEAD) \
		$(COMPOSE_OBS) --env-file $(ENVFILE) up -d --build
	@echo ""
	@echo "  Grafana       http://localhost:3001  (admin/admin)"
	@echo "  Prometheus    http://localhost:9090"
	@echo "  Alertmanager  http://localhost:9093"
	@echo "  App           http://localhost"
	@echo ""

observability-down: ## Stop everything, keep the data volumes
	$(COMPOSE_OBS) down

observability-logs:
	$(COMPOSE_OBS) logs -f prometheus grafana promtail

check-rules: ## Validate the Prometheus rule files before shipping them
	docker run --rm -v "$(CURDIR)/observability/prometheus:/work" \
		prom/prometheus:v3.1.0 promtool check rules /work/rules/slo.yml /work/rules/alerts.yml

# TESTING THE SYSTEM, NOT THE CODE

smoke-test: ## Post-deploy verification: probes plus one real user flow
	./scripts/smoke-test.sh

load-test: ## k6 load test against the local stack
	docker run --rm -i --network host -v "$(CURDIR)/load:/scripts" \
		grafana/k6:latest run /scripts/k6-baseline.js
