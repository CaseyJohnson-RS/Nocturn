ENVFILE ?= .env.example

clear-infra:
	docker rm -f postgres || true
	docker volume rm postgres_data || true
	docker rm -f redis || true

start-infra:
	docker compose --env-file $(ENVFILE) up -d postgres redis

# BACKEND

backend-lint:
	cd backend && uv run flake8 src/ tests/

backend-test-full: clear-infra start-infra
	cd backend && uv run --env-file ../$(ENVFILE) pytest

backend-test-unit: clear-infra start-infra
	cd backend && uv run --env-file ../$(ENVFILE) pytest tests/unit

backend-test-integration: clear-infra start-infra
	cd backend && uv run --env-file ../$(ENVFILE) pytest tests/integration

# FRONTEND

frontend-test:
	cd frontend && npm run test