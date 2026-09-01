# Runbook: Postgres близок к пределу соединений

**Алерт:** `PostgresConnectionsHigh` (> 80% от `max_connections` в течение 10 мин)

## Impact

Пока предупреждение: сервис работает. Но при исчерпании `max_connections`
новые соединения получают `FATAL: sorry, too many clients already`, и API
начинает отдавать 5xx на всех эндпоинтах разом. Между «80%» и «полный отказ»
может быть один деплой или один скачок трафика.

## Арифметика, которую надо проверить

Это главное содержимое runbook'а — не команда, а расчёт.

```
потребление = (pool_size + max_overflow) × реплик_api
            + пул_воркера × реплик_воркера
            + служебные (psql, экспортёр, миграции)
```

Текущая конфигурация:

| Компонент | Соединений |
|---|---|
| API (`DATABASE_POOL_SIZE=10` + `DATABASE_MAX_OVERFLOW=5`) | 15 на реплику |
| Воркер (`pool_size=5`) | 5 на реплику |
| postgres-exporter | 1–2 |
| Запас на ручной `psql` и миграции | 5 |

При `max_connections=100` (дефолт Postgres) это даёт потолок примерно
**5 реплик API**. Каждый `--scale worker=N` тоже отъедает по 5.

Проверить фактические значения:

```bash
docker compose exec postgres psql -U nocturn -d nocturn -c "SHOW max_connections;"

docker compose exec postgres psql -U nocturn -d nocturn -c "
  SELECT state, count(*) FROM pg_stat_activity
  WHERE datname = 'nocturn' GROUP BY state ORDER BY count DESC;"
```

## 1. Кто держит соединения

```bash
docker compose exec postgres psql -U nocturn -d nocturn -c "
  SELECT application_name, client_addr, state, count(*)
  FROM pg_stat_activity WHERE datname = 'nocturn'
  GROUP BY 1,2,3 ORDER BY count DESC;"
```

Отдельно — «висящие» соединения, которые обычно и являются причиной:

```bash
docker compose exec postgres psql -U nocturn -d nocturn -c "
  SELECT pid, state, now() - state_change AS idle_for, left(query, 100)
  FROM pg_stat_activity
  WHERE state = 'idle in transaction' AND now() - state_change > interval '1 minute'
  ORDER BY idle_for DESC;"
```

`idle in transaction` дольше минуты — это утечка сессии в коде: транзакция
открыта и не закрыта. Соединение занято, но работы не делает.

## 2. Быстрая митигация

```bash
# Прибить зависшие транзакции (безопасно: они всё равно ничего не делают)
docker compose exec postgres psql -U nocturn -d nocturn -c "
  SELECT pg_terminate_backend(pid) FROM pg_stat_activity
  WHERE datname = 'nocturn' AND state = 'idle in transaction'
    AND now() - state_change > interval '5 minutes';"
```

Если соединения заняты законно и нужен запас прямо сейчас — либо уменьшите
`DATABASE_POOL_SIZE` (меньше параллелизма, но сервис жив), либо поднимите
`max_connections`, помня, что каждое соединение в Postgres — это отдельный
процесс с собственной памятью:

```bash
docker compose exec postgres psql -U nocturn -d nocturn -c \
  "ALTER SYSTEM SET max_connections = 200;"
docker compose restart postgres   # требует рестарта
```

Поднимать `max_connections` до сотен — плохой путь. Правильное решение при
реальном росте — пулер (PgBouncer в режиме transaction) между приложением и
базой.

## 3. Не деплой ли это

Каждая новая реплика мгновенно добавляет 15 соединений. Если алерт совпал с
масштабированием — это не утечка, а исчерпанная ёмкость, и лечится она
уменьшением `DATABASE_POOL_SIZE` на реплику, а не увеличением лимита.

## Проверка

```promql
sum(pg_stat_activity_count) / max(pg_settings_max_connections)
```

Должно устойчиво держаться ниже 0.8.

## Эскалация

Достигли 95% — это уже подступающий полный отказ. Немедленно сократите число
реплик до минимально работоспособного и только потом разбирайтесь: отказ в
обслуживании хуже, чем замедление.
