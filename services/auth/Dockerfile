FROM astral/uv:python3.10-alpine

WORKDIR /auth-service
COPY . .

RUN uv sync --no-dev

EXPOSE 8000

RUN chmod +x entrypoint.sh
ENTRYPOINT [ "./entrypoint.sh" ]