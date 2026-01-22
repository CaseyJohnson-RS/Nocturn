
run-app:
	docker compose --profile app up --build

run-infra:
	docker compose --profile infra up --build

run-auth:
	docker compose --profile auth up --build
