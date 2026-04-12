
# Infra for testing

infra-test-up:
	docker compose up -f docker-compose.test.yaml -d

infra-test-down:
	docker compose stop -f docker-compose.test.yaml


# Local run full project (backend + frontend + worker)

run:
	docker compose up