# Runbook: API не отвечает

**Алерт:** `NocturnApiDown` (`up{job="nocturn-api"} == 0` дольше минуты)

## Impact

Полный отказ. Приложение не открывается вообще. Бюджет доступности горит с
максимальной скоростью — весь месячный запас исчезает за 3 часа 39 минут
непрерывного простоя.

Прежде чем чинить, поймите: алерт означает, что **Prometheus не смог снять
метрики**. Это не всегда падение сервиса — это может быть и разрыв сети между
Prometheus и приложением.

## 1. Отличить падение от проблемы мониторинга

```bash
# Отвечает ли приложение снаружи вообще
curl -sS -m 5 -o /dev/null -w '%{http_code}\n' localhost/livez

# Жив ли контейнер и не рестартует ли он по кругу
docker compose ps backend
```

* `curl` отвечает 200, а алерт горит → проблема в мониторинге, не в продукте.
  Проверьте `promtail`/`prometheus`, инцидент понижается до `ticket`.
* `curl` молчит → реальный отказ, дальше по пунктам.

## 2. Почему процесс не поднимается

```bash
docker compose logs --tail=100 backend
```

Наиболее вероятные причины, в порядке частоты:

| Симптом в логах | Причина | Действие |
|---|---|---|
| `alembic upgrade head` падает | Битая миграция | См. п.3 |
| `ConnectionRefusedError` к postgres | БД не поднялась | [dependency-down.md](dependency-down.md) |
| `ValidationError` от pydantic-settings | Не хватает переменной окружения | Сверить с `.env.example` |
| `Address already in use` | Порт занят прошлым контейнером | `docker compose down && docker compose up -d` |
| Контейнер в `Restarting` без логов | OOM | `docker inspect <id> \| grep -i oom` |

## 3. Падение на миграциях

Приложение по умолчанию накатывает миграции при старте
(`RUN_MIGRATIONS_ON_STARTUP=true`), поэтому битая миграция гарантированно
превращается в crash loop. Разорвать цикл:

```bash
# Поднять API без миграций, чтобы вернуть сервис пользователям
docker compose run --rm -e RUN_MIGRATIONS_ON_STARTUP=false -p 8000:8000 backend

# Разбираться с миграцией отдельно
docker compose run --rm backend uv run python -m alembic current
docker compose run --rm backend uv run python -m alembic history --verbose
```

Именно поэтому миграции вынесены в отдельный шаг (`make migrate`): падение
миграции должно валить деплой, а не работающий сервис.

## 4. Восстановление

```bash
docker compose up -d backend
BASE_URL=http://localhost ./scripts/smoke-test.sh
```

Smoke-тест обязателен: `livez` отвечает и на инстансе, у которого нет связи с
БД, — он специально ничего не проверяет.

## Эскалация

Больше 15 минут простоя без понятной причины — откатывайтесь на последний
заведомо рабочий образ, не дожидаясь диагноза. Восстановление сервиса важнее
понимания причины; причину найдёте по сохранённым логам.

```bash
docker compose logs --no-color > incident-$(date +%s).log
```
