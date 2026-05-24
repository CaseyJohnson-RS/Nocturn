# Nocturn

**Облачный Markdown-редактор с ИИ-ассистентом, который умеет управлять вашими заметками**

[![Backend CI](https://github.com/CaseyJohnson-RS/Nocturn/actions/workflows/backend_ci.yml/badge.svg)](https://github.com/CaseyJohnson-RS/Nocturn/actions)
[![Frontend CI](https://github.com/CaseyJohnson-RS/Nocturn/actions/workflows/frontend_ci.yml/badge.svg)](https://github.com/CaseyJohnson-RS/Nocturn/actions)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=flat&logo=python&logoColor=white)
![React](https://img.shields.io/badge/React_19-61DAFB?style=flat&logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)

🌐 **[Открыть демо](https://frontend-uko1.onrender.com/)**

---

Nocturn — полноценное веб-приложение для работы с заметками. ИИ-ассистент не просто отвечает на вопросы о ваших записях — он умеет создавать, редактировать и удалять заметки прямо из чата, предлагая изменения на ваше подтверждение.

## Скриншоты

<!-- Скриншот: главный экран — редактор и боковая панель -->
<!-- ![Главный экран](docs/screenshots/main.png) -->

<!-- GIF: работа ИИ-ассистента — запрос и предложение правки -->
<!-- ![Демо ИИ-ассистента](docs/screenshots/ai-demo.gif) -->

<!-- Скриншот: семантический поиск -->
<!-- ![Поиск](docs/screenshots/search.png) -->

## Возможности

### Редактор заметок
- Markdown с подсветкой синтаксиса и мгновенным превью (три режима: редактор / превью / split-view)
- Автосохранение и обнаружение конфликтов редактирования через счётчик версий
- Система тегов для фильтрации и организации заметок
- Мягкое удаление в корзину с хранением 30 дней и возможностью восстановления

### ИИ-ассистент
- Чат с потоковой передачей ответов в реальном времени (SSE-стриминг)
- Предложения действий с подтверждением: создать / отредактировать / удалить заметку, добавить или снять теги
- Массовые операции над несколькими заметками сразу
- Прикрепление заметок к контексту чата для точных ответов
- Семантический поиск по смыслу запроса для нахождения релевантных заметок

### Пользователи и безопасность
- Регистрация с подтверждением email, сброс пароля
- JWT-аутентификация с ротацией refresh-токенов
- Rate limiting по всем группам эндпоинтов
- Тёмная и светлая темы, интернационализация (RU / EN)

### Администрирование
- Панель управления пользователями: просмотр, блокировка, смена роли, удаление аккаунта

## Технические детали

### SSE-стриминг
Ответы ИИ-ассистента доставляются через Server-Sent Events. Бэкенд отправляет события (`ai:text_delta`, `ai:proposal`, `ai:done`) по мере генерации — фронтенд обрабатывает поток инкрементально, не дожидаясь полного ответа.

### Собственные AI Tools
Реализован кастомный `ToolExecutor` по аналогии с function calling. ИИ вызывает инструменты (`create_note`, `edit_note`, `delete_note`, `add_tags`, `remove_tags` и др.), результаты которых формируются в `Proposal`-объекты и отправляются на фронтенд через SSE-поток для подтверждения пользователем.

### RAG и семантический поиск
Заметки автоматически разбиваются на чанки, эмбеддируются и сохраняются в PostgreSQL с расширением `pgvector`. Поиск выполняется по косинусному сходству. Индексация происходит в фоновом воркере с очередью, дебаунсом и retry-логикой.

### CI/CD
Раздельные GitHub Actions пайплайны для фронтенда и бэкенда. При пуше в `main`: запускаются тесты и линтер — при успехе автоматически триггерится деплой на Render через deploy hook.

### Фоновый воркер
Отдельный процесс (Worker) обрабатывает очередь индексации эмбеддингов и периодически удаляет заметки, пролежавшие в корзине дольше установленного срока.

### JWT + Redis
Аутентификация через access/refresh токены. Redis используется для rate limiting (скользящее окно по IP) и хранения временных данных сессий.

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
| Контейнеризация | Docker Compose |
| CI/CD | GitHub Actions → Render |

## Архитектура

```
                  :80/:443
                     │
                   Nginx
                  ╱     ╲
          /api/*          /*
            │              │
    FastAPI backend    React frontend
     (Uvicorn:8000)    (static/Nginx:80)
        │      │
   PostgreSQL  Redis
   (pgvector)
        │
      Worker
  (эмбеддинги + очистка)
```

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
```

## Быстрый старт

### Требования

- [Docker](https://docs.docker.com/get-docker/) и Docker Compose

### 1. Клонировать и настроить

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
ROUTERAI_EMBEDDING_MODEL=your-emb-model    # модель для эмбеддингов

# Resend — для отправки писем (подтверждение email, сброс пароля)
# Получить ключ: https://resend.com
EMAIL_API_KEY=re_your_resend_key
EMAIL_FROM=noreply@yourdomain.com
```

> **Без Resend** приложение запустится, но письма отправляться не будут. Для локального тестирования можно использовать демо-аккаунт, указанный на странице входа.

### 2. Запустить

```bash
docker compose up
```

Запускаются все сервисы: Nginx, бэкенд, воркер, фронтенд, PostgreSQL, Redis.

Приложение доступно по адресу **http://localhost**.  
Документация API: **http://localhost/api/docs**.

При первом запуске автоматически выполняются Alembic-миграции и создаётся аккаунт администратора (`ADMIN_EMAIL` / `ADMIN_PASSWORD` из `.env`).

### 3. Остановить

```bash
docker compose down        # остановить сервисы
docker compose down -v     # + удалить данные БД
```

## Разработка

### Фронтенд (без Docker)

```bash
cd frontend
npm install
npm run dev
```

Vite запускается на `http://localhost:5173` и проксирует `/api/*` на `http://localhost:80`, поэтому Docker-бэкенд должен быть запущен.

### Тестирование

```bash
# Поднять тестовую инфраструктуру
docker compose -f docker-compose.test.yml up -d

# Backend — интеграционные + unit тесты
cd backend && uv run pytest

# Frontend — unit тесты
cd frontend && npm run test
```

### Линтер

```bash
cd frontend && npm run lint
cd backend && uv run flake8 .
```

## Переменные окружения

Все переменные задаются в `.env` (загружается Docker Compose). Полный список — в [`.env.example`](.env.example).

| Группа | Переменные |
|--------|-----------|
| База данных | `DATABASE_URL`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW` |
| Redis | `REDIS_URL` |
| JWT | `JWT_SECRET`, `ACCESS_TOKEN_TTL_MINUTES`, `REFRESH_TOKEN_TTL_DAYS` |
| RouterAI | `ROUTERAI_API_KEY`, `ROUTERAI_BASE_URL`, `ROUTERAI_LLM_MODEL`, `ROUTERAI_EXECUTOR_MODEL`, `ROUTERAI_EMBEDDING_MODEL` |
| Email (Resend) | `EMAIL_PROVIDER`, `EMAIL_API_KEY`, `EMAIL_FROM` |
| Сид администратора | `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NICKNAME` |
| Лимиты | `MAX_NOTES_PER_USER`, `MAX_CHAT_SESSIONS_PER_USER`, `TRASH_RETENTION_DAYS` и др. |
| Rate limiting | `RATE_AUTH_PER_MINUTE`, `RATE_CRUD_PER_MINUTE`, `RATE_AI_PER_MINUTE` и др. |
| Воркер | `EMBEDDING_QUEUE_INTERVAL_SECONDS`, `CLEANUP_INTERVAL_SECONDS` |

## Структура проекта

```
Nocturn/
  backend/
    src/
      app/              FastAPI-приложение
        common/         Общее: БД, Redis, email, зависимости
        middleware/     Аутентификация, rate limiting
        modules/        Модули (auth, notes, ai, rag и др.)
      worker/           Фоновые задачи (эмбеддинги, очистка)
    migrations/         Alembic-миграции
    pyproject.toml      Зависимости Python
  frontend/
    src/
      api/              HTTP-клиент, типы
      components/       UI-компоненты
      features/         Функциональные модули (chat, notes, tags)
      stores/           Глобальное состояние (Zustand)
      i18n/             Переводы (RU / EN)
    package.json        Зависимости Node
  nginx/
    nginx.conf          Конфигурация обратного прокси
  .github/workflows/    CI/CD пайплайны
  docker-compose.yml    Продакшн-стек
  .env.example          Шаблон переменных окружения
  Makefile              Команды для разработки
```
