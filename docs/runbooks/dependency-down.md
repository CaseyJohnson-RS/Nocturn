# Runbook: недоступна зависимость (Postgres / Redis)

**Алерты:** `NocturnDependencyDown`, `PostgresDown`, `RedisDown`,
`NocturnRateLimiterDegraded`, `RedisMemoryHigh`

## Как деградирует продукт

Важно понимать заранее, что именно ломается — от этого зависит срочность.

| Отказала | Что перестаёт работать | Что продолжает |
|---|---|---|
| **Postgres** | Всё. Заметки, логин, ИИ | Ничего |
| **Redis** | Rate limiting; писать нельзя (fail closed → 503) | Чтение заметок, ИИ-чат |

Отказ Redis — **частичная** деградация, и это спроектированное поведение:
на GET/HEAD limiter пропускает запрос (fail open, доступность важнее
ограничения), на записи возвращает 503 (fail closed, неучтённые записи хуже
отказа). Обе ветки инкрементят `nocturn_rate_limit_errors_total`, поэтому
тихой деградации не бывает.

## 1. Что именно недоступно

```bash
curl -s localhost/readyz | jq
```

Ответ прямо называет отказавшую зависимость и текст ошибки:

```json
{"status": "not_ready",
 "checks": {"postgres": {"ok": true, "error": null},
            "redis": {"ok": false, "error": "ConnectionError: ..."}}}
```

```promql
nocturn_dependency_up          # с точки зрения приложения
pg_up                          # с точки зрения экспортёра
redis_up
```

Расхождение между `nocturn_dependency_up{dependency="postgres"} == 0` и
`pg_up == 1` означает, что база жива, а сеть или пул соединений — нет.

## 2. Postgres

```bash
docker compose ps postgres
docker compose logs --tail=100 postgres

# Принимает ли соединения
docker compose exec postgres pg_isready -U nocturn

# Не кончилось ли место — самая частая причина «внезапной» смерти
docker compose exec postgres df -h /var/lib/postgresql/data
```

Кончилось место → освободить и только потом поднимать: Postgres,
запущенный на полном диске, уходит в recovery по кругу.

## 3. Redis

```bash
docker compose exec redis redis-cli ping
docker compose exec redis redis-cli info memory | grep -E 'used_memory_human|maxmemory'
docker compose logs --tail=50 redis
```

Redis здесь хранит только rate-limit окна и служебное состояние — данные
пользователей в нём не лежат. Поэтому **сброс Redis безопасен** и это
допустимая быстрая митигация:

```bash
docker compose restart redis
```

Единственное последствие — счётчики rate limit обнулятся.

## 4. Митигация

| Ситуация | Действие |
|---|---|
| Контейнер упал | `docker compose up -d <service>` |
| Кончилось место на диске | Освободить, затем поднимать БД |
| Redis переполнен | Задать `maxmemory` + `allkeys-lru`, перезапустить |
| Сетевая изоляция | `docker network inspect nocturn_default` |
| БД жива, приложение не видит | Перезапустить `backend` — вероятно, залип пул |

## Проверка восстановления

```bash
curl -s localhost/readyz | jq -e '.status == "ready"' && echo OK
```

Метрика `nocturn_dependency_up` вернётся в 1 в течение ~15 секунд после
следующей проверки готовности (результат кэшируется на 2 секунды).

## Эскалация

Postgres недоступен дольше 10 минут — это уже про восстановление из бэкапа,
а не про перезапуск контейнера. Убедитесь, что свежий дамп существует, прежде
чем предпринимать что-либо разрушительное с volume.
