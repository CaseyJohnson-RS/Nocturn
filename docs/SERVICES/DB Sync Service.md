# DB Sync Service

---

## Description

**Sync Service** отвечает за синхронизацию основной базы заметок (**Notes DB**) с векторной базой данных (**Vector DB**).

Сервис подписывается на события изменений заметок через **Outbox** и асинхронно обновляет векторное представление данных (эмбеддинги и метаданные).  
Не обслуживает клиентские запросы напрямую.

---

## Responsibility

- Чтение событий изменений из **Outbox**
- Загрузка актуальных данных заметок из **Notes DB**
- Генерация эмбеддингов
- Создание, обновление и удаление записей в **Vector DB**
- Обеспечение eventual consistency между Notes DB и Vector DB
- Обработка повторных событий (idempotency)

---

## Non-Responsibilities

- Не принимает запросы от клиента
- Не хранит бизнес-логику заметок
- Не принимает решения об удалении или изменении данных
- Не выполняет поиск (retrieval)

---

## Input

### Source

- **Outbox (polling)**

### Event types (примерно)

- `NoteCreated`
- `NoteUpdated`
- `NoteDeleted`
- `NoteRestored`

### Event payload (примерно)

- `event_id`
- `event_type`
- `note_id`
- `user_id`
- `timestamp`

---

## Processing Flow

1. Периодически опрашивает Outbox (polling)
2. Забирает новые, необработанные события
3. Для каждого события:
    - читает актуальное состояние заметки из Notes DB
    - генерирует эмбеддинг
    - синхронизирует состояние с Vector DB
4. Помечает событие как обработанное

---

## Consistency Model

- **Eventual consistency**
- Векторная БД может временно отставать от основной
- Агент работает только с тем состоянием, которое уже проиндексировано

Это осознанный компромисс в пользу:

- масштабируемости
- изоляции сервисов
- отказоустойчивости

---

## Failure Handling

- Повторная обработка событий допустима (idempotent операции)
- При падении сервиса:
    - события остаются в Outbox
    - синхронизация продолжается после восстановления
- Потеря Sync Service не влияет на:
    - редактирование заметок
    - работу клиента

---

## Storage

- **Notes DB** — read-only
- **Vector DB** — write/read
- Локальное состояние (offset / last processed event) — опционально

---

## Stack

- **Python**
- Vector DB client (**ChromaDB**)
- Embeddings provider (LLM / **embedding model**)
- **PostgreSQL** (Outbox polling)