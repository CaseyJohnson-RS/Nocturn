MAKEFLAGS += --silent

ENV_FILE ?= .env.tmp
EXAMPLE_ENV ?= .env.example
UV_CMD = uv run --env-file $(ENV_FILE)
DC_CMD = docker compose --env-file $(ENV_FILE) -f docker-compose.db.yaml

# Создание временного .env.tmp с подменой DB_HOST
.env.tmp: $(EXAMPLE_ENV)
	@echo "Creating temporary env file $(ENV_FILE)..."
	@cp $(EXAMPLE_ENV) $(ENV_FILE)
	@sed -i 's/^DB_HOST=.*/DB_HOST=localhost/' $(ENV_FILE)

# Docker
db-up: .env.tmp
	$(DC_CMD) up -d

db-down: .env.tmp
	$(DC_CMD) down -v

# Alembic
alembic-check: .env.tmp
	$(UV_CMD) alembic check

migrate: .env.tmp
	$(UV_CMD) alembic upgrade head

revision: .env.tmp
ifndef MSG
	$(error MSG is not set. Usage: make revision MSG="your message here")
endif
	$(UV_CMD) alembic revision --autogenerate -m "$(MSG)"

# Run app
run: .env.tmp
	$(UV_CMD) uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Tests
test-unit: .env.tmp
	@echo "Running unit tests..."
	$(UV_CMD) pytest app/services

test-integration: db-down .env.tmp
	@echo "Waiting 2 seconds after db-down..."
	@sleep 2
	@$(MAKE) db-up
	@echo "Waiting 2 seconds for DB to be ready..."
	@sleep 2
	@$(MAKE) migrate
	@sleep 1
	@echo "Running integration tests..."
	$(UV_CMD) pytest app/repositories
	@$(MAKE) db-down

test: test-unit test-integration
