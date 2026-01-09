# Nocturn — Intelligent Notes Assistant

Nocturn — это система для управления заметками с поддержкой LLM-агента.  
Сервис позволяет пользователю:

- создавать, редактировать и удалять заметки;
- искать и получать релевантный контент по тегам, дате, ключевым словам;
- использовать чат-агента для работы с заметками и автоматизации действий.

Архитектура построена по принципу микросервисов с событиями (Outbox) и слабой связанностью.

---

## Components Overview

### Services

| Service                 | Responsibility                                                                                  |
|-------------------------|------------------------------------------------------------------------------------------------|
| **Authorization Service** | Аутентификация и авторизация пользователей (JWT + Refresh Token Rotation)                      |
| **Notes Service**         | Управление заметками, CRUD, Editing Sessions, публикация событий через Outbox                  |
| **Sync Service**          | Подписка на события из Outbox, обновление Vector DB для поиска и retrieval                     |
| **Agent Service**         | Интерпретация запросов пользователя, планирование действий, вызов *ручек*, генерация ответа   |
| **Client Service**        | UI/UX клиент, отправка запросов и отображение результатов                                       |

### Databases

| Database       | Owned By           | Usage                                               |
|----------------|------------------|---------------------------------------------------|
| **Auth DB**    | Authorization Service | Пользователи, refresh tokens                     |
| **Notes DB**   | Notes Service       | Хранение заметок                                  |
| **Vector DB**  | Sync Service        | Индексация эмбеддингов заметок для поиска        |
| **Outbox**     | Notes Service       | Очередь событий для синхронизации с Vector DB    |
| **Cache / Context DB** | Agent Service | Контексты чата, временные данные пользователей   |

---

## Key Principles

- **Event-Driven**: Notes Service публикует события через Outbox, Sync Service и другие подписчики обрабатывают их асинхронно.
- **Separation of Concerns**: Агент управляет логикой действий, не имеет прямого доступа к БД.
- **Eventual Consistency**: Vector DB может временно отставать от Notes DB.
- **Undo / Audit**: Все действия агента фиксируются и могут быть отменены.
- **Debounce & Batching**: Notes Service агрегирует изменения и пишет их в БД по таймауту или при явных событиях.

---

## Usage Scenarios

- **User Login / Logout**
- **Access Token Expiration**
- **Refresh Token Rotation**
- **Create / Edit / Delete Notes**
- **Search Notes by Content, Tags, Date**
- **Chat with Agent (query / update / contextual actions)**
- **Undo Last Action**

---

## Technology Stack

- **FastAPI** — API для Notes и Agent Service
- **PostgreSQL** — Auth DB, Notes DB
- **Redis / MongoDB** — контексты чатов
- **ChromaDB** — Vector DB
- **LLM** — планирование и генерация текста
- **Async workers** — обработка Outbox и Sync Service
- **Docker / Docker Compose** — локальное развертывание

---