#!/bin/sh

if [ "$MIGRATE" = "True" ]; then
  echo "MIGRATE=True: starting database migrations..."
  uv run alembic upgrade head
  if [ $? -ne 0 ]; then
    echo "Error: database migration failed" >&2
    exit 1
  fi
else
  echo "MIGRATE is not True (value: '$MIGRATE'), skipping migrations"
fi

uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

exec "$@"
