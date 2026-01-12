# Цели для разных окружений
dev-up:
	PG_ENV_FILE=.env.db.example PG_PORT=5432 \
	docker compose -f docker-compose.yaml -p dev up -d


dev-down:
	PG_ENV_FILE=.env.db.example PG_PORT=5432 \
	docker compose -f docker-compose.yaml -p dev down

test-up:
	PG_ENV_FILE=.env.db.example PG_PORT=5433 \
	docker compose -f docker-compose.yaml -p test up -d


test-down:
	PG_ENV_FILE=.env.db.example PG_PORT=5433 \
	docker compose -f docker-compose.yaml -p test down -v


# Справка
help:
	@echo "Доступные цели:"
	@echo "  make dev-up     — запустить dev окружение"
	@echo "  make dev-down   — остановить dev окружение"
	@echo "  make test-up    — запустить test окружение"
	@echo "  make test-down  — остановить test окружение"

.PHONY: dev-up dev-down test-up test-down help