# Runbooks

Один runbook на алерт. Ссылка на нужный приходит прямо в уведомлении
(`runbook_url` в аннотациях правила) — открывать этот индекс во время инцидента
не нужно.

| Алерт | Runbook |
|---|---|
| `NocturnAvailabilityBudgetBurn*` | [api-error-rate.md](api-error-rate.md) |
| `NocturnLatencyBudgetBurn*` | [api-latency.md](api-latency.md) |
| `NocturnApiDown` | [api-down.md](api-down.md) |
| `NocturnDependencyDown`, `RedisDown`, `PostgresDown`, `NocturnRateLimiterDegraded` | [dependency-down.md](dependency-down.md) |
| `NocturnWorkerDown`, `NocturnWorkerStalled` | [worker-stalled.md](worker-stalled.md) |
| `NocturnEmbeddingQueueBacklog`, `NocturnEmbeddingTasksFailing`, `NocturnEmbeddingTasksStuck` | [embedding-backlog.md](embedding-backlog.md) |
| `NocturnLlmProviderErrors`, `NocturnLlmTimeToFirstTokenSlow` | [llm-provider-outage.md](llm-provider-outage.md) |
| `PostgresConnectionsHigh` | [postgres-saturation.md](postgres-saturation.md) |

## Формат

Каждый runbook отвечает на четыре вопроса и ничего сверх этого:

1. **Что сломано у пользователя** — impact, а не текст алерта.
2. **Как понять причину** — конкретные запросы и команды, копируемые как есть.
3. **Как остановить кровь** — митигация, часто без устранения root cause.
4. **Когда эскалировать** — условие, а не «если не помогло».

Runbook пишется под человека, который разбужен, видит этот сервис впервые за
три месяца и не помнит, как называются контейнеры.

## Общие команды

```bash
# Состояние всего стека
docker compose -f docker-compose.yml -f docker-compose.observability.yml ps

# Логи одного сервиса в JSON, последние 200 строк
docker compose logs --tail=200 backend

# Проверить, что инстанс вообще готов принимать трафик
curl -s localhost/readyz | jq
```

Grafana: <http://localhost:3001> · Prometheus: <http://localhost:9090> ·
Alertmanager: <http://localhost:9093>
