# Runbook: очередь эмбеддингов не разгребается

**Алерты:** `NocturnEmbeddingQueueBacklog`, `NocturnEmbeddingTasksFailing`,
`NocturnEmbeddingTasksStuck`

## Impact

Нарушается SLO свежести: заметки сохранены, но не находятся семантическим
поиском. Пользователь видит «поиск не работает», хотя формально всё зелёное —
ни одного 5xx, латентность в норме.

Дашборд: **Nocturn — Worker & Embedding Queue**.

## 1. Понять природу отставания

```promql
nocturn_embedding_queue_tasks                          # глубина по статусам
nocturn_embedding_queue_oldest_pending_seconds         # возраст головы очереди
sum by (outcome) (rate(nocturn_embedding_tasks_total[5m])) * 60
```

Три принципиально разных сценария:

| Картина | Диагноз | Куда дальше |
|---|---|---|
| `pending` растёт, `success` близок к нулю | Воркер стоит | [worker-stalled.md](worker-stalled.md) |
| `pending` растёт, но `success` идёт | Не хватает пропускной способности | п.2 |
| `failed` > 0 | Задачи исчерпали ретраи | п.3 |
| `processing` не меняется > 30 мин | Не работает reaper | п.4 |

## 2. Не хватает пропускной способности

Воркер берёт по 20 задач раз в 30 секунд — это потолок примерно 40 заметок в
минуту, и то если провайдер отвечает мгновенно. Проверьте, где узкое место:

```promql
# Сколько времени уходит на одну заметку
histogram_quantile(0.95, sum by (le) (rate(nocturn_embedding_task_duration_seconds_bucket[10m])))

# Из них — сколько ждём провайдера
histogram_quantile(0.95, sum by (le) (
  rate(nocturn_llm_request_duration_seconds_bucket{operation="embeddings"}[10m])))
```

Если почти всё время — ожидание провайдера, увеличение частоты опроса не
поможет. Варианты, по возрастанию сложности:

```bash
# 1. Опрашивать чаще (дёшево, помогает при коротких задачах)
EMBEDDING_QUEUE_INTERVAL_SECONDS=10

# 2. Запустить второй воркер
docker compose up -d --scale worker=2
```

Второй воркер безопасен не полностью: `get_pending_tasks` не берёт блокировку
(`FOR UPDATE SKIP LOCKED`), поэтому два воркера могут взять одну задачу и
посчитать эмбеддинг дважды. Данные при этом не портятся (чанки
перезаписываются), но платить провайдеру придётся дважды. Как временная
митигация — приемлемо; как постоянное решение — нужен `SKIP LOCKED`.

## 3. Задачи в статусе `failed`

Они исчерпали `EMBEDDING_MAX_ATTEMPTS` и **больше не будут обработаны никогда**.
Сначала выясните причину — она сохранена в самой строке:

```bash
docker compose exec postgres psql -U nocturn -d nocturn -c "
  SELECT note_id, attempts, left(error, 200) AS error, updated_at
  FROM embedding_queue WHERE status = 'failed' ORDER BY updated_at DESC LIMIT 20;"
```

Типичные причины: заметка длиннее контекста модели, недоступный провайдер во
время всех трёх попыток, изменившееся имя модели в конфиге.

После устранения причины вернуть задачи в очередь:

```bash
docker compose exec postgres psql -U nocturn -d nocturn -c "
  UPDATE embedding_queue SET status = 'pending', attempts = 0, error = NULL
  WHERE status = 'failed';"
```

## 4. Задачи залипли в `processing`

Означает, что воркер умер между `mark_processing` и `mark_done`. Штатно такие
задачи возвращаются в очередь через 15 минут (`STUCK_TASK_MINUTES`). Если
`processing` не рассасывается дольше — reaper не отрабатывает, то есть воркер
не крутит цикл вовсе, см. [worker-stalled.md](worker-stalled.md).

Вернуть вручную:

```bash
docker compose exec postgres psql -U nocturn -d nocturn -c "
  UPDATE embedding_queue SET status = 'pending'
  WHERE status = 'processing' AND updated_at < now() - interval '15 minutes';"
```

## Проверка восстановления

`nocturn_embedding_queue_oldest_pending_seconds` должен вернуться ниже 60
секунд. Панель *Age of the oldest pending embedding task* на дашборде SLO —
это и есть SLI свежести.

## Эскалация

Не эскалируется как `page`: пользовательские данные не теряются, страдает
только полнота поиска. Если backlog не разгребается больше суток — стоит
пересмотреть архитектуру очереди (`SKIP LOCKED` + несколько воркеров) и
завести это отдельной задачей, а не чинить в режиме инцидента.
