# Nocturn

**Распределённое веб-приложение с ИИ-ассистентом — и полный контур его эксплуатации: SLO, метрики, алерты, runbook'и**

[![Backend CI](https://github.com/CaseyJohnson-RS/Nocturn/actions/workflows/backend_ci.yml/badge.svg)](https://github.com/CaseyJohnson-RS/Nocturn/actions)
[![Frontend CI](https://github.com/CaseyJohnson-RS/Nocturn/actions/workflows/frontend_ci.yml/badge.svg)](https://github.com/CaseyJohnson-RS/Nocturn/actions)
[![Observability CI](https://github.com/CaseyJohnson-RS/Nocturn/actions/workflows/observability_ci.yml/badge.svg)](https://github.com/CaseyJohnson-RS/Nocturn/actions)

![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React_19-61DAFB?style=flat&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL_+_pgvector-4169E1?style=flat&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=flat&logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-F46800?style=flat&logo=grafana&logoColor=white)
![Loki](https://img.shields.io/badge/Loki-F5A623?style=flat&logo=grafana&logoColor=white)
![k6](https://img.shields.io/badge/k6-7D64FF?style=flat&logo=k6&logoColor=white)

🌐 **[Открыть демо](https://frontend-uko1.onrender.com/)**

---

Nocturn — облачный Markdown-редактор, в котором ИИ-ассистент не просто отвечает на вопросы о заметках, а создаёт, редактирует и удаляет их прямо из чата, предлагая изменения на подтверждение.

С точки зрения эксплуатации это система из **шести взаимодействующих компонентов** с асинхронной очередью, потоковыми SSE-соединениями и внешним LLM-провайдером, который может деградировать в любой момент. Такая система интересна не тем, что она делает, а тем, **как понять, что она сломалась, и что с этим делать**.

Именно про это большая часть репозитория.

```bash
make observability-up   # приложение + Prometheus + Grafana + Loki + Alertmanager
```

---

## Что здесь стоит посмотреть

Если вы открыли репозиторий, чтобы оценить инженерный подход, — вот пять мест, где принимались неочевидные решения. У каждого есть обоснование в коде или документации.

| Решение | Где | Почему так |
|---|---|---|
| Латентность измеряется до **заголовков** ответа, а не до последнего байта тела | [`middleware.py`](backend/src/app/common/observability/middleware.py) | Иначе каждый SSE-стрим падал бы в верхний бакет и уничтожал латентный SLI |
| Порог латентного SLO — ровно **250 мс**, граница бакета гистограммы | [`docs/SLO.md`](docs/SLO.md) | Любое другое значение Prometheus интерполирует, и SLI превращается в оценку |
| Лейбл `path` — **шаблон роута**, а 404-ы схлопываются в `<unmatched>` | [`middleware.py`](backend/src/app/common/observability/middleware.py) | Сканер чужих админок не должен взрывать кардинальность и жечь бюджет ошибок |
| Отдельный SLI **свежести поиска**, невидимый в HTTP-трафике | [`docs/SLO.md`](docs/SLO.md) | Очередь эмбеддингов может встать намертво при 100% доступности API |
| Алерты — **multi-window multi-burn-rate**, а не пороги | [`rules/slo.yml`](observability/prometheus/rules/slo.yml) | Длинное окно душит шум, короткое гасит алерт после устранения причины |

Плюс: CI **падает, если у алерта нет runbook'а или severity** — [`observability_ci.yml`](.github/workflows/observability_ci.yml).

## Скриншоты

<!-- Скриншот: Grafana — Service Overview (RED) -->
<!-- ![RED-дашборд](docs/screenshots/grafana-overview.png) -->

<!-- Скриншот: Grafana — SLO & Error Budget -->
<!-- ![SLO и error budget](docs/screenshots/grafana-slo.png) -->

<!-- Скриншот: сработавший burn-rate алерт в Alertmanager -->
<!-- ![Алерт](docs/screenshots/alert.png) -->

<!-- Скриншот: главный экран приложения -->
<!-- ![Главный экран](docs/screenshots/main.png) -->

---

# Эксплуатация

## SLO

Определения, обоснование порогов и политика error budget — в **[docs/SLO.md](docs/SLO.md)**.

| SLO | Цель | Почему именно так |
|---|---|---|
| Доступность API | 99.5% не-5xx за 30 дней | Один инстанс без резервирования, деплой рестартует процесс. Три девятки при такой архитектуре — обман себя |
| Латентность CRUD | 99% быстрее 250 мс | Порог совпадает с границей бакета — SLI не интерполируется |
| Отзывчивость ИИ | p95 time-to-first-token < 3 с | Полное время генерации зависит от длины ответа и ничего не говорит о нашем качестве |
| Свежесть поиска | заметка индексируется < 60 с | Единственный SLI, полностью невидимый в кодах ответа |

Бюджет ошибок 0.5% — это 3 часа 39 минут полной недоступности в месяц. Политика расходования бюджета (когда замораживать фичи) описана там же.

## Модель отказов

Что именно ломается у пользователя при отказе каждого компонента — от этого зависит severity и формулировка в статус-канале.

| Отказал | Не работает | Продолжает работать | Severity |
|---|---|---|---|
| **Postgres** | Всё | — | `page` |
| **Redis** | Запись заметок (fail closed → 503), rate limiting | Чтение, ИИ-чат | `page` |
| **LLM-провайдер** | Чат, предложения правок, индексация новых заметок | Весь CRUD, поиск по старым заметкам, логин | `ticket` |
| **Воркер** | Индексация, retention-очистка | Всё остальное — API этого не замечает | `page` при зависании |

Деградация Redis спроектирована явно: на `GET`/`HEAD` rate limiter пропускает запрос (**fail open** — доступность важнее ограничения), на записи возвращает 503 (**fail closed** — неучтённые записи хуже отказа). Обе ветки инкрементят `nocturn_rate_limit_errors_total`, поэтому тихой деградации не бывает.

Отказ LLM-провайдера — единственный, который не эскалируется как `page`: рычага на чужой сервис у дежурного нет, и задача сводится к тому, чтобы убедиться, что ИИ-часть не утягивает за собой CRUD.

## Метрики

Приложение отдаёт метрики на `/metrics` (наружу через nginx закрыт), воркер — на отдельном порту `9101`, потому что своего HTTP-сервера у него нет.

Кроме стандартных RED-метрик собирается то, что специфично именно для этой системы:

| Метрика | Что показывает |
|---|---|
| `nocturn_llm_time_to_first_token_seconds` | То, что пользователь ощущает как «подвис» в чате |
| `nocturn_embedding_queue_oldest_pending_seconds` | Верхняя граница отставания семантического поиска |
| `nocturn_worker_last_loop_timestamp_seconds` | Heartbeat воркера — без него зависание видно только по жалобе |
| `nocturn_rate_limit_errors_total` | Деградация rate limiter'а с разбивкой fail-open / fail-closed |
| `nocturn_dependency_up` | Результат проб готовности по каждой зависимости |
| `nocturn_sse_active_streams` | Открытые SSE-соединения — каждое держит слот |
| `nocturn_build_info` | Версия и коммит; по нему сопоставляется деплой с началом инцидента |

## Логи

Structured JSON в stdout, сбор Promtail → Loki. Один формат у API и у воркера, поэтому оба потока читаются одним запросом.

У каждой строки есть `request_id`: он берётся из заголовка `X-Request-ID` (или генерируется), живёт в contextvar и поэтому попадает в записи из глубины сервисов без проброса через сигнатуры. Путь от «этот запрос был медленным» до всех его логов:

```logql
{compose_service="backend"} | json | request_id = "<REQUEST_ID>"
```

`request_id` намеренно **не** является лейблом Loki — это создало бы по стриму на каждый запрос и положило бы хранилище. Лейблами становятся только `level` и `service`.

## Пробы

| Endpoint | Назначение |
|---|---|
| `/livez` | Процесс жив. Сознательно **не трогает зависимости**: иначе блип БД приводил бы к рестарт-циклу здорового процесса |
| `/readyz` | Инстанс готов принимать трафик: проверяет Postgres и Redis, отдаёт 503 и **называет** отказавшую зависимость |
| `/metrics` | Скрейп Prometheus, наружу закрыт |

Результат `/readyz` кэшируется на 2 секунды — проба, которую опрашивают каждую секунду, не должна становиться собственным источником нагрузки.

## Алертинг и runbook'и

Алерты делятся на два класса:

* **Symptom-based** ([`slo.yml`](observability/prometheus/rules/slo.yml)) — выгорание бюджета ошибок. Отвечают на вопрос «страдают ли пользователи».
* **Cause-based** ([`alerts.yml`](observability/prometheus/rules/alerts.yml)) — то, что SLO структурно увидеть не может: зависший воркер не создаёт HTTP-трафика, поэтому ни одно отношение не сдвинется.

У каждого алерта есть `severity` и `runbook_url`, ссылка приходит прямо в уведомление. Все runbook'и — в **[docs/runbooks/](docs/runbooks/)**, по одному на алерт. Каждый отвечает ровно на четыре вопроса:

1. Что сломано **у пользователя** (impact, а не текст алерта)
2. Как понять причину — конкретные запросы и команды, копируемые как есть
3. Как остановить кровь — часто без устранения root cause
4. Когда эскалировать — условие, а не «если не помогло»

Alertmanager разводит `page` и `ticket` по разным маршрутам и подавляет производные алерты: при `NocturnApiDown` burn-rate алерты — это тот же инцидент, а не второй.

## Проверка системы, а не кода

```bash
make smoke-test    # пробы + реальный пользовательский сценарий; гейт деплоя
make load-test     # k6, пороги которого — это SLO из docs/SLO.md
make check-rules   # валидация правил Prometheus до коммита
```

Нагрузочный тест [`load/k6-baseline.js`](load/k6-baseline.js) выходит на плато и держит его: одиночный спайк ничего не говорит ни об исчерпании пула, ни о медленной утечке. Пороги взяты из SLO, поэтому провалившийся прогон означает «эта сборка жгла бы бюджет в проде», а не «показалось медленно».

## Что происходит при деплое

Пайплайн не считает деплой успешным по коду ответа deploy hook — хук, тихо возвращающий 4xx, выглядит ровно как успешный деплой.

```
lint → тесты → deploy hook (с проверкой статуса)
     → опрос /readyz нового инстанса (до 10 минут)
     → smoke-тест
```

Миграции вынесены из старта приложения в отдельный шаг `make migrate`: при нескольких репликах каждая гонялась бы за `alembic upgrade head`, а битая миграция валила бы работающий сервис вместо одного шага деплоя. Для платформ без release-фазы поведение возвращается флагом `RUN_MIGRATIONS_ON_STARTUP=true` (это дефолт).

## Локальный стенд

```bash
make observability-up
```

| Что | Где |
|---|---|
| Приложение | http://localhost |
| Grafana | http://localhost:3001 · `admin` / `admin` |
| Prometheus | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |

В Grafana три предзагруженных дашборда (папка **Nocturn**), заданных как код — правки через UI перезаписываются при рестарте, экспортируйте JSON и коммитьте:

* **Service Overview (RED)** — первый дашборд, который открывают в инциденте
* **SLO & Error Budget** — остаток бюджета и burn rate по окнам
* **Worker & Embedding Queue** — асинхронная половина системы

Остановить: `make observability-down`.

---

# Приложение

## Возможности

### Редактор заметок
- Markdown с подсветкой синтаксиса и мгновенным превью (редактор / превью / split-view)
- Автосохранение и обнаружение конфликтов редактирования через счётчик версий
- Система тегов для фильтрации и организации
- Мягкое удаление в корзину с хранением 30 дней и восстановлением

### ИИ-ассистент
- Чат с потоковой передачей ответов (SSE-стриминг)
- Предложения действий с подтверждением: создать / отредактировать / удалить заметку, добавить или снять теги
- Массовые операции над несколькими заметками сразу
- Прикрепление заметок к контексту чата
- Семантический поиск по смыслу запроса

### Пользователи и безопасность
- Регистрация с подтверждением email, сброс пароля
- JWT-аутентификация с ротацией refresh-токенов
- Rate limiting по всем группам эндпоинтов
- Тёмная и светлая темы, интернационализация (RU / EN)

### Администрирование
- Панель управления пользователями: просмотр, блокировка, смена роли, удаление аккаунта

## Технические детали

### SSE-стриминг
Ответы ассистента доставляются через Server-Sent Events. Бэкенд отправляет события (`ai:text_delta`, `ai:proposal`, `ai:done`) по мере генерации — фронтенд обрабатывает поток инкрементально.

### Собственные AI Tools
Кастомный `ToolExecutor` по аналогии с function calling. ИИ вызывает инструменты (`create_note`, `edit_note`, `delete_note`, `add_tags`, `remove_tags` и др.), результаты формируются в `Proposal`-объекты и уходят на фронтенд через SSE для подтверждения пользователем.

### RAG и семантический поиск
Заметки разбиваются на чанки, эмбеддируются и сохраняются в PostgreSQL с `pgvector`. Поиск — по косинусному сходству. Индексация асинхронная, в фоновом воркере, с очередью, дебаунсом и retry.

### Фоновый воркер
Отдельный процесс обрабатывает очередь эмбеддингов и периодически удаляет просроченные данные. Обрабатывает `SIGTERM` и завершает текущую итерацию, а задачи, брошенные упавшим воркером в статусе `processing`, через 15 минут автоматически возвращаются в очередь reaper'ом — иначе они висели бы там вечно.

### Устойчивость к внешнему LLM
Таймауты к провайдеру заданы явно (`LLM_CONNECT_TIMEOUT_SECONDS`, `LLM_READ_TIMEOUT_SECONDS`) — дефолт SDK составляет 10 минут, и один зависший запрос держал бы SSE-соединение и слот воркера всё это время. Деградация одного провайдера не должна превращаться в отказ всего API.

### JWT + Redis
Аутентификация через access/refresh токены. Redis — для rate limiting (скользящее окно) и временных данных сессий.

## Архитектура

```
                          :80/:443
                             │
                           Nginx  ──── /livez, /readyz ──┐
                          ╱     ╲                        │
                  /api/*          /*                     │
                    │              │                     │
            FastAPI backend    React frontend            │
             (Uvicorn:8000)    (static/Nginx:80)         │
              /metrics                                   │
                │      │                                 │
           PostgreSQL  Redis ◄── rate limit              │
           (pgvector)                                    │
                │                                        │
              Worker ── /metrics:9101                    │
        (эмбеддинги + retention)                         │
                │                                        │
         RouterAI (внешний LLM)                          │
                                                         │
   ─────────────────── контур наблюдаемости ─────────────┘
     Prometheus ◄─ скрейп ─ backend, worker, pg-exporter, redis-exporter
          │
          ├── Alertmanager ── page / ticket
          └── Grafana ◄── Loki ◄── Promtail ◄── stdout всех контейнеров
```

Контур наблюдаемости живёт в **отдельном** compose-файле: приложение обязано работать без него, и сломанный мониторинг не должен иметь возможности уронить продукт.

**Модули бэкенда** следуют единому паттерну `models → repository → service → router → schemas`:

```
backend/src/app/modules/
  auth/       Регистрация, вход, JWT, подтверждение email
  profile/    Никнейм, смена пароля, удаление аккаунта
  notes/      CRUD, мягкое удаление, теги, версионирование
  tags/       Пользовательские метки
  rag/        Чанкинг, эмбеддинги, семантический поиск
  ai/         Чат-сессии, SSE-стриминг, proposals, bulk-операции
  admin/      Управление пользователями и ролями
  system/     Пробы и экспорт метрик
```

## Стек технологий

| Слой | Технологии |
|------|-----------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, Zustand, TanStack Query, CodeMirror 6, Radix UI |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic |
| База данных | PostgreSQL 16 + pgvector |
| Кеш / Rate limit | Redis |
| LLM | RouterAI (OpenAI-совместимый API) |
| Email | Resend |
| Аутентификация | JWT (PyJWT) + Argon2 |
| Прокси | Nginx |
| Метрики и алерты | Prometheus, Alertmanager, postgres/redis exporters |
| Логи | Loki + Promtail |
| Дашборды | Grafana (provisioning as code) |
| Нагрузка | k6 |
| Контейнеризация | Docker Compose |
| CI/CD | GitHub Actions → Render |

---

# Запуск

## Требования

- [Docker](https://docs.docker.com/get-docker/) и Docker Compose
- `make` (для команд ниже; всё то же можно выполнить напрямую через `docker compose`)

## 1. Клонировать и настроить

```bash
git clone https://github.com/CaseyJohnson-RS/Nocturn && cd Nocturn
cp .env.example .env
```

Открыть `.env` и заполнить обязательные поля:

```dotenv
# JWT — любая случайная строка длиной от 32 символов
JWT_SECRET=your-random-secret-here

# RouterAI — ключ и модели для работы ИИ-ассистента
# Получить ключ и список моделей: https://routerai.ru
ROUTERAI_API_KEY=your-routerai-key
ROUTERAI_LLM_MODEL=your-llm-model           # основная модель (чат)
ROUTERAI_EXECUTOR_MODEL=your-exec-model     # модель для tool calling
ROUTERAI_EMBEDDING_MODEL=your-emb-model     # модель для эмбеддингов

# Resend — для отправки писем (подтверждение email, сброс пароля)
# Получить ключ: https://resend.com
EMAIL_API_KEY=re_your_resend_key
EMAIL_FROM=noreply@yourdomain.com
```

> **Без Resend** приложение запустится, но письма отправляться не будут. Для локального тестирования есть демо-аккаунт, указанный на странице входа.
>
> **Без RouterAI** работает всё, кроме чата и семантического поиска: заметки, теги, корзина и авторизация от LLM не зависят.

## 2. Запустить

```bash
make run-app             # только приложение
make observability-up    # приложение + весь контур наблюдаемости
```

Приложение — **http://localhost**, документация API — **http://localhost/api/docs**.

При первом запуске выполняются Alembic-миграции и создаётся аккаунт администратора (`ADMIN_EMAIL` / `ADMIN_PASSWORD` из `.env`). Чтобы прогонять миграции отдельным шагом, как в проде, поставьте `RUN_MIGRATIONS_ON_STARTUP=false` и вызывайте `make migrate`.

## 3. Проверить

```bash
make smoke-test
```

## 4. Остановить

```bash
make observability-down       # остановить всё, данные сохранить
docker compose down -v        # + удалить данные БД
```

---

# Разработка

## Фронтенд (без Docker)

```bash
cd frontend
npm install
npm run dev
```

Vite запускается на `http://localhost:5173` и проксирует `/api/*` на `http://localhost:80`, поэтому Docker-бэкенд должен быть запущен.

## Тестирование

```bash
make backend-test-unit          # unit-тесты бэкенда
make backend-test-integration   # интеграционные (поднимут Postgres и Redis)
make backend-test-full          # всё сразу
make frontend-test              # vitest
```

Каждая цель сама поднимает нужную инфраструктуру, отдельный шаг для этого не нужен.

## Линт и статические проверки

```bash
make backend-lint               # ruff check
cd frontend && npm run build    # tsc -b — типы проверяются сборкой
make check-rules                # promtool: правила Prometheus
```

---

# Конфигурация

Все переменные задаются в `.env` (загружается Docker Compose). Полный список — в [`.env.example`](.env.example).

| Группа | Переменные |
|--------|-----------|
| База данных | `DATABASE_URL`, `DATABASE_SSL_REQUIRE`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW` |
| Redis | `REDIS_URL` |
| JWT | `JWT_SECRET`, `ACCESS_TOKEN_TTL_MINUTES`, `REFRESH_TOKEN_TTL_DAYS` |
| RouterAI | `ROUTERAI_API_KEY`, `ROUTERAI_BASE_URL`, `ROUTERAI_LLM_MODEL`, `ROUTERAI_EXECUTOR_MODEL`, `ROUTERAI_EMBEDDING_MODEL` |
| Таймауты LLM | `LLM_CONNECT_TIMEOUT_SECONDS`, `LLM_READ_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` |
| Email (Resend) | `EMAIL_PROVIDER`, `EMAIL_API_KEY`, `EMAIL_FROM` |
| Сид администратора | `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NICKNAME` |
| Лимиты | `MAX_NOTES_PER_USER`, `MAX_CHAT_SESSIONS_PER_USER`, `TRASH_RETENTION_DAYS` и др. |
| Rate limiting | `RATE_AUTH_PER_MINUTE`, `RATE_CRUD_PER_MINUTE`, `RATE_AI_PER_MINUTE` и др. |
| Воркер | `EMBEDDING_QUEUE_INTERVAL_SECONDS`, `CLEANUP_INTERVAL_SECONDS` |
| Наблюдаемость | `LOG_LEVEL`, `LOG_FORMAT`, `WORKER_METRICS_PORT`, `RUN_MIGRATIONS_ON_STARTUP` |

`DATABASE_SSL_REQUIRE` — `true` для managed-Postgres (Neon), `false` для локального и compose-Postgres, который TLS не умеет вовсе.

`LOG_FORMAT=plain` переключает логи в человекочитаемый вид для локальной отладки; в контейнерах всегда `json`.

# Структура проекта

```
Nocturn/
  backend/
    src/
      app/                    FastAPI-приложение
        common/
          observability/      Логи, метрики, request-id middleware
          database/           Движок и сессии SQLAlchemy
        middleware/           Аутентификация, rate limiting
        modules/              Модули (auth, notes, ai, rag, system и др.)
      worker/                 Фоновые задачи (эмбеддинги, очистка, reaper)
    migrations/               Alembic-миграции
    pyproject.toml            Зависимости Python
  frontend/
    src/
      api/                    HTTP-клиент, типы
      components/             UI-компоненты
      features/               Функциональные модули (chat, notes, tags)
      stores/                 Глобальное состояние (Zustand)
      i18n/                   Переводы (RU / EN)
    package.json              Зависимости Node
  nginx/
    nginx.conf                Обратный прокси; /metrics закрыт наружу
  observability/
    prometheus/               Скрейп-конфиг, SLI-правила, алерты
    alertmanager/             Маршрутизация page / ticket, inhibit-правила
    grafana/                  Датасорсы и дашборды как код
    loki/ promtail/           Хранение и сбор структурных логов
  load/
    k6-baseline.js            Нагрузочный тест, пороги = SLO
  scripts/
    smoke-test.sh             Проверка после деплоя, гейт пайплайна
  docs/
    SLO.md                    Определения SLI/SLO и политика error budget
    runbooks/                 По одному runbook на алерт
  .github/workflows/          CI: backend, frontend, observability
  docker-compose.yml                 Стек приложения
  docker-compose.observability.yml   Контур наблюдаемости (оверлей)
  .env.example                Шаблон переменных окружения
  Makefile                    Команды разработки и эксплуатации
```

# Дальнейшие шаги

Контур эксплуатации закрыт по наблюдаемости и реагированию. Не сделано осознанно, следующим этапом:

- **Инфраструктура как код** — Terraform + Ansible либо k3s с Helm-чартом и GitOps через Argo CD вместо deploy hook
- **Трассировка** — OpenTelemetry поверх FastAPI, SQLAlchemy, httpx; связка trace ↔ логи по `trace_id`
- **Chaos-эксперименты** — падение Redis, исчерпание коннектов, 500-е от LLM, сетевые задержки, каждый оформлен как гипотеза → эксперимент → результат
- **Бэкапы и DR** — WAL в S3-совместимое хранилище, автоматическая проверка восстановления, зафиксированные RTO/RPO
- **Постмортемы** — `docs/postmortems/` по результатам chaos-экспериментов
