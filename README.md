# Nocturn

[![Backend CI](https://github.com/CaseyJohnson-RS/Nocturn/actions/workflows/backend_ci.yml/badge.svg)](https://github.com/CaseyJohnson-RS/Nocturn/actions)
[![Frontend CI](https://github.com/CaseyJohnson-RS/Nocturn/actions/workflows/frontend_ci.yml/badge.svg)](https://github.com/CaseyJohnson-RS/Nocturn/actions)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=flat&logo=python&logoColor=white)
![React](https://img.shields.io/badge/React_19-61DAFB?style=flat&logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)

Это полноценное веб приложение для создания и хранения заметок. Создавался как отечественный аналог [Mem.ai](https://mem.ai/).

🌐 **[Открыть демо](https://frontend-uko1.onrender.com/)**

## Главные фишки

### Редактор заметок

- Markdown с мгновенным превью (три режима: редактор / превью / split-view)
- Автосохранение и обнаружение конфликтов редактирования
- Система тегов для фильтрации и организации заметок
- Мягкое удаление в корзину с хранением 30 дней и возможностью восстановления

<img width="1330" height="434" alt="image" src="https://github.com/user-attachments/assets/154c7295-a642-460e-9f7c-9b7b1177bf1d" />


### ИИ-ассистент
<p align="center">
  <img
    src="https://github.com/user-attachments/assets/586e02d8-0cf7-4c70-b077-25e2083e80e4"
    alt="Chat interface"
    width="300"
  />
</p>

- Чат с потоковой передачей ответов в реальном времени
- Предложения действий с подтверждением: создать / отредактировать / удалить заметку, добавить или снять теги
- Массовые операции над несколькими заметками сразу
- Прикрепление заметок к контексту чата для точных ответов
- Семантический поиск по смыслу запроса для нахождения релевантных заметок

### Пользователи и безопасность
- Регистрация с подтверждением email, сброс пароля (в демке не работает, но есть демо-аккаунт)
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
