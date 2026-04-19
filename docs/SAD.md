# Software Architecture Document
## **Nocturn**
**Версия:** 1.3
**Дата:** 2026-04-19
**Автор:** Shamukhametov Ruslan

---
## Содержание

[[#1. Введение]]
[[#2. Обзор архитектуры]]
[[#3. Модульная структура backend]]
[[#4. Аутентификация и безопасность]]
[[#5. База данных]]
[[#6. Embedding]]
[[#7. AI-ассистент]]
[[#8. Frontend]]
[[#9. Worker]]
[[#10. Развёртывание]]
[[#11. Принятые trade-offs]]

---
## 1. Введение

### 1.1 Цель документа

Данный документ описывает архитектуру системы Nocturn: компоненты, их взаимодействие, выбранные технологии и обоснования принятых решений. Документ предназначен для использования при разработке и сопровождении системы.

### 1.2 Связанные документы

| Документ                | Описание                                       |
| ----------------------- | ---------------------------------------------- |
| SRS                     | Функциональные и нефункциональные требования   |
| CPS                     | Конфигурируемые параметры, политики, лимиты    |
| Assistant Specification | Детальная спецификация поведения AI-ассистента |

### 1.3 Стек технологий

| Компонент                        | Технология                      |
| -------------------------------- | ------------------------------- |
| Backend                          | Python, FastAPI, Uvicorn        |
| Frontend                         | React                           |
| База данных                      | PostgreSQL + pgvector           |
| Embedding-модель                 | RouterAI (внешний сервис)       |
| LLM API                          | RouterAI (внешний сервис)       |
| Email                            | Resend / Brevo (внешний сервис) |
| Контейнеризация                  | Docker, docker-compose          |
| Reverse proxy                    | Nginx                           |
| Pub/Sub, Rate limiting, Presence | Redis                           |

---
<div class="page-break" style="page-break-before: always;"></div>

## 2. Обзор архитектуры

### 2.1 Архитектурный стиль

Модульный монолит. Единый backend-сервис с чёткими границами между модулями. Выбор обусловлен: один разработчик, 25 пользователей, отсутствие потребности в независимом масштабировании отдельных компонентов. При необходимости модули могут быть выделены в отдельные сервисы - границы зависимостей это позволяют.

### 2.2 Контейнеры

| Контейнер | Назначение                                                 |
| --------- | ---------------------------------------------------------- |
| backend   | FastAPI-приложение, API, бизнес-логика                     |
| frontend  | React SPA, статика, отдаётся через Nginx                   |
| postgres  | PostgreSQL + pgvector                                      |
| worker    | Фоновые задачи: очередь embedding, очистка данных          |
| nginx     | Reverse proxy, HTTPS-терминация, маршрутизация             |
| redis     | Pub/Sub для SSE, rate limiting, presence активного клиента |
### 2.3 Зависимости

**Внешние зависимости**

| Сервис         | Назначение              | Последствия недоступности                                            |
| -------------- | ----------------------- | -------------------------------------------------------------------- |
| RouterAI       | LLM API + Embedding API | AI-ассистент и семантический поиск недоступны. CRUD заметок работает |
| Resend / Brevo | Отправка email          | Регистрация и сброс пароля невозможны. Остальное работает            |

**Внутренние зависимости**

| Сервис     | Назначение                       | Последствия недоступности                                                                                    |
| ---------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| PostgreSQL | Основное хранилище данных        | Система полностью недоступна                                                                                 |
| Redis      | Pub/Sub, rate limiting, presence | Мутирующие операции недоступны (503). Чтение работает (без rate limiting). AI-стриминг и presence недоступны |

<div class="page-break" style="page-break-before: always;"></div>

### 2.4 Диаграмма контейнеров

```mermaid
graph TD
    User[Пользователь] -->|HTTPS| Nginx
    Nginx --> Frontend[Frontend<br/>React SPA]
    Nginx --> Backend[Backend<br/>FastAPI]
    Backend --> Postgres[(PostgreSQL<br/>+ pgvector)]
    Backend --> Redis[(Redis)]
    Backend --> RouterAI[RouterAI<br/>LLM + Embedding API]
    Backend --> Email[Email-провайдер]
    Worker[Worker] --> Postgres
    Worker --> RouterAI
```
---
<div class="page-break" style="page-break-before: always;"></div>

## 3. Модульная структура backend

### 3.1 Архитектура модуля

Каждый модуль с эндпоинтами следует трёхслойной архитектуре:

- **Router** - эндпоинты, валидация входных данных, вызов service
- **Service** - бизнес-логика, оркестрация, вызов repository
- **Repository** - SQL-запросы, работа с БД

Модули без дополнительных файлов (profile) содержат только router, service и schemas.

```mermaid
graph LR
    Request --> Router --> Service --> Repository --> DB[(PostgreSQL)]
```

### 3.2 Модули

|Модуль|Ответственность|Эндпоинты|
|---|---|---|
|auth|Регистрация, вход, подтверждение email, сброс пароля, управление токенами|Да|
|notes|CRUD заметок, soft delete, корзина, версионирование, поиск по ключевым словам (FR-NOTES-10). При сохранении пишет задачу в embedding_queue|Да|
|tags|CRUD тегов, связь с заметками|Да|
|ai|Чат-сессии, взаимодействие с LLM, proposals, bulk-операции|Да|
|admin|Список пользователей, блокировка, статистика|Да|
|profile|Просмотр и редактирование профиля|Да|
|rag|Семантический поиск, полнотекстовый поиск, комбинирование результатов|Да|
<div class="page-break" style="page-break-before: always;"></div>

### 3.3 Правила зависимостей

Модули с эндпоинтами не вызывают друг друга. Взаимодействие:

- **Auth middleware** - извлекает user_id из JWT и передаёт в контекст запроса. Остальные модули получают user_id из контекста, не зная о механизме аутентификации
- **Служебные модули** - модуль ai вызывает rag.service для семантического и полнотекстового поиска. Для остальных данных (заметки, теги) ai использует собственный repository
- **Outbox** - notes при сохранении пишет задачу в embedding_queue. Worker подхватывает и генерирует вектора через RouterAI
- **Redis** — общий клиент в `common/`. Используется для: Pub/Sub (SSE-события), rate limiting (счётчики запросов), presence (активный клиент). Модули не обращаются к Redis напрямую — взаимодействие через общие утилиты
		
```mermaid
graph TD
    Middleware[Auth Middleware<br/>JWT → user_id] --> notes
    Middleware --> tags
    Middleware --> ai
    Middleware --> admin
    Middleware --> profile
	ai -->|доступ к LLM| RouterAI
    ai -->|сервисный слой| rag
    notes -->|embedding_queue| Worker
    Worker -->|генерация векторов| RouterAI
```

<div class="page-break" style="page-break-before: always;"></div>

### 3.4 Структура проекта

```
backend/
├── src/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── seed.py
│   │   ├── middleware/
│   │   │   ├── auth.py
│   │   │   └── rate_limit.py
│   │   ├── modules/
│   │   │   ├── auth/
│   │   │   │   ├── router.py
│   │   │   │   ├── service.py
│   │   │   │   ├── repository.py
│   │   │   │   ├── schemas.py
│   │   │   │   └── models.py
│   │   │   ├── notes/
│   │   │   ├── tags/
│   │   │   ├── ai/
│   │   │   │   └── (router, service, repository, schemas, models, tools, locale)
│   │   │   ├── admin/
│   │   │   ├── profile/
│   │   │   └── rag/
│   │   │       ├── router.py
│   │   │       ├── service.py
│   │   │       ├── repository.py
│   │   │       ├── schemas.py
│   │   │       └── models.py
│   │   └── common/
│   │       ├── database/
│   │       │   ├── base.py
│   │       │   └── engine.py
│   │       ├── dependencies.py
│   │       ├── email.py
│   │       ├── exceptions.py
│   │       ├── models.py
│   │       ├── redis.py
│   │       └── routerai.py
│   └── worker/
│       └── main.py
├── migrations/
└── tests/
```
<div class="page-break" style="page-break-before: always;"></div>

## 4. Аутентификация и безопасность

### 4.1 Схема аутентификации

Аутентификация построена на паре access token (JWT) + refresh token с ротацией.
Предусловия: пользователь зарегистрирован (FR-AUTH-01) и подтвердил email (FR-AUTH-02). Неподтверждённый пользователь не может войти в систему.

```mermaid
sequenceDiagram
    participant C as Клиент
    participant B as Backend
    participant DB as PostgreSQL

    C->>B: POST /auth/login (email, password)
    B->>DB: Проверка credentials
    B-->>C: access token (JWT) + refresh token (cookie)

    C->>B: GET /notes (Authorization: Bearer JWT)
    B->>B: Валидация JWT, извлечение user_id
    B-->>C: Данные

    Note over C,B: Access token истёк

    C->>B: POST /auth/refresh (refresh token cookie)
    B->>DB: Проверка refresh token, ротация
    B-->>C: Новый access token + новый refresh token
```

### 4.2 Access token (JWT)

| Параметр            | Значение                             |
| ------------------- | ------------------------------------ |
| Формат              | JWT (HS256)                          |
| Время жизни         | [[CPS#5.1 Сессии и токены]]          |
| Payload             | user_id, role, exp, iat              |
| Хранение на клиенте | В памяти (JavaScript-переменная)     |

JWT не хранится в БД. Валидация - проверка подписи и срока. При блокировке пользователя access token остаётся валидным до истечения. Это осознанный trade-off (см. раздел 11).

### 4.3 Refresh token

|Параметр| Значение                                                        |
|---|---|
|Формат| Случайная строка (UUID v4 или crypto-random)                    |
|Время жизни| [[CPS#5.1 Сессии и токены]]                                     |
|Хранение в БД| Хеш (SHA-256) в таблице refresh_tokens                          |
|Хранение на клиенте| HttpOnly, Secure, SameSite=Strict cookie                        |
|Ротация| При каждом использовании старый токен удаляется, выдаётся новый |

Если предъявлен уже использованный refresh token (replay attack), все сессии пользователя аннулируются.
<div class="page-break" style="page-break-before: always;"></div>

### 4.4 Хеширование паролей

Алгоритм: Argon2id. Устойчив к side-channel и GPU-атакам. Конкретные параметры (memory cost, time cost, parallelism) определяются дефолтами используемой библиотеки и фиксируются при деплое.


### 4.5 Защита от CSRF

Refresh token передаётся через cookie с `SameSite=Strict`. Этот флаг гарантирует, что cookie не отправляется при cross-site запросах, что исключает CSRF-атаки на эндпоинт `/auth/refresh`.

Access token хранится в памяти и передаётся через заголовок `Authorization` - не подвержен CSRF.

### 4.6 CORS

Backend принимает запросы только с домена frontend-приложения. Настраивается в FastAPI middleware:

- `allow_origins`: домен frontend
- `allow_credentials`: true (для передачи cookie)
- `allow_methods`: GET, POST, PUT, PATCH, DELETE

### 4.7 Rate limiting

- Реализуется как FastAPI middleware. Лимиты определены в [[CPS#6. Rate limiting]]
- Счётчики хранятся в Redis (sliding window)
- При недоступности Redis: read-запросы пропускаются без rate limit, мутирующие запросы возвращают 503 (см. NFR-REL-03)

|Тип лимита|Ключ|Источник ключа|
|---|---|---|
|AUTH-эндпоинты|IP-адрес|Заголовок X-Forwarded-For от Nginx|
|CRUD-эндпоинты|user_id|JWT payload|
|AI-эндпоинты|user_id|JWT payload|

Nginx настраивается как trusted proxy: перезаписывает (не дописывает) заголовок `X-Forwarded-For`. FastAPI принимает этот заголовок только от IP Nginx (`--forwarded-allow-ips`).

### 4.8 HTTPS

HTTPS-терминация выполняется на уровне Nginx. Соединение между Nginx и backend - HTTP внутри Docker-сети (не выходит наружу).

---
<div class="page-break" style="page-break-before: always;"></div>

## 5. База данных

### 5.1 Общие принципы

- Все первичные ключи - UUID v4
- Временные метки хранятся в UTC
- Soft delete реализуется через поле `deleted_at` (NULL - активная запись, timestamp - удалённая)
- Все таблицы с `user_id` имеют индекс по этому полю для изоляции данных

### 5.2 Схема данных

```mermaid
erDiagram
    users ||--o{ notes : "владеет"
    users ||--o{ tags : "владеет"
    users ||--o{ refresh_tokens : "имеет"
    users ||--o{ verification_tokens : "имеет"
    users ||--o{ chat_sessions : "владеет"
    notes ||--o{ note_tags : "имеет"
    tags ||--o{ note_tags : "имеет"
    notes ||--o{ note_chunks : "имеет"
    notes ||--o| embedding_queue : "имеет"
    chat_sessions ||--o{ chat_messages : "содержит"
```

### 5.3 Таблицы

> **users**

|Колонка|Тип|Ограничения|Описание|
|---|---|---|---|
|id|UUID|PK||
|email|VARCHAR(255)|UNIQUE, NOT NULL|Хранится в lowercase|
|nickname|VARCHAR(32)|NOT NULL||
|password_hash|TEXT|NOT NULL|Argon2id хеш|
|role|VARCHAR(10)|NOT NULL, DEFAULT 'user'|user / admin|
|is_email_confirmed|BOOLEAN|NOT NULL, DEFAULT false||
|is_active|BOOLEAN|NOT NULL, DEFAULT true|false = заблокирован|
|created_at|TIMESTAMPTZ|NOT NULL, DEFAULT now()||
|updated_at|TIMESTAMPTZ|NOT NULL, DEFAULT now()||

> **notes**

|Колонка|Тип|Ограничения|Описание|
|---|---|---|---|
|id|UUID|PK||
|user_id|UUID|FK → users, NOT NULL||
|title|VARCHAR(200)||NULL = без заголовка|
|content|TEXT||NULL = пустая заметка|
|version|INTEGER|NOT NULL, DEFAULT 1|Инкрементируется при каждом сохранении|
|created_at|TIMESTAMPTZ|NOT NULL, DEFAULT now()||
|updated_at|TIMESTAMPTZ|NOT NULL, DEFAULT now()||
|deleted_at|TIMESTAMPTZ||NULL = активная|

> **tags**

|Колонка|Тип|Ограничения|Описание|
|---|---|---|---|
|id|UUID|PK||
|user_id|UUID|FK → users, NOT NULL||
|name|VARCHAR(50)|NOT NULL|Уникальность регистронезависимая в рамках user_id|
|created_at|TIMESTAMPTZ|NOT NULL, DEFAULT now()||

> **note_tags**

|Колонка|Тип|Ограничения|Описание|
|---|---|---|---|
|note_id|UUID|PK, FK → notes||
|tag_id|UUID|PK, FK → tags||

> **note_chunks**

|Колонка|Тип|Ограничения|Описание|
|---|---|---|---|
|id|UUID|PK||
|note_id|UUID|FK → notes, NOT NULL||
|user_id|UUID|FK → users, NOT NULL|Денормализация (см. 5.5)|
|chunk_index|INTEGER|NOT NULL|Порядковый номер чанка в заметке|
|embedding|VECTOR(2560)|nullable|Размерность определяется моделью (default 2560); null до первой генерации|
|created_at|TIMESTAMPTZ|NOT NULL, DEFAULT now()||

> **embedding_queue**

|Колонка|Тип|Ограничения|Описание|
|---|---|---|---|
|id|UUID|PK||
|note_id|UUID|FK → notes, UNIQUE|Одна задача на заметку|
|user_id|UUID|FK → users, NOT NULL|Денормализация для поиска задач по пользователю|
|status|VARCHAR(20)|NOT NULL, DEFAULT 'pending'|pending / processing / failed|
|attempts|INTEGER|NOT NULL, DEFAULT 0||
|error|TEXT||Текст последней ошибки (заполняется при failed)|
|created_at|TIMESTAMPTZ|NOT NULL, DEFAULT now()||
|updated_at|TIMESTAMPTZ|NOT NULL, DEFAULT now()|Время последней попытки|

> **refresh_tokens**

|Колонка|Тип|Ограничения|Описание|
|---|---|---|---|
|id|UUID|PK||
|user_id|UUID|FK → users, NOT NULL||
|token_hash|TEXT|NOT NULL|SHA-256 хеш токена|
|expires_at|TIMESTAMPTZ|NOT NULL||
|created_at|TIMESTAMPTZ|NOT NULL, DEFAULT now()||
<div class="page-break" style="page-break-before: always;"></div>

> **verification_tokens**

|Колонка|Тип|Ограничения|Описание|
|---|---|---|---|
|id|UUID|PK||
|user_id|UUID|FK → users, NOT NULL||
|type|VARCHAR(20)|NOT NULL|email_confirm / password_reset|
|token_hash|TEXT|NOT NULL|SHA-256 хеш токена|
|expires_at|TIMESTAMPTZ|NOT NULL||
|created_at|TIMESTAMPTZ|NOT NULL, DEFAULT now()||

> **chat_sessions**

|Колонка|Тип|Ограничения|Описание|
|---|---|---|---|
|id|UUID|PK||
|user_id|UUID|FK → users, NOT NULL||
|title|VARCHAR(200)|nullable|Автоматически заполняется из первых 100 символов первого сообщения|
|created_at|TIMESTAMPTZ|NOT NULL, DEFAULT now()||
|last_message_at|TIMESTAMPTZ||Для определения срока хранения|

> **chat_messages**

| Колонка           | Тип         | Ограничения                  | Описание                                                          |
| ----------------- | ----------- | ---------------------------- | ----------------------------------------------------------------- |
| id                | UUID        | PK                           |                                                                   |
| session_id        | UUID        | FK → chat_sessions, NOT NULL |                                                                   |
| role              | VARCHAR(10) | NOT NULL                     | user / assistant                                                  |
| content           | TEXT        | NOT NULL                     | Текст сообщения                                                   |
| actions           | JSONB       |                              | Proposals и confirmations, только для assistant                   |
| attached_note_ids | UUID[]      |                              | Без FK. ID прикреплённых заметок ([[CPS#5.3 AI-ассистент]]). Только для user |
| token_estimate    | INTEGER     | NOT NULL, DEFAULT 0          | Приблизительное количество токенов. Используется при формировании токен-бюджета истории |
| created_at        | TIMESTAMPTZ | NOT NULL, DEFAULT now()      |                                                                   |
<div class="page-break" style="page-break-before: always;"></div>

### 5.4 Индексы

|Таблица|Индекс|Тип|Назначение|
|---|---|---|---|
|notes|user_id, deleted_at|B-tree|Фильтрация заметок пользователя|
|notes|content|GIN (tsvector)|Полнотекстовый поиск|
|notes|created_at|B-tree|Фильтрация по дате (AI-ассистент)|
|notes|deleted_at|B-tree|Задача очистки (NFR-CLEAN-04)|
|note_chunks|embedding|HNSW|Семантический поиск (фильтрация по user_id выполняется через B-tree + JOIN с notes для проверки soft delete)|
|note_chunks|user_id|B-tree|Фильтрация чанков по пользователю|
|tags|user_id, lower(name)|B-tree, UNIQUE|Уникальность имени тега в рамках пользователя|
|chat_sessions|user_id|B-tree|Список сессий пользователя|
|chat_sessions|last_message_at|B-tree|Задача очистки (NFR-CLEAN-03)|
|refresh_tokens|user_id|B-tree|Отзыв всех сессий пользователя|
|refresh_tokens|expires_at|B-tree|Задача очистки (NFR-CLEAN-02)|
|verification_tokens|user_id, type|B-tree|Поиск токенов пользователя|
|verification_tokens|expires_at|B-tree|Задача очистки (NFR-CLEAN-02)|

### 5.5 Денормализация

Таблица `note_chunks` содержит `user_id`, дублирующий данные из `notes`. Обоснование: все поисковые запросы фильтруют по user_id, прямое поле позволяет использовать B-tree индекс без JOIN с таблицей notes. При soft delete заметки чанки остаются в таблице — поиск фильтрует удалённые заметки через JOIN с notes по полю `deleted_at`. При hard delete — чанки удаляются каскадно.

### 5.6 Каскадное удаление

|Событие|Поведение|
|---|---|
|Soft delete заметки|Теги (note_tags) и чанки (note_chunks) сохраняются для возможности восстановления; поиск фильтрует удалённые заметки через JOIN по deleted_at|
|Восстановление заметки|deleted_at сбрасывается в NULL; чанки снова участвуют в поиске без пересчёта|
|Hard delete заметки|Каскадно удаляются note_tags, note_chunks, embedding_queue|
|Удаление пользователя|Каскадно удаляются все связанные данные: notes, tags, refresh_tokens, verification_tokens, chat_sessions (с chat_messages)|
|Удаление тега|Удаляются записи в note_tags. Заметки не затрагиваются|

### 5.7 Полнотекстовый поиск

Используется конфигурация `simple` для `to_tsvector` / `to_tsquery`. Обоснование: не зависит от языка, не применяет стемминг, корректно работает с мультиязычным контентом (кириллица + латиница). Поиск выполняется по точным словоформам.

GIN-индекс строится по полю content. Заголовок включается в поиск через конкатенацию при запросе.

### 5.8 Миграции

Миграции управляются через Alembic. При первом запуске применяются автоматически (SRS NFR-DEPLOY-03). Seed-скрипт создаёт администратора из переменных окружения.

### 5.9 Эволюция JSONB-структур

Поле `chat_messages.actions` хранит proposals и pending_confirmations в формате JSONB (структура определена в [[AIS#2. Хранение данных]]). Формат эволюционирует по правилу **append-only**: новые типы и поля могут добавляться, существующие типы и поля не переименовываются и не удаляются. Это гарантирует обратную совместимость при десериализации старых записей без миграции данных.

---
<div class="page-break" style="page-break-before: always;"></div>

## 6. Embedding

### 6.1 Обзор

Система использует векторные представления (embeddings) текста заметок для семантического поиска через AI-ассистента. Генерация embeddings выполняется через RouterAI (внешний API). Вектора хранятся в PostgreSQL с расширением pgvector.

### 6.2 Выбор модели

⚠️ **Конкретная модель определяется доступностью в RouterAI. Параметры ниже (размерность, max sequence length) зависят от выбранной модели и фиксируются перед началом разработки. Смена модели требует пересчёта всех векторов ([[SRS#6.1 Ограничения]]).**

Требования к модели:

|Критерий|Требование| Обоснование                                                                   |
| ------------------- | -------------------- | ----------------------------------------------------------------------------- |
|Мультиязычность|Русский + английский| ([[SRS#3.3 Характеристики пользователя]]): заметки преимущественно на русском |
|Размерность|2560 (default)| Конфигурируется через `EMBEDDING_DIMENSIONS`; определяется выбранной моделью ([[CPS#5.4 Очередь embedding]]) |
|Max sequence length|≥ 512 токенов| Покрытие одного чанка с запасом                                               |

### 6.3 Стратегия chunking

Заметки разбиваются на чанки фиксированного размера перед генерацией embeddings.

| Параметр         | Значение          | Обоснование                                                   |
| ---------------- | ----------------- | ------------------------------------------------------------- |
| Размер чанка     | 500 токенов       | Стандартный размер для RAG; обеспечивает достаточный контекст |
| Overlap          | 50 токенов        | 10% перекрытие; сохраняет контекст на границах                |
| Префикс          | Заголовок заметки | Включается в начало каждого чанка для контекста               |
| Короткие заметки | Один чанк целиком | Заметки, не превышающие размер чанка, не разбиваются          |
| Пересчёт         | Полный            | При редактировании заметки все её чанки пересоздаются         |

Оценка объёма при максимальной нагрузке (25 пользователей × 3000 заметок):

|Сценарий|Чанков/заметка|Всего чанков|Объём векторов (при 2560 dim)|
|---|---|---|---|
|Реалистичный|~2|~150 000|~1.5 ГБ|
|Worst case|~15|~1 125 000|~11 ГБ|

### 6.4 pgvector

|Параметр|Значение|Обоснование|
|---|---|---|
|Тип индекса|HNSW|Не требует переобучения при росте данных; при объёмах до 1М записей разница с ivfflat минимальна|
|Soft delete фильтрация|JOIN с notes по deleted_at при поиске|Чанки удалённых заметок исключаются через JOIN вместо partial index|
|Метрика расстояния|Cosine|Стандарт для text embeddings; нормализация длины вектора|
<div class="page-break" style="page-break-before: always;"></div>

### 6.5 Очередь генерации


```mermaid
stateDiagram-v2
    [*] --> pending: Заметка сохранена
    pending --> processing: Worker подхватил
    processing --> [*]: Успех → запись удаляется
    processing --> pending: Ошибка, attempts < max
    processing --> failed: Ошибка, attempts ≥ max
    pending --> pending: Повторное редактирование → attempts сброшен
```

**Поведение:**

- При создании/редактировании заметки notes.service пишет запись в embedding_queue (outbox)
- UNIQUE constraint на note_id: повторное редактирование обновляет существующую запись, сбрасывает attempts и status в pending
- Worker периодически опрашивает таблицу, берёт задачи со статусом pending
- При успешной генерации: старые чанки удаляются, новые записываются в note_chunks, задача удаляется из очереди
- При ошибке: attempts инкрементируется, status возвращается в pending
- После исчерпания попыток ([[CPS#5.4 Очередь embedding]]): status = failed, администратор отслеживает через системную статистику (FR-ADMIN-05)
- Backoff - линейный. При масштабировании должен быть переведен в экспоненциальный

### 6.6 Soft delete заметки

При soft delete заметки чанки в `note_chunks` не удаляются и не помечаются флагом. Поиск исключает их через JOIN с `notes` по полю `deleted_at IS NOT NULL`. При восстановлении заметки чанки снова участвуют в поиске без пересчёта. При hard delete — каскадно удаляются вместе с заметкой.

---
## 7. AI-ассистент

Всю информацию смотри здесь [[AIS]].

---
<div class="page-break" style="page-break-before: always;"></div>

## 8. Frontend

### 8.1 Стек

|Технология|Назначение|
|---|---|
|React|UI-фреймворк|
|TypeScript|Типизация|
|Vite|Сборка, dev-сервер|

В production frontend собирается в статику и раздаётся через Nginx.

### 8.2 Markdown-редактор

Редактор заметок с пререндерингом Markdown (SRS FR-NOTES-02). Пользователь видит отформатированный текст в процессе набора (как в Obsidian), а не split-view с отдельной панелью превью.

Поддерживаемые элементы: заголовки, списки, жирный/курсив, код, цитаты, горизонтальные линии, таблицы, ссылки. Изображения и другие нетекстовые элементы не поддерживаются.

### 8.3 Автосохранение

Заметка сохраняется автоматически с интервалом, определённым в [[CPS#5.2 Заметки]]. Сохранение происходит только при наличии изменений (dirty flag). При ошибке сети клиент отображает индикатор и повторяет при следующем цикле.

### 8.4 Санитайзация

Markdown-контент санитайзится в двух точках (NFR-SEC-06):

**Сервер (первая линия защиты):** notes.service санитайзирует `content` и `title` при каждом сохранении (включая apply proposals от AI-ассистента). Опасные HTML-элементы (`<script>`, `<iframe>`, обработчики событий) удаляются. Библиотека: `nh3`.

**Клиент (вторая линия защиты):** Markdown-контент санитайзится при рендеринге. Опасные HTML-элементы экранируются и отображаются как обычный текст.

### 8.5 Аутентификация на клиенте

Access token хранится в памяти (JavaScript-переменная). При обновлении страницы токен теряется - клиент автоматически запрашивает новый через refresh-эндпоинт (cookie отправляется автоматически).

### 8.6 Взаимодействие с AI-ассистентом

Ответы ассистента доставляются через SSE-потоки, встроенные в POST-запросы (см. 8.7). Типы событий и формат payload определяются в [[AIS#11. SSE-события]]. Proposals отображаются как интерактивные элементы после завершения стриминга.

<div class="page-break" style="page-break-before: always;"></div>

### 8.7 SSE-доставка событий AI-ассистента

AI-события доставляются как inline SSE-поток в рамках двух POST-эндпоинтов (см. [[AIS#11. SSE-события]]):

- `POST /api/ai/sessions/{id}/messages` — стриминг ответа Planner
- `POST /api/ai/sessions/{id}/confirm/{confirmation_id}` — стриминг proposals после bulk-подтверждения

Каждый SSE-поток существует в рамках одного HTTP-запроса и завершается событием `ai:done`. Отдельного persistent SSE-канала (`GET /api/events`) в реализации нет.

**Presence**

Presence (отслеживание активного клиента) реализован через Redis. Backend регистрирует presence-ключ при каждом запросе и обновляет TTL. При открытии второго клиента backend проверяет наличие presence-ключа в Redis — если активная сессия уже есть, новый клиент переходит в read-only режим.

**Подключение второго клиента**

Если активный клиент уже существует, новый клиент переходит в read-only режим: доступен просмотр заметок и истории AI-чата, редактирование, создание, удаление заметок и отправка сообщений в AI-чат заблокированы. Клиент отображает баннер с кнопкой «Продолжить здесь».

**Takeover**

Пользователь нажимает «Продолжить здесь» — клиент отправляет запрос на takeover. Backend перезаписывает presence-ключ и публикует `session_taken` через Redis Pub/Sub. Предыдущий активный клиент получает событие и переходит в read-only.

---
<div class="page-break" style="page-break-before: always;"></div>

## 9. Worker

### 9.1 Обзор

Worker — отдельный контейнер, выполняющий фоновые задачи. Использует тот же код backend-приложения, запущенный с другим entrypoint.

### 9.2 Задачи

Каждая задача выполняется с собственным интервалом, задаваемым через переменные окружения ([[CPS#5.5 Worker]]).

|Задача|Описание|
|---|---|
|Обработка embedding_queue|Берёт задачи со статусом `pending`, генерирует вектора через RouterAI, записывает в note_chunks|
|Очистка неподтверждённых аккаунтов|Удаляет пользователей с is_email_confirmed = false старше срока ([[CPS#5.1 Сессии и токены]])|
|Очистка истёкших токенов|Удаляет refresh_tokens и verification_tokens с expires_at < now()|
|Очистка чат-сессий|Удаляет chat_sessions с last_message_at старше срока ([[CPS#5.3 AI-ассистент]]) с каскадным удалением chat_messages|
|Hard delete заметок|Удаляет notes с deleted_at старше срока ([[CPS#5.2 Заметки]]) с каскадным удалением note_tags, note_chunks, embedding_queue|

### 9.3 Обработка embedding_queue

1. SELECT задачи со статусом `pending` **и `updated_at` старше debounce-интервала ([[CPS#5.4 Очередь embedding]])**
2. Установить статус `processing`
3. Получить content и title заметки из notes
4. Разбить на чанки (стратегия — раздел 6.3)
5. Отправить чанки в RouterAI, получить вектора
6. Удалить старые записи из note_chunks для этой заметки
7. Записать новые чанки с векторами в note_chunks
8. Удалить задачу из embedding_queue

При ошибке на шагах 5–7: инкрементировать attempts, вернуть статус в `pending`. Retry с линейным backoff (интервал × attempts). После исчерпания попыток ([[CPS#5.4 Очередь embedding]]) — статус `failed`.

---
<div class="page-break" style="page-break-before: always;"></div>

## 10. Развёртывание

### 10.1 Контейнеры

```mermaid
graph TD
    subgraph Docker Compose
        nginx[Nginx<br/>порт 80/443]
        backend[Backend<br/>FastAPI + Uvicorn]
        frontend[Frontend<br/>React статика]
        worker[Worker]
        postgres[(PostgreSQL<br/>+ pgvector)]
        redis[(Redis)]
    end

    nginx -->|/api| backend
    nginx -->|/| frontend
    backend --> postgres
    backend --> redis
    worker --> postgres
```

| Контейнер | Образ                    | Описание                                       |
| --------- | ------------------------ | ---------------------------------------------- |
| nginx     | nginx:alpine             | Reverse proxy, HTTPS-терминация, маршрутизация |
| backend   | Собственный Dockerfile   | FastAPI-приложение                             |
| frontend  | nginx:alpine             | Собранная React-статика                        |
| worker    | Тот же образ что backend | Другой entrypoint                              |
| postgres  | pgvector/pgvector:pg16   | PostgreSQL с расширением pgvector              |
| redis     | redis:alpine             | Pub/Sub, rate limiting, presence               |
### 10.2 Nginx

**Маршрутизация**

|Путь|Назначение|
|---|---|
|`/api/*`|Проксирование в backend|
|`/`|Статика frontend|

HTTPS-терминация на уровне Nginx. Между Nginx и backend — HTTP внутри Docker-сети. Nginx перезаписывает заголовок `X-Forwarded-For` реальным IP клиента (см. раздел 4.7).

Для SSE-эндпоинта отключается буферизация (`proxy_buffering off`), чтобы события доставлялись клиенту без задержки.

SSL-сертификаты: Let's Encrypt, автопродление через certbot.

<div class="page-break" style="page-break-before: always;"></div>

### 10.3 Переменные окружения

| Переменная                 | Описание                                        | Пример                                         |
| -------------------------- | ----------------------------------------------- | ---------------------------------------------- |
| `DATABASE_URL`             | Строка подключения к PostgreSQL                 | `postgresql://user:pass@postgres:5432/nocturn` |
| `JWT_SECRET`               | Секретный ключ для подписи JWT                  | Случайная строка ≥ 32 символа                  |
| `ROUTERAI_API_KEY`         | Ключ API RouterAI                               |                                                |
| `ROUTERAI_BASE_URL`        | Базовый URL RouterAI                            | `https://api.routerai.ru/v1`                   |
| `ROUTERAI_LLM_MODEL`       | Модель для Planner                              |                                                |
| `ROUTERAI_EXECUTOR_MODEL`  | Модель для Executor                             |                                                |
| `ROUTERAI_EMBEDDING_MODEL` | Модель для embeddings                           |                                                |
| `EMAIL_PROVIDER`           | Провайдер email                                 | `resend` / `brevo`                             |
| `EMAIL_API_KEY`            | Ключ API email-провайдера                       |                                                |
| `EMAIL_FROM`               | Адрес отправителя                               | `noreply@nocturn.example.com`                  |
| `ADMIN_EMAIL`              | Email первого администратора                    |                                                |
| `ADMIN_PASSWORD`           | Пароль первого администратора                   |                                                |
| `ADMIN_NICKNAME`           | Никнейм первого администратора                  |                                                |
| `FRONTEND_URL`             | URL фронтенда (для CORS и ссылок в письмах)     | `https://nocturn.example.com`                  |
| `REDIS_URL`                | Строка подключения к Redis                      | redis://redis:6379/0                           |
| PLANNER_CHARS_PER_TOKEN    | Коэффициент символов на токен для аппроксимации | Подбирается под конкретную модель              |

### 10.4 Первый запуск

```mermaid
flowchart LR
    Start([docker-compose up]) --> Postgres[PostgreSQL запускается]
    Postgres --> Migrations[Backend: Alembic применяет миграции]
    Migrations --> Seed{Админ существует?}
    Seed -->|Нет| CreateAdmin[Создать администратора из env]
    Seed -->|Да| Skip[Пропустить]
    CreateAdmin --> Ready([Система готова])
    Skip --> Ready
```

### 10.5 Volumes

|Volume|Контейнер|Назначение|
|---|---|---|
|`postgres_data`|postgres|Персистентное хранение данных БД|
|`nginx_certs`|nginx|SSL-сертификаты|

---
<div class="page-break" style="page-break-before: always;"></div>

## 11. Принятые trade-offs

| #   | Решение                                                                                 | Альтернатива                                    | Обоснование                                                                                                                                                                                                                                               |
| --- | --------------------------------------------------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Модульный монолит                                                                       | Микросервисы                                    | Один разработчик, 25 пользователей. Микросервисы вносят сложность (межсервисная коммуникация, распределённые транзакции, несколько деплойментов) без пропорциональной выгоды. Модули с чёткими границами позволяют вынести сервис позже при необходимости |
| 2   | Окно доступа при блокировке (до TTL access token)                                       | Проверка is_active на каждый запрос             | Access token (JWT) валидируется без обращения к БД. Добавление проверки is_active вводит зависимость от БД на каждый запрос. При коротком TTL access token ([[CPS#5.1 Сессии и токены]]) окно приемлемо                                                    |
| 3   | Денормализация user_id в note_chunks                                                    | JOIN с notes при каждом поиске                  | Все поисковые запросы фильтруют по user_id. Прямое поле позволяет использовать B-tree индекс без JOIN для фильтрации по пользователю. Soft delete проверяется через JOIN с notes по deleted_at                                                            |
| 4   | Полнотекстовый поиск с конфигурацией `simple`                                           | Языко-зависимая конфигурация (russian, english) | `simple` не применяет стемминг, но корректно работает с мультиязычным контентом без определения языка. Поиск по точным словоформам. Можно переключить на языко-зависимую конфигурацию позже                                                               |
| 5   | RouterAI как единая точка для LLM и Embedding                                           | Разные провайдеры для LLM и embedding           | Single point of failure: при недоступности RouterAI не работают ни ассистент, ни семантический поиск. CRUD заметок работает. Принято ради простоты конфигурации и единого API                                                                             |
| 6   | Refresh token в HttpOnly cookie (SameSite=Strict)                                       | Хранение в localStorage                         | SameSite=Strict исключает CSRF, HttpOnly исключает XSS-доступ к токену. Требует, чтобы frontend и backend были на одном origin                                                                                                                            |
| 7   | Access token в памяти (JS-переменная)                                                   | Хранение в localStorage / sessionStorage        | Теряется при обновлении страницы (требует refresh), но недоступен для XSS. Для персонального сервиса частый refresh приемлем                                                                                                                              |
| 8   | attached_note_ids без FK constraint                                                       | FK → notes                                      | Отсутствие FK позволяет не блокировать удаление заметок. Невалидные UUID игнорируются при отправке сообщения; при просмотре истории клиент отображает «Заметка удалена»                                                                                                                   |
| 9   | Зависшие задачи в embedding_queue (status = processing) не обрабатываются автоматически | Таймаут зависших задач                          | При крэше worker'а задача остаётся в processing. Починится автоматически при следующем редактировании заметки пользователем. Для одного worker'а и 25 пользователей вероятность и последствия минимальны                                                  |
| 10  | Линейный backoff в embedding_queue                                                      | Экспоненциальный backoff                        | При одном worker'е линейный backoff достаточен. При масштабировании на несколько worker'ов потребуется переход на экспоненциальный                                                                                                                        |
| 11  | Single active client с read-only для остальных     | Multi-client sync (CRDT/OT)           | CRDT/OT — непропорциональная сложность для одного разработчика и 25 пользователей с персональными заметками. Single active client исключает конфликты by design                   |
| 12  | Redis — fail-closed на запись, fail-open на чтение | Fail-open на всё / Fail-closed на всё | Полный fail-open теряет гарантию single client — возможны конфликты записи. Полный fail-closed блокирует даже чтение, что нарушает принцип graceful degradation. Компромисс: чтение работает, запись блокируется |
| 13 | Redis как обязательная внутренняя зависимость|Rate limiting и presence in-memory|In-memory rate limiting и presence делают backend stateful, нарушая NFR-SCALE-02. Redis добавляет точку отказа, но обеспечивает stateless backend и корректную работу при горизонтальном масштабировании|

---

*Документ подлежит обновлению при изменении требований. Версия фиксируется при каждом изменении.*
