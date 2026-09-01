# Runbook: рост латентности API

**Алерты:** `NocturnLatencyBudgetBurnFast`, `NocturnLatencyBudgetBurnSlow`

## Impact

Запросы обслуживаются медленнее 250 мс чаще, чем позволяет SLO. Приложение
ощущается тормозящим: автосохранение заметки подвисает, список грузится с
задержкой. Ошибок при этом нет — доступность может быть 100%.

## 1. Что именно медленное

Дашборд **Nocturn — Service Overview**, панель *Slowest endpoints (p95)*.

```promql
topk(10, histogram_quantile(0.95,
  sum by (le, path) (rate(nocturn_http_request_duration_seconds_bucket{path!="<unmatched>"}[5m]))))
```

Сравните с профилем нагрузки — вырос ли трафик:

```promql
sum(rate(nocturn_http_requests_total[5m]))
```

* **Латентность выросла вместе с трафиком** → упёрлись в ёмкость, переходите к п.2.
* **Трафик не менялся** → деградация зависимости или регрессия запроса, п.3.

## 2. Ёмкость

Первый подозреваемый — пул соединений SQLAlchemy. При `pool_size=10` и
`max_overflow=5` одиннадцатый одновременный запрос встаёт в очередь, и это
выглядит именно как рост латентности без ошибок.

```promql
# Занятость соединений на стороне Postgres
sum(pg_stat_activity_count) / max(pg_settings_max_connections)

# Сколько запросов в обработке прямо сейчас
sum(nocturn_http_requests_in_progress)
```

Если `in_progress` устойчиво превышает `pool_size + max_overflow` —
поднимите `DATABASE_POOL_SIZE`, предварительно проверив по
[postgres-saturation.md](postgres-saturation.md), что сервер это выдержит.

## 3. Медленные запросы к БД

```bash
docker compose exec postgres psql -U nocturn -d nocturn -c "
  SELECT pid, now() - query_start AS duration, left(query, 120) AS query
  FROM pg_stat_activity
  WHERE state = 'active' AND now() - query_start > interval '1 second'
  ORDER BY duration DESC;"
```

Отдельно проверьте векторный поиск: `/api/rag/search` делает
cosine-distance по всем чанкам пользователя, и без индекса он линейно
деградирует с ростом базы.

```promql
histogram_quantile(0.95, sum by (le) (
  rate(nocturn_http_request_duration_seconds_bucket{path=~"/api/rag/.*"}[5m])))
```

## 4. Redis

Rate limiter делает четыре команды Redis на каждый запрос — они на
критическом пути. Медленный Redis замедляет **всё**.

```bash
docker compose exec redis redis-cli --latency-history
docker compose exec redis redis-cli info stats | grep -E 'instantaneous|keyspace'
```

## Митигация

| Причина | Действие |
|---|---|
| Пул БД исчерпан | Поднять `DATABASE_POOL_SIZE`, следом проверить `max_connections` |
| Медленный RAG-поиск | Временно снизить `MAX_SOURCES_PER_RESPONSE`, завести задачу на ivfflat-индекс |
| Медленный Redis | Проверить память (`RedisMemoryHigh`), при необходимости перезапустить |
| Регрессия в коде | Откат деплоя (см. [api-error-rate.md](api-error-rate.md), п.3) |

## Эскалация

Латентность сама по себе — `ticket`, не `page`. Но если p95 переваливает за
1 секунду или начинают появляться 5xx (таймауты) — это уже инцидент
доступности, переходите к [api-error-rate.md](api-error-rate.md).
