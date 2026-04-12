# Assistant Interface Specification
## Nocturn
**Версия:** 1.1
**Дата:** 2026-03-28
**Автор:** Shamukhametov Ruslan

---

## Содержание

[[#1. Архитектура]]
[[#2. Хранение данных]]
[[#3. Tools Planner]]
[[#4. Tools Executor]]
[[#5. Жизненный цикл proposals]]
[[#6. Жизненный цикл bulk-операций]]
[[#7. Формирование контекста LLM]]
[[#8. Системные промпты]]
[[#9. API-эндпоинты]]
[[#10. Поведение клиента и граничные случаи]]
[[#11. SSE-события]]
[[#12. Обработка ошибок]]
[[#13. Ограничения и лимиты]]

---

## 1. Архитектура

### 1.1 Компоненты

Ассистент состоит из двух компонентов, использующих разные LLM-модели:

**Planner** (`ROUTERAI_LLM_MODEL`) — основная модель. Отвечает за:
- понимание запроса пользователя
- поиск и чтение заметок через tools
- генерацию текстовых ответов
- регистрацию одиночных proposals
- инициирование bulk-операций (через pending_confirmations)

**Executor** (`ROUTERAI_EXECUTOR_MODEL`) — дешёвая модель. Отвечает за:
- обработку каждой заметки в рамках `batch_transform`
- возврат tool calls, каждый из которых становится отдельным proposal
- работает в режиме one-shot: один вызов на заметку, без feedback loop

### 1.2 Принцип работы

```
Пользователь
    │
    ▼
POST /api/ai/sessions/{id}/messages
    │
    ▼
Backend сохраняет user-сообщение
    │
    ▼
Формирование контекста (см. раздел 7)
    │
    ▼
Planner (LLM, streaming)
    ├── текстовый ответ → SSE: ai:text_delta
    ├── tool call (чтение) → backend выполняет → результат в LLM
    ├── tool call (propose_*) → backend регистрирует proposal → SSE: ai:proposal
    └── tool call (batch_*) → backend регистрирует pending_confirmation → SSE: ai:pending_confirmation
    │
    ▼
SSE: ai:done
Backend сохраняет assistant-сообщение
```

Для `batch_transform` после подтверждения пользователем:

```
POST /api/ai/sessions/{id}/confirm/{confirmation_id}
    │
    ▼
Для каждой заметки:
    Executor (one-shot LLM вызов)
        └── tool calls → proposals
    │
    ▼
SSE: ai:proposal (по мере генерации)
    │
    ▼
SSE: ai:done
```

### 1.3 Sources

Planner ссылается на заметки непосредственно в тексте ответа используя формат `[[note:uuid|Заголовок]]`. Клиент парсит этот формат и рендерит как кликабельные ссылки. Отдельная структура для sources не хранится.

Ограничение на sources реализуется через tool `search_notes`: бэкенд принудительно ограничивает параметр `limit` максимальным значением **5** ([[CPS#5.3 AI-ассистент]]) вне зависимости от переданного Planner значения. Это ограничивает количество заметок, которые Planner получает за один вызов и может использовать как источники.

---

## 2. Хранение данных

### 2.1 Схема chat_messages

Финальная структура таблицы `chat_messages`:

| Колонка | Тип | Ограничения | Описание |
|---|---|---|---|
| id | UUID | PK | |
| session_id | UUID | FK → chat_sessions, NOT NULL | |
| role | VARCHAR(10) | NOT NULL | `user` / `assistant` |
| content | TEXT | NOT NULL | Текст сообщения. У assistant — с инлайн-ссылками `[[note:uuid\|Заголовок]]` |
| actions | JSONB | | Массив proposals и pending_confirmations. Только для assistant |
| attached_note_ids | UUID[] | | Без FK. ID прикреплённых заметок ([[CPS#5.3 AI-ассистент]]). Только для user |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

### 2.2 Структура proposal в actions

```json
{
  "type": "proposal",
  "id": "uuid-v4",
  "proposal_type": "edit_note | create_note | delete_note | add_tags | remove_tags",
  "status": "pending | applied | dismissed",
  "note_id": "uuid (null для create_note)",
  "data": { ... },
  "summary": "строка"
}
```

**Правило хранения data:**
- Пока `status = pending`: поле `data` содержит полный snapshot (см. 2.3). `summary` отсутствует или null
- После `status = applied | dismissed`: поле `data` удаляется (null). `summary` заполняется бэкендом по шаблону (см. 2.5)

### 2.3 Поле data по типам proposal

**`edit_note`:**
```json
{ "title": "Новый заголовок (null если не меняется)", "content": "Полный новый контент (null если не меняется)" }
```

**`create_note`:**
```json
{ "title": "Заголовок", "content": "Содержимое", "tags": ["тег1", "тег2"] }
```

**`delete_note`:**
```json
{ "note_title": "Заголовок удаляемой заметки (для отображения в UI)" }
```

**`add_tags`:**
```json
{ "tags": ["тег1", "тег2"] }
```

**`remove_tags`:**
```json
{ "tags": ["тег1", "тег2"] }
```

### 2.4 Структура pending_confirmation в actions

```json
{
  "type": "pending_confirmation",
  "id": "uuid-v4",
  "status": "pending | confirmed | dismissed",
  "operation_type": "add_tags | remove_tags | delete | replace | transform",
  "note_ids": ["uuid1", "uuid2"],
  "params": { ... },
  "summary": "строка"
}
```

**Правило хранения:**
- Пока `status = pending`: `note_ids` и `params` хранятся полностью. `summary` отсутствует или null
- После `status = confirmed | dismissed`: `note_ids` и `params` сохраняются для отображения истории. `summary` заполняется бэкендом

### 2.5 Шаблоны summary

Summary генерируется бэкендом детерминированно в момент изменения статуса. Не требует LLM.

| Тип | Шаблон |
|---|---|
| `edit_note` applied | `"Изменена заметка «{title}»"` |
| `edit_note` dismissed | `"Отклонено редактирование заметки «{title}»"` |
| `create_note` applied | `"Создана заметка «{title}»"` |
| `create_note` dismissed | `"Отклонено создание заметки"` |
| `delete_note` applied | `"Удалена заметка «{note_title}»"` |
| `delete_note` dismissed | `"Отклонено удаление заметки «{note_title}»"` |
| `add_tags` applied | `"Добавлены теги [{tags}] к заметке «{title}»"` |
| `add_tags` dismissed | `"Отклонено добавление тегов к заметке «{title}»"` |
| `remove_tags` applied | `"Удалены теги [{tags}] из заметки «{title}»"` |
| `remove_tags` dismissed | `"Отклонено удаление тегов из заметки «{title}»"` |
| pending_confirmation confirmed | `"{operation_type} для {N} заметок — подтверждено, {M} proposals сгенерировано"` |
| pending_confirmation dismissed | `"{operation_type} для {N} заметок — отклонено"` |

---

## 3. Tools Planner

Planner получает tools через стандартный механизм function calling LLM API.

### 3.1 Чтение (3 tools)

#### `search_notes`

Универсальный поиск заметок с комбинируемыми фильтрами.

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `query` | string | Нет | Текст запроса для поиска |
| `search_mode` | enum: `semantic` \| `fulltext` | Обязателен если `query` задан | Режим поиска |
| `tags` | string[] | Нет | Включить заметки с ВСЕМИ указанными тегами (AND-логика) |
| `exclude_tags` | string[] | Нет | Исключить заметки с ЛЮБЫМ из указанных тегов (OR-логика) |
| `created_from` | datetime (ISO 8601) | Нет | `created_at ≥` |
| `created_to` | datetime (ISO 8601) | Нет | `created_at ≤` |
| `updated_from` | datetime (ISO 8601) | Нет | `updated_at ≥` |
| `updated_to` | datetime (ISO 8601) | Нет | `updated_at ≤` |
| `sort_by` | enum: `relevance` \| `created_at` \| `updated_at` | Нет | По умолчанию: `relevance` если query задан, иначе `updated_at` |
| `sort_order` | enum: `asc` \| `desc` | Нет | По умолчанию: `desc` |
| `limit` | int (1–5, default 5) | Нет | Максимальное количество результатов ([[CPS#5.3 AI-ассистент]]) |

**Поведение:**
- `sort_by: relevance` допустим только при наличии `query`. Иначе — `{ error: "validation_error", details: "relevance sort requires query" }`
- При `search_mode: semantic` и недоступности embedding-сервиса — tool возвращает ошибку; Planner может повторить с `fulltext`
- Фильтры комбинируются AND между группами

**Возвращает:**
```json
{
  "total_count": 42,
  "notes": [
    {
      "note_id": "uuid",
      "title": "Заголовок",
      "content_preview": "Первые 100 символов...",
      "tags": ["тег1"],
      "created_at": "ISO 8601",
      "updated_at": "ISO 8601",
      "relevance_score": 0.87
    }
  ]
}
```

`total_count` — общее количество заметок по фильтрам без учёта `limit`. Позволяет Planner определить что результат усечён.

#### `get_note`

Получить полное содержимое заметки. Использовать только когда нужен полный контент (редактирование, детальный анализ). Для общих ответов достаточно `content_preview` из `search_notes`.

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `note_id` | UUID | Да | ID заметки |

**Валидация:** заметка существует, принадлежит пользователю, не soft-deleted. Иначе — `{ error: "note_not_found" }`.

**Возвращает:** `{ note_id, title, content, tags, version, created_at, updated_at }`

#### `list_tags`

Получить список всех тегов пользователя.

**Параметры:** нет.

**Возвращает:** массив `{ tag_id, name, notes_count }`

---

### 3.2 Одиночные proposals (5 tools)

Эти tools не выполняют мутацию данных. Они регистрируют proposal в `chat_messages.actions` текущего ответа ассистента.

**Ограничение:** не более одного proposal каждого типа на одну `note_id` в одном ответе. Дублирующий proposal отклоняется с `{ error: "duplicate_proposal" }`.

#### `propose_edit_note`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `note_id` | UUID | Да | |
| `title` | string (max 200) | Нет | Новый заголовок. Если не указан — не меняется |
| `content` | string (max 20000) | Нет | Полный новый контент. Если не указан — не меняется |

**Валидация:** заметка существует, принадлежит пользователю, не soft-deleted. Хотя бы одно из полей `title` / `content` должно быть указано.

**Возвращает:** `{ proposal_id, status: "registered" }`

#### `propose_create_note`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `title` | string (max 200) | Нет | |
| `content` | string (max 20000) | Нет | |
| `tags` | string[] | Нет | Теги для новой заметки |

**Валидация:** теги (если указаны) проходят валидацию формата ([[CPS#4. Политика тегов]]). Количество тегов ≤ 10. Существование тегов не проверяется на этом этапе — при apply клиент создаёт несуществующие теги через `POST /api/tags`.

**Возвращает:** `{ proposal_id, status: "registered" }`

#### `propose_delete_note`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `note_id` | UUID | Да | |

**Валидация:** заметка существует, принадлежит пользователю, не soft-deleted.

**Возвращает:** `{ proposal_id, status: "registered" }`

#### `propose_add_tags`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `note_id` | UUID | Да | |
| `tags` | string[] | Да | Теги для добавления |

**Валидация:** заметка существует, принадлежит пользователю, не soft-deleted. Теги проходят валидацию формата. Итоговое количество тегов (существующие + добавляемые) ≤ 10 на момент регистрации. Если к моменту apply лимит превышен — стандартная ошибка 400 от модуля NOTES.

**Возвращает:** `{ proposal_id, status: "registered" }`

#### `propose_remove_tags`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `note_id` | UUID | Да | |
| `tags` | string[] | Да | Теги для удаления |

**Валидация:** заметка существует, принадлежит пользователю, не soft-deleted. Теги проходят валидацию формата.

**Возвращает:** `{ proposal_id, status: "registered" }`

---

### 3.3 Bulk-операции (5 tools)

Все batch-tools регистрируют `pending_confirmation` в `chat_messages.actions`. Proposals генерируются только после явного подтверждения пользователем. Не более одной batch-операции в одном ответе.

#### Общая валидация batch-tools (backend)

Выполняется до регистрации pending_confirmation:
- Количество `note_ids` ≤ 25 ([[CPS#5.3 AI-ассистент]]). При превышении — `{ error: "too_many_notes", max: 25 }`
- Все `note_ids` существуют, принадлежат пользователю, не soft-deleted
- Невалидные `note_ids` исключаются; если список пуст после фильтрации — `{ error: "no_valid_notes" }`

**Возвращает:** `{ confirmation_id, status: "awaiting_confirmation", valid_note_count, excluded_note_ids? }`

#### `batch_add_tags`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `note_ids` | UUID[] | Да | Список ID заметок (макс. 25) |
| `tags` | string[] | Да | Теги для добавления |

**Тип:** детерминированная. После подтверждения backend генерирует proposals типа `add_tags` без LLM.

#### `batch_remove_tags`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `note_ids` | UUID[] | Да | |
| `tags` | string[] | Да | Теги для удаления |

**Тип:** детерминированная. Backend генерирует proposals типа `remove_tags` без LLM.

#### `batch_delete`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `note_ids` | UUID[] | Да | |

**Тип:** детерминированная. Backend генерирует proposals типа `delete_note` без LLM.

#### `batch_replace`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `note_ids` | UUID[] | Да | |
| `pattern` | string (max 200) | Да | Regex для поиска (синтаксис RE2) |
| `replacement` | string (max 500) | Да | Строка замены. Поддерживает capture groups: `\1`, `\2` |
| `flags` | string[] | Нет | `i` (IGNORECASE), `m` (MULTILINE), `s` (DOTALL). По умолчанию — без флагов |
| `scope` | enum: `content` \| `title` \| `both` | Нет | Область замены. По умолчанию: `content` |

**Тип:** детерминированная. Backend загружает каждую заметку, выполняет `re2.sub(pattern, replacement, text)` для полей, определённых `scope`, генерирует proposal типа `edit_note` со snapshot нового контента. Если совпадений нет — proposal не создаётся.

**Дополнительная валидация:**
- `pattern` компилируется через библиотеку **RE2** (`google-re2`). RE2 гарантирует линейное время, исключает ReDoS
- Lookahead, lookbehind, backreferences не поддерживаются RE2 — отклоняются с `{ error: "unsupported_pattern" }`
- При невалидном regex — `{ error: "invalid_pattern", details: "..." }`

#### `batch_transform`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `note_ids` | UUID[] | Да | |
| `instruction` | string | Да | Инструкция для Executor (что сделать с каждой заметкой) |

**Тип:** недетерминированная. После подтверждения backend вызывает Executor на каждую заметку (см. раздел 4).

---

## 4. Tools Executor

Executor вызывается backend'ом для каждой заметки в рамках `batch_transform`.

### 4.1 Режим работы

- **One-shot**: backend отправляет один запрос к LLM с системным промптом, контентом заметки и описанием tools
- LLM отвечает одним сообщением, содержащим ноль или более tool calls
- Backend **не отправляет** результаты tool calls обратно в LLM — tool calls обрабатываются как декларации
- Если Executor не вызывает ни одного tool — proposal для заметки не создаётся
- Каждый tool call Executor преобразуется backend'ом в отдельный proposal

### 4.2 Tools (4)

#### `edit_note`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `title` | string (max 200) | Нет | Новый заголовок |
| `content` | string (max 20000) | Нет | Полный новый контент |

Хотя бы одно из полей должно быть указано. → Proposal типа `edit_note`.

#### `add_tags`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `tags` | string[] | Да | Теги для добавления |

**Валидация:** теги проходят валидацию формата. Итоговое количество тегов ≤ 10. → Proposal типа `add_tags`.

#### `remove_tags`

| Параметр | Тип | Обязательность | Описание |
|---|---|---|---|
| `tags` | string[] | Да | Теги для удаления |

**Валидация:** теги проходят валидацию формата. → Proposal типа `remove_tags`.

#### `delete_note`

**Параметры:** нет. → Proposal типа `delete_note`.

---

## 5. Жизненный цикл proposals

### 5.1 Регистрация

1. Planner вызывает `propose_*` tool
2. Backend валидирует параметры
3. Backend добавляет proposal в `actions` текущего assistant-сообщения со `status: "pending"` и полным `data`
4. SSE: событие `ai:proposal` → клиент отображает интерактивную карточку

### 5.2 Применение (Apply)

1. Пользователь нажимает Apply
2. Клиент вызывает `PATCH /api/ai/sessions/{id}/messages/{msg_id}/actions/{action_id}` с `{ status: "applied" }`
3. Backend записывает `status: "applied"`, удаляет `data`, записывает `summary`
4. Клиент вызывает CRUD-эндпоинт модуля NOTES:
   - `edit_note` → `PUT /api/notes/{note_id}` с `{ title, content, version }`
   - `create_note` → `POST /api/notes`, затем теги через `POST /api/tags` (если не существуют) + `PUT /api/notes/{id}/tags`
   - `delete_note` → `DELETE /api/notes/{note_id}`
   - `add_tags` → `PUT /api/notes/{note_id}/tags` с полным набором (текущие + добавляемые)
   - `remove_tags` → `PUT /api/notes/{note_id}/tags` с полным набором (текущие − удаляемые)

**Порядок операций:** PATCH статуса выполняется до CRUD-операции. При сбое между ними: proposal помечен как applied, но мутация не выполнена — менее критично, чем обратный случай (мутация выполнена, proposal остался в pending и может быть применён повторно).

**Сбой CRUD-операции:** клиент отображает уведомление об ошибке с кнопкой повтора. Для `edit_note` изменения также подхватываются автосохранением при открытом редакторе.
### 5.3 Отклонение (Dismiss)

1. Пользователь нажимает Dismiss
2. Клиент вызывает `PATCH .../actions/{action_id}` с `{ status: "dismissed" }`
3. Backend записывает `status: "dismissed"`, удаляет `data`, записывает `summary`

### 5.4 Массовые действия (Apply all / Dismiss all)

При наличии нескольких proposals клиент отображает кнопки:
- **«Применить всё»** — последовательно применяет все pending proposals. При ошибке на одном (404, 409, 400) — пропускает, отмечает как failed, продолжает с остальными
- **«Отклонить всё»** — переводит все pending proposals в `dismissed`

### 5.5 Ошибки при apply

| Ошибка | Поведение |
|---|---|
| `404` — заметка удалена | Клиент отмечает proposal как failed, показывает уведомление |
| `409` — конфликт версий | Клиент отмечает proposal как failed, предлагает обновить страницу |
| `400` — превышен лимит (теги, размер заметки) | Клиент отмечает proposal как failed, показывает причину |

---

## 6. Жизненный цикл bulk-операций

### 6.1 Инициирование

1. Planner вызывает `batch_*` tool
2. Backend валидирует `note_ids`
3. Backend добавляет `pending_confirmation` в `actions` со `status: "pending"`
4. SSE: событие `ai:pending_confirmation` → клиент показывает кнопки Подтвердить/Отклонить

### 6.2 Подтверждение

1. Пользователь нажимает Подтвердить
2. Клиент: `POST /api/ai/sessions/{id}/confirm/{confirmation_id}`
3. Backend:
   - Обновляет `pending_confirmation.status` → `confirmed`
   - Создаёт новое assistant-сообщение (в него будут добавляться proposals)
   - Генерирует proposals:
     - **Детерминированные** (`batch_add_tags`, `batch_remove_tags`, `batch_delete`, `batch_replace`): backend генерирует самостоятельно без LLM
     - **Недетерминированные** (`batch_transform`): backend вызывает Executor на каждую заметку
   - По мере генерации добавляет proposals в `actions` нового сообщения и стримит клиенту через SSE
4. SSE: `ai:proposal` события по мере генерации
5. SSE: `ai:done`
6. Backend обновляет `pending_confirmation.summary`

### 6.3 Отклонение

1. Пользователь нажимает Отклонить
2. Клиент: `POST /api/ai/sessions/{id}/dismiss/{confirmation_id}`
3. Backend: `status` → `dismissed`, записывает `summary`

### 6.4 Отмена выполняющейся операции

1. Пользователь нажимает «Остановить»
2. Клиент: `POST /api/ai/sessions/{id}/cancel`
3. Backend обрывает текущий LLM-запрос
4. Уже сгенерированные proposals сохраняются
5. SSE: `ai:done`

---

## 7. Формирование контекста LLM

### 7.1 Структура контекста

```
[system prompt]
[история сессии — сообщения от новых к старым, в рамках токен-бюджета]
```

### 7.2 Токен-бюджет

```
input_token_budget = model_context_window - max_tokens - system_prompt_tokens - safety_margin
```

Параметры задаются через переменные окружения. Значения по умолчанию определены в [[CPS#5.3 AI-ассистент]].

Аппроксимация: **1 токен ≈ 1.3 символа** (для преимущественно кириллического контента). Коэффициент задаётся через переменную окружения `PLANNER_CHARS_PER_TOKEN` и подбирается под конкретную модель. Рекомендуется калибровать на реальных данных перед продом. `safety_margin` компенсирует погрешность.

### 7.3 Алгоритм формирования истории

1. Backend берёт сообщения сессии с конца (от новых к старым)
2. Добавляет пока не исчерпан токен-бюджет
3. Верхняя граница — **25 сообщений** ([[CPS#5.3 AI-ассистент]]), даже если бюджет позволяет больше
4. Если одно последнее сообщение + system prompt превышает бюджет — отправляется только system prompt + последнее сообщение пользователя, обрезанное по необходимости

### 7.4 Представление сообщений в контексте

**user-сообщение:**
```
content

[Прикреплённые заметки (если есть):]
- uuid1 | Заголовок1: превью первых 100 символов...
- uuid2 | Заголовок2: превью первых 100 символов...
```

Прикреплённые заметки добавляются только к последнему user-сообщению. В исторических сообщениях блок прикреплённых заметок не включается для экономии токен-бюджета.

**assistant-сообщение:**
```
content + резюме actions (если есть)
```

Поле `actions` **не передаётся целиком**. Backend заменяет его текстовым резюме:
- Proposal: `"[propose_edit_note для заметки «Python» — applied]"`
- Pending_confirmation: `"[batch_transform для 15 заметок — confirmed, 14 proposals сгенерировано]"`

Полные snapshots (`data`) в контекст не передаются — это предотвращает переполнение контекста при наличии заметок до 20 000 символов.

---

## 8. Системные промпты

### 8.1 Системный промпт Planner

Формируется бэкендом при каждом вызове Planner.

```
Ты — AI-ассистент приложения для заметок Nocturn.
Помогаешь пользователю находить, анализировать и изменять его заметки.

## Правила

1. Читай заметки через tools search_notes, get_note, list_tags.
2. Для изменений используй propose_* (одиночные) или batch_* (массовые).
   Ты не можешь изменять заметки напрямую — только предлагать изменения.
3. Пользователь сам решает, применять ли proposals.
4. Не более одного proposal каждого типа на одну заметку в одном ответе.
5. Не более одной batch_* операции в одном ответе. Если запрос требует
   несколько — выполни первую, предложи пользователю повторить для следующей.
6. Максимум заметок в одной batch_* операции — 25.
   Если нужно больше — выполни первые 25, предложи повторить для остальных.
7. Отвечай на языке пользователя.
8. Если заметки не найдены — сообщи об этом. Не выдумывай содержимое.
9. Ссылайся на заметки в тексте в формате [[note:uuid|Заголовок]].
   Максимум 5 ссылок в одном ответе (не считая прикреплённых пользователем).
10. Используй get_note только когда нужен полный контент заметки
    (редактирование, детальный анализ). Для общих ответов достаточно
    content_preview из search_notes.
11. Для batch_replace regex выполняется через RE2 — не используй lookahead,
    lookbehind, backreferences. При необходимости используй более точный
    паттерн без них.

## Контекст

Текущая дата: {current_date}
Прикреплённые заметки отображаются в последнем сообщении пользователя.
Если нужен полный контент прикреплённой заметки, используй get_note.
```

### 8.2 Системный промпт Executor

Формируется бэкендом при каждом вызове Executor.

```
Обработай заметку по инструкции. Используй tools для внесения изменений.
Если инструкция не применима к этой заметке — не вызывай tools.

## Инструкция
{instruction из batch_transform}

## Заметка
Заголовок: {title}
Теги: {tags}
Содержимое:
{content}
```

---

## 9. API-эндпоинты

### 9.1 Чат-сессии

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/ai/sessions` | Создать сессию |
| GET | `/api/ai/sessions` | Список сессий пользователя |
| DELETE | `/api/ai/sessions/{session_id}` | Удалить сессию |
| GET | `/api/ai/sessions/{session_id}/messages` | История сообщений (пагинация) |

### 9.2 Отправка сообщения

**POST `/api/ai/sessions/{session_id}/messages`**

Request:
```json
{
  "content": "Текст сообщения (max 4000 символов)",
  "attached_note_ids": ["uuid1", "uuid2"]
}
```

`attached_note_ids` — опциональный массив UUID заметок (макс. 5, [[CPS#5.3 AI-ассистент]]). Бэкенд резолвит каждый UUID: проверяет существование, принадлежность пользователю, не soft-deleted. Невалидные UUID игнорируются без ошибки. Для валидных заметок бэкенд загружает заголовок и `content_preview` (первые 100 символов) и передаёт в контекст LLM (см. раздел 7.4).

Response: пустой `200 OK`. Ответ ассистента доставляется через персистентный SSE-канал (`GET /api/events`).

Ошибки:
- `400` — пустое сообщение, превышена длина, более 5 прикреплённых заметок
- `404` — сессия не найдена / чужая
- `409` — генерация уже в процессе или есть необработанные proposals / pending_confirmations
- `429` — rate limit

### 9.3 Отмена активности ассистента

**POST `/api/ai/sessions/{session_id}/cancel`**

Единый эндпоинт для остановки любой активной операции ассистента в рамках сессии:
- обычная генерация Planner
- генерация proposals после bulk-подтверждения (Executor)

Поведение:
- Backend обрывает текущий LLM-запрос (Planner или Executor)
- Частично сгенерированный текст ответа сохраняется в `chat_messages`
- Частично сгенерированные proposals сохраняются — пользователь может их применить
- SSE: `ai:done`

Response: `200 OK` с `{ "status": "cancelled" }`.

Ошибки:
- `404` — сессия не найдена
- `409` — нет активной операции

### 9.4 Proposals и confirmations

| Метод | Путь | Описание |
|---|---|---|
| PATCH | `/api/ai/sessions/{session_id}/messages/{message_id}/actions/{action_id}` | Обновить статус proposal (`applied` / `dismissed`) |
| POST | `/api/ai/sessions/{session_id}/confirm/{confirmation_id}` | Подтвердить bulk-операцию |
| POST | `/api/ai/sessions/{session_id}/dismiss/{confirmation_id}` | Отклонить bulk-операцию |

**PATCH actions/{action_id}:**

Request: `{ "status": "applied" | "dismissed" }`

Поведение: backend обновляет статус, удаляет `data`, записывает `summary`.

**POST confirm/{confirmation_id}:**

Response: пустой `200 OK`. Proposals стримятся через персистентный SSE-канал.

Ошибки:
- `404` — сессия или confirmation не найдены
- `409` — confirmation уже обработан

### 9.5 Вспомогательные

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/notes/batch` | Получить несколько заметок по массиву ID (для diff в bulk proposals) |

**POST `/api/notes/batch`:**

Request: `{ "note_ids": ["uuid1", "uuid2"] }` (макс. 50)

Response:
```json
{
  "notes": [{ "note_id": "uuid", "title": "...", "content": "...", "tags": [...], "version": 1 }],
  "not_found": ["uuid-не-найден"]
}
```

Возвращает только заметки, принадлежащие пользователю и не soft-deleted.

---

## 10. Поведение клиента и граничные случаи

### 10.1 Обрыв SSE-соединения

При потере персистентного SSE-соединения клиент предлагает пользователю перезагрузить страницу. После перезагрузки клиент загружает историю сессии через `GET /messages` и восстанавливает интерфейс на основе сохранённых данных — `content` сообщений и `status` proposals.

### 10.2 Создание нового чата при pending proposals

Если в текущей сессии есть proposals со `status: "pending"` и пользователь инициирует создание новой сессии:

1. Клиент показывает предупреждение: «В текущем чате есть необработанные предложения. При создании нового чата они будут отклонены»
2. Пользователь подтверждает
3. Клиент вызывает `POST /api/ai/sessions` с телом `{ "dismiss_session_id": "uuid" }` — ID сессии с pending proposals
4. Бэкенд переводит все pending proposals указанной сессии в `dismissed`, записывает summary, затем создаёт новую сессию

### 10.3 Флаг активной генерации

Бэкенд хранит в Redis ephemeral ключ `generating:{session_id}` на время активной операции (генерация Planner или Executor). При завершении, ошибке или cancel — ключ удаляется. TTL ключа — страховка на случай краша бэкенда.

Ключ используется для:
- возврата `409` при повторной отправке сообщения во время генерации
- корректной обработки `POST /cancel`

## 11. SSE-события

Все AI-события доставляются через персистентный SSE-канал (`GET /api/events`), описанный в SAD раздел 8.7.

### 11.1 Типы AI-событий

#### `ai:text_delta`
Фрагмент текстового ответа Planner.
```
event: ai:text_delta
data: {"delta": "Фрагмент текста"}
```

#### `ai:proposal`
Зарегистрированный proposal.
```
event: ai:proposal
data: {
  "id": "uuid",
  "proposal_type": "edit_note",
  "note_id": "uuid",
  "status": "pending",
  "data": { ... }
}
```

#### `ai:pending_confirmation`
Запрос подтверждения bulk-операции.
```
event: ai:pending_confirmation
data: {
  "id": "uuid",
  "operation_type": "transform",
  "note_ids": ["uuid1", "uuid2"],
  "params": { "instruction": "Исправь грамматику" },
  "valid_note_count": 15
}
```

#### `ai:error`
Ошибка во время генерации.
```
event: ai:error
data: {"code": "llm_timeout", "message": "LLM API не ответил в течение 10 секунд"}
```

#### `ai:done`
Завершение генерации (ответ или bulk-обработка).
```
event: ai:done
data: {}
```

### 11.2 Порядок событий

Типичный ответ с proposals:
1. `ai:text_delta` (несколько)
2. `ai:proposal` (один или несколько)
3. `ai:done`

Ответ с bulk:
1. `ai:text_delta`
2. `ai:pending_confirmation`
3. `ai:done`

После подтверждения bulk:
1. `ai:proposal` (по одному на заметку, по мере генерации)
2. `ai:done`

---

## 12. Обработка ошибок

### 12.1 Ошибки LLM API

| Ситуация | Поведение |
|---|---|
| LLM API недоступен | SSE: `ai:error` с кодом `llm_unavailable`. User-сообщение сохранено, ответ ассистента — нет |
| Таймаут первого токена (> 10 сек) | SSE: `ai:error` с кодом `llm_timeout`. User-сообщение сохранено, ответ — нет |
| LLM вернул невалидный tool call | Backend игнорирует, возвращает ошибку в LLM. Planner может попробовать другой tool |
| LLM вызвал несуществующий tool | Backend возвращает ошибку в LLM |

### 12.2 Ошибки tool calls

| Ситуация | Поведение |
|---|---|
| `search_notes` с `semantic`, embedding недоступен | Tool возвращает ошибку. Planner может повторить с `fulltext` |
| `get_note` с несуществующим / чужим / deleted note_id | `{ error: "note_not_found" }` |
| `propose_*` с невалидными данными | `{ error: "validation_error", details: "..." }` |
| Дублирующий proposal на ту же заметку | `{ error: "duplicate_proposal" }` |
| `batch_*` — все note_ids невалидны | `{ error: "no_valid_notes" }` |
| `batch_*` — часть note_ids невалидна | Результат с `excluded_note_ids` |

### 12.3 Ошибки при генерации proposals (batch_transform)

| Ситуация | Поведение |
|---|---|
| Заметка удалена между confirm и генерацией | Proposal не создаётся. SSE: `ai:text_delta` с предупреждением |
| Executor вернул ошибку для одной заметки | Proposal не создаётся. Остальные обрабатываются |
| Executor вернул невалидный tool call | Proposal не создаётся |
| Все вызовы Executor завершились ошибкой | SSE: `ai:error` с кодом `bulk_failed` |
| Пользователь отменил операцию (`POST /cancel`) | Backend прекращает обработку. Готовые proposals сохраняются. SSE: `ai:done` |

---

## 13. Ограничения и лимиты

| Параметр | Значение | Источник |
|---|---|---|
| Макс. длина сообщения пользователя | 4 000 символов | [[CPS#5.3 AI-ассистент]] |
| Макс. прикреплённых заметок к сообщению | 5 | [[CPS#5.3 AI-ассистент]] |
| Таймаут первого токена Planner | 10 сек | [[CPS#5.3 AI-ассистент]] |
| Макс. сообщений в контексте LLM | 25 | [[CPS#5.3 AI-ассистент]] |
| Макс. заметок в одной batch_* операции | 25 | [[CPS#5.3 AI-ассистент]] |
| Макс. чат-сессий на пользователя | 50 | [[CPS#5.3 AI-ассистент]] |
| TTL чат-сессии | 14 дней | [[CPS#5.3 AI-ассистент]] |
| Rate limit AI-эндпоинты | 10 req/мин на пользователя | [[CPS#6. Rate limiting]] |
| Макс. результатов search_notes (limit) | 5 | [[CPS#5.3 AI-ассистент]] |
| Макс. длина regex-паттерна (batch_replace) | 200 символов | Раздел 3.3 |
| Движок regex | RE2 (google-re2) — линейное время, без ReDoS | Раздел 3.3 |
| Макс. note_ids в POST /api/notes/batch | 50 | Раздел 9.4 |
| Safety margin (токены) | 500 | [[CPS#5.3 AI-ассистент]] |
| System prompt tokens | 500 | [[CPS#5.3 AI-ассистент]] |
| Не более одного batch_* в одном ответе | — | Раздел 3.3 |
| Не более одного proposal каждого типа на одну заметку | — | Раздел 3.2 |

---

*Документ подлежит обновлению при изменении требований. Версия фиксируется при каждом изменении.*
