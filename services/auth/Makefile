ENV_FILE ?= .env.example

db-up:
	docker compose --env-file $(ENV_FILE) -f docker-compose.db.yaml up -d

db-down:
	docker compose --env-file $(ENV_FILE) -f docker-compose.db.yaml down -v

migrate:
	uv run --env-file $(ENV_FILE) alembic upgrade head

revision:
ifndef MSG
	$(error MSG is not set. Usage: make revision MSG="your message here")
endif
	uv run --env-file $(ENV_FILE) alembic revision --autogenerate -m "$(MSG)"

run:
	uv run --env-file $(ENV_FILE) uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


# TODO: unit tests

# TODO: integration tests
