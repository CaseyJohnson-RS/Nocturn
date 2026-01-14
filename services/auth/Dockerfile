FROM astral/uv:python3.10-bookworm

WORKDIR /auth-service
COPY . .

RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
