MAKEFLAGS += --silent
ENV_FILE ?= .env.tmp
EXAMPLE_ENV ?= .env.example

# Генерация временного .env.tmp с подменой DB_HOST
.env.tmp: $(EXAMPLE_ENV)
	@echo "Creating temporary env file .env.tmp..."
	@cp $(EXAMPLE_ENV) .env.tmp
	@sed -i 's/^DB_HOST=.*/DB_HOST=localhost/' .env.tmp

db-up: .env.tmp
	docker compose --env-file $(ENV_FILE) -f docker-compose.db.yaml up -d

db-down: .env.tmp
	docker compose --env-file $(ENV_FILE) -f docker-compose.db.yaml down -v

alembic-check: .env.tmp
	uv run --env-file $(ENV_FILE) alembic check
	
migrate: .env.tmp
	uv run --env-file $(ENV_FILE) alembic upgrade head

revision: .env.tmp
ifndef MSG
	$(error MSG is not set. Usage: make revision MSG="your message here")
endif
	uv run --env-file $(ENV_FILE) alembic revision --autogenerate -m "$(MSG)"

run: .env.tmp
	uv run --env-file $(ENV_FILE) uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test-unit: .env.tmp
	@echo "Running unit tests..."
	uv run --env-file $(ENV_FILE) pytest app/registration

test-integration: db-down .env.tmp
	@echo "Waiting 3 seconds after db-down..."
	@sleep 3
	@make db-up
	@echo "Waiting 3 seconds for DB to be ready..."
	@sleep 3
	@make migrate
	@sleep 1
	@echo "Running integration tests..."
	uv run --env-file $(ENV_FILE) pytest app/repositories

test: test-unit test-integration
