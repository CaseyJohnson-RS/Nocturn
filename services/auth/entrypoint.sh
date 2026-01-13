#!/usr/bin/env sh
set -e

# Проверка наличия uv
if ! command -v uv >/dev/null 2>&1; then
  echo "[error] uv not found. Please install uv."
  exit 1
fi

RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"

if [ "$RUN_MIGRATIONS" = "false" ]; then
  echo "[migrations] skipped"
  exec "$@"
fi

echo "[migrations] running alembic upgrade head"

# Функция для запуска миграций с retry и таймаутом
run_migrations() {
  local max_attempts=5
  local attempt=1
  local timeout_seconds=10

  while [ $attempt -le $max_attempts ]; do
    echo "[migrations] attempt $attempt/$max_attempts"
    if timeout $timeout_seconds uv run alembic upgrade head; then
      echo "[migrations] success"
      return 0
    else
      echo "[migrations] attempt $attempt failed"
      if [ $attempt -lt $max_attempts ]; then
        echo "[migrations] retrying in 5 seconds..."
        sleep 5
      fi
      attempt=$((attempt + 1))
    fi
  done

  echo "[error] migrations failed after $max_attempts attempts"
  exit 1
}

run_migrations

exec "$@"
