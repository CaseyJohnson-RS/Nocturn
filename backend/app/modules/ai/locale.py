"""Localized strings for the AI module.

All user-facing text is centralized here for i18n readiness.
To add a new language: create a new dict following the same keys,
and switch STRINGS to point to it.
"""

RU: dict[str, str] = {
    # --- System prompts ---
    "planner_system_prompt": """\
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
Если нужен полный контент прикреплённой заметки, используй get_note.\
""",
    "executor_system_prompt": """\
Обработай заметку по инструкции. Используй tools для внесения изменений.
Если инструкция не применима к этой заметке — не вызывай tools.

## Инструкция
{instruction}

## Заметка
Заголовок: {title}
Теги: {tags}
Содержимое:
{content}\
""",

    # --- Proposal summaries ---
    "edit_note_applied": "Изменена заметка «{title}»",
    "edit_note_dismissed": "Отклонено редактирование заметки «{title}»",
    "create_note_applied": "Создана заметка «{title}»",
    "create_note_dismissed": "Отклонено создание заметки",
    "delete_note_applied": "Удалена заметка «{title}»",
    "delete_note_dismissed": "Отклонено удаление заметки «{title}»",
    "add_tags_applied": "Добавлены теги [{tags}] к заметке «{title}»",
    "add_tags_dismissed": "Отклонено добавление тегов к заметке «{title}»",
    "remove_tags_applied": "Удалены теги [{tags}] из заметки «{title}»",
    "remove_tags_dismissed": "Отклонено удаление тегов из заметки «{title}»",

    # --- Bulk confirmation summaries ---
    "bulk_dismissed": "{op} для {n} заметок — отклонено",
    "bulk_confirmed": "{op} для {n} заметок — подтверждено",
    "bulk_confirmed_with_proposals": (
        "{op} для {n} заметок — подтверждено, "
        "{proposals_count} proposals сгенерировано"
    ),

    # --- Bulk execution message ---
    "bulk_proposals_generated": "Сгенерировано {count} proposals из bulk {op}.",

    # --- Context labels ---
    "attached_notes_header": "[Прикреплённые заметки:]",

    # --- LLM context summaries ---
    "context_proposal_with_summary": "[{ptype} — {status}: {summary}]",
    "context_proposal_no_summary": "[{ptype} для заметки {note_id} — {status}]",
    "context_confirmation": "[{op} для {n} заметок — {status}]",

    # --- Errors ---
    "llm_timeout": "LLM API не ответил в течение {timeout} секунд",
}

# Active string set — switch this to change language
STRINGS = RU


def t(key: str, **kwargs: object) -> str:
    """Get a localized string by key, with optional format arguments."""
    template = STRINGS[key]
    if kwargs:
        return template.format(**kwargs)
    return template
