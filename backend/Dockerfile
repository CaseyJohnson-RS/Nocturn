FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libre2-dev && \
    rm -rf /var/lib/apt/lists/*

ARG INSTALL_DEV=false
COPY pyproject.toml uv.lock ./
RUN if [ "$INSTALL_DEV" = "true" ]; then \
      uv sync --frozen --no-dev && \
      ./.venv/bin/python -m ensurepip && \
      ./.venv/bin/python -m pip install --upgrade pip && \
      ./.venv/bin/python -m pip install pytest pytest-asyncio; \
    else \
      uv sync --frozen --no-dev; \
    fi

COPY . .

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips", "*"]
