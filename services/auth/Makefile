MAKEFLAGS += --silent
ENV_FILE ?= .env.example

db-up:
	docker compose --env-file $(ENV_FILE) -f docker-compose.db.yaml up -d

db-down:
	docker compose --env-file $(ENV_FILE) -f docker-compose.db.yaml down -v

alembic-check:
	uv run --env-file $(ENV_FILE) alembic check
	
migrate:
	uv run --env-file $(ENV_FILE) alembic upgrade head

revision:
ifndef MSG
	$(error MSG is not set. Usage: make revision MSG="your message here")
endif
	uv run --env-file $(ENV_FILE) alembic revision --autogenerate -m "$(MSG)"

run:
	uv run --env-file $(ENV_FILE) uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


test-unit:
	@echo "Running unit tests..."
	uv run --env-file $(ENV_FILE) pytest app/registration

test-integration: db-down
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