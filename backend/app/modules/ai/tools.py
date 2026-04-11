"""Planner & Executor tool definitions and backend handlers.

Implements AIS sections 3 and 4:
- PLANNER_TOOLS: 13 OpenAI function-calling schemas for the Planner LLM
- EXECUTOR_TOOLS: 4 tool schemas for the Executor LLM (batch_transform)
- ToolExecutor: executes Planner tool calls, returns results or registers
  proposals / pending_confirmations in the actions list.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

import re2
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.ai.locale import t
from app.modules.notes.models import Note
from app.modules.notes.repository import NotesRepository
from app.modules.rag.service import RAGService
from app.modules.tags.repository import TagsRepository

logger = logging.getLogger(__name__)


def truncate_at_word(text: str, max_len: int) -> str:
    """Truncate text at the last word boundary within max_len."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        truncated = truncated[:last_space]
    return truncated + "…" # Yeah, single character triple dot)


# ---------------------------------------------------------------------------
# region Planner tool schemas (OpenAI function-calling format)


_SEARCH_NOTES: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_notes",
        "description": (
            "Search the user's notes with combinable filters. "
            "Returns note_id, title, content_preview, tags, dates, and relevance_score."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search text"},
                "search_mode": {
                    "type": "string",
                    "enum": ["semantic", "fulltext"],
                    "description": "Required when query is set",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Include notes with ALL these tags (AND)",
                },
                "exclude_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Exclude notes with ANY of these tags (OR)",
                },
                "created_from": {"type": "string", "description": "ISO 8601 datetime"},
                "created_to": {"type": "string", "description": "ISO 8601 datetime"},
                "updated_from": {"type": "string", "description": "ISO 8601 datetime"},
                "updated_to": {"type": "string", "description": "ISO 8601 datetime"},
                "sort_by": {
                    "type": "string",
                    "enum": ["relevance", "created_at", "updated_at"],
                },
                "sort_order": {"type": "string", "enum": ["asc", "desc"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 5, "default": 5},
            },
            "required": [],
        },
    },
}

_GET_NOTE: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_note",
        "description": (
            "Get the full content of a note. Use only when full content is needed "
            "(editing, detailed analysis). For general answers use content_preview "
            "from search_notes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "note_id": {"type": "string", "format": "uuid"},
            },
            "required": ["note_id"],
        },
    },
}

_LIST_TAGS: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "list_tags",
        "description": "Get all of the user's tags with note counts.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

_PROPOSE_EDIT_NOTE: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "propose_edit_note",
        "description": (
            "Propose editing an existing note. At least one of title or content must be provided."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "note_id": {"type": "string", "format": "uuid"},
                "title": {"type": "string", "maxLength": 200},
                "content": {"type": "string", "maxLength": 20000},
            },
            "required": ["note_id"],
        },
    },
}

_PROPOSE_CREATE_NOTE: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "propose_create_note",
        "description": "Propose creating a new note.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": 200},
                "content": {"type": "string", "maxLength": 20000},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 10,
                },
            },
            "required": [],
        },
    },
}

_PROPOSE_DELETE_NOTE: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "propose_delete_note",
        "description": "Propose soft-deleting a note (moves to trash).",
        "parameters": {
            "type": "object",
            "properties": {
                "note_id": {"type": "string", "format": "uuid"},
            },
            "required": ["note_id"],
        },
    },
}

_PROPOSE_ADD_TAGS: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "propose_add_tags",
        "description": "Propose adding tags to a note.",
        "parameters": {
            "type": "object",
            "properties": {
                "note_id": {"type": "string", "format": "uuid"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["note_id", "tags"],
        },
    },
}

_PROPOSE_REMOVE_TAGS: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "propose_remove_tags",
        "description": "Propose removing tags from a note.",
        "parameters": {
            "type": "object",
            "properties": {
                "note_id": {"type": "string", "format": "uuid"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["note_id", "tags"],
        },
    },
}

_BATCH_ADD_TAGS: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "batch_add_tags",
        "description": ("Add tags to multiple notes. Requires user confirmation before execution."),
        "parameters": {
            "type": "object",
            "properties": {
                "note_ids": {
                    "type": "array",
                    "items": {"type": "string", "format": "uuid"},
                    "maxItems": 25,
                },
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["note_ids", "tags"],
        },
    },
}

_BATCH_REMOVE_TAGS: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "batch_remove_tags",
        "description": "Remove tags from multiple notes. Requires user confirmation.",
        "parameters": {
            "type": "object",
            "properties": {
                "note_ids": {
                    "type": "array",
                    "items": {"type": "string", "format": "uuid"},
                    "maxItems": 25,
                },
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["note_ids", "tags"],
        },
    },
}

_BATCH_DELETE: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "batch_delete",
        "description": "Delete multiple notes. Requires user confirmation.",
        "parameters": {
            "type": "object",
            "properties": {
                "note_ids": {
                    "type": "array",
                    "items": {"type": "string", "format": "uuid"},
                    "maxItems": 25,
                },
            },
            "required": ["note_ids"],
        },
    },
}

_BATCH_REPLACE: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "batch_replace",
        "description": (
            "Regex find-and-replace across multiple notes. Uses RE2 engine "
            "(no lookahead/lookbehind/backreferences). Requires user confirmation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "note_ids": {
                    "type": "array",
                    "items": {"type": "string", "format": "uuid"},
                    "maxItems": 25,
                },
                "pattern": {"type": "string", "maxLength": 200},
                "replacement": {"type": "string", "maxLength": 500},
                "flags": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["i", "m", "s"]},
                },
                "scope": {
                    "type": "string",
                    "enum": ["content", "title", "both"],
                },
            },
            "required": ["note_ids", "pattern", "replacement"],
        },
    },
}

_BATCH_TRANSFORM: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "batch_transform",
        "description": (
            "Transform multiple notes using a natural-language instruction. "
            "Each note is processed by a separate LLM call. "
            "Requires user confirmation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "note_ids": {
                    "type": "array",
                    "items": {"type": "string", "format": "uuid"},
                    "maxItems": 25,
                },
                "instruction": {"type": "string"},
            },
            "required": ["note_ids", "instruction"],
        },
    },
}

PLANNER_TOOLS: list[dict[str, Any]] = [
    _SEARCH_NOTES,
    _GET_NOTE,
    _LIST_TAGS,
    _PROPOSE_EDIT_NOTE,
    _PROPOSE_CREATE_NOTE,
    _PROPOSE_DELETE_NOTE,
    _PROPOSE_ADD_TAGS,
    _PROPOSE_REMOVE_TAGS,
    _BATCH_ADD_TAGS,
    _BATCH_REMOVE_TAGS,
    _BATCH_DELETE,
    _BATCH_REPLACE,
    _BATCH_TRANSFORM,
]

# ---------------------------------------------------------------------------
# Executor tool schemas
# ---------------------------------------------------------------------------

_EXEC_EDIT_NOTE: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "edit_note",
        "description": "Edit this note's title and/or content.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": 200},
                "content": {"type": "string", "maxLength": 20000},
            },
            "required": [],
        },
    },
}

_EXEC_ADD_TAGS: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "add_tags",
        "description": "Add tags to this note.",
        "parameters": {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tags"],
        },
    },
}

_EXEC_REMOVE_TAGS: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "remove_tags",
        "description": "Remove tags from this note.",
        "parameters": {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tags"],
        },
    },
}

_EXEC_DELETE_NOTE: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "delete_note",
        "description": "Delete this note.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

EXECUTOR_TOOLS: list[dict[str, Any]] = [
    _EXEC_EDIT_NOTE,
    _EXEC_ADD_TAGS,
    _EXEC_REMOVE_TAGS,
    _EXEC_DELETE_NOTE,
]

# ---------------------------------------------------------------------------
# Tool name sets
# ---------------------------------------------------------------------------

READ_TOOL_NAMES = {"search_notes", "get_note", "list_tags"}

PROPOSE_TOOL_NAMES = {
    "propose_edit_note",
    "propose_create_note",
    "propose_delete_note",
    "propose_add_tags",
    "propose_remove_tags",
}

BATCH_TOOL_NAMES = {
    "batch_add_tags",
    "batch_remove_tags",
    "batch_delete",
    "batch_replace",
    "batch_transform",
}

# endregion
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# region Proposal / confirmation helpers


def make_proposal(
    proposal_type: str,
    note_id: str | None,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Create a proposal dict with pending status"""
    return {
        "type": "proposal",
        "id": str(uuid.uuid4()),
        "proposal_type": proposal_type,
        "status": "pending",
        "note_id": note_id,
        "data": data,
        "summary": None,
    }


def make_pending_confirmation(
    operation_type: str,
    note_ids: list[str],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Create a pending_confirmation dict"""
    return {
        "type": "pending_confirmation",
        "id": str(uuid.uuid4()),
        "status": "pending",
        "operation_type": operation_type,
        "note_ids": note_ids,
        "params": params,
        "summary": None,
    }


# --- Summary templates ---


def build_summary(action: dict[str, Any], new_status: str) -> str:
    """Generate a deterministic summary string when status changes."""
    atype = action.get("type")

    if atype == "proposal":
        ptype = action.get("proposal_type", "")
        data: dict[str, Any] = action.get("data") or {}
        title = data.get("title") or data.get("note_title") or "Untitled"

        key = f"{ptype}_{new_status}"
        kwargs: dict[str, str] = {"title": title}
        if ptype in ("add_tags", "remove_tags") and new_status == "applied":
            kwargs["tags"] = ", ".join(data.get("tags", []))

        try:
            return t(key, **kwargs)
        except KeyError:
            return f"{ptype} — {new_status}"

    if atype == "pending_confirmation":
        op = action.get("operation_type", "")
        n = len(action.get("note_ids", []))
        if new_status == "dismissed":
            return t("bulk_dismissed", op=op, n=n)
        return t("bulk_confirmed", op=op, n=n)

    return f"{atype} — {new_status}"


# endregion
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# region ToolExecutor — handles Planner tool calls


class ToolExecutor:
    """Executes Planner tool calls, returning JSON results or registering
    proposals/confirmations in the actions accumulator."""

    def __init__(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        actions: list[dict[str, str]],
    ):
        self.db = db
        self.user_id = user_id
        self.actions = actions
        self.notes_repo = NotesRepository(db)
        self.tags_repo = TagsRepository(db)
        self.rag = RAGService(db)
        self._proposal_keys: set[tuple[str, str | None]] = set()
        self._has_batch = False  # At most one batch per response

    async def execute(self, name: str, arguments: str) -> str:
        """Execute a tool call and return the JSON result string."""
        try:
            args: Any = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            return json.dumps(
                {
                    "error": "invalid_json",
                    "details": "Could not parse tool arguments",
                }
            )

        handler = getattr(self, f"_handle_{name}", None)
        if handler is None:
            return json.dumps(
                {
                    "error": "unknown_tool",
                    "details": f"Tool '{name}' not found",
                }
            )

        try:
            result = await handler(args)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.exception("Tool %s failed", name)
            return json.dumps({"error": "tool_error", "details": str(e)})

    # --- Read tools ---

    async def _handle_search_notes(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args.get("query")
        search_mode = args.get("search_mode")
        limit = min(args.get("limit", 5), settings.max_sources_per_response)
        sort_by = args.get("sort_by")

        # Validation
        if sort_by == "relevance" and not query:
            return {
                "error": "validation_error",
                "details": "relevance sort requires query",
            }
        if query and not search_mode:
            return {
                "error": "validation_error",
                "details": "search_mode required when query is set",
            }

        # Semantic search via RAG
        if query and search_mode == "semantic":
            try:
                search_resp = await self.rag.search(
                    self.user_id,
                    query,
                    limit=limit,
                )
                if not search_resp.results:
                    return {"total_count": 0, "notes": []}

                note_ids = [r.note_id for r in search_resp.results]
                notes = await self.notes_repo.get_active_notes_by_ids(
                    note_ids,
                    self.user_id,
                )
                notes_map = {n.id: n for n in notes}
                scores_map = {r.note_id: r.score for r in search_resp.results}

                notes_out = [
                    self._format_note_result(notes_map[nid], scores_map.get(nid))
                    for nid in note_ids
                    if nid in notes_map
                ]
                return {"total_count": len(notes_out), "notes": notes_out}
            except Exception as e:
                logger.warning("Semantic search failed: %s", e)
                return {"error": "embedding_unavailable", "details": str(e)}

        # Fulltext / filter-based search
        tag_ids = await self._resolve_tag_ids(args.get("tags", []))
        if args.get("tags") and tag_ids is None:
            return {"total_count": 0, "notes": []}

        exclude_tag_ids = await self._resolve_tag_ids(
            args.get("exclude_tags", []),
        )

        date_filters = self._parse_date_filters(args)

        notes, total = await self.notes_repo.list_notes(
            user_id=self.user_id,
            limit=limit,
            offset=0,
            search=query if (query and search_mode == "fulltext") else None,
            tag_ids=tag_ids,
            exclude_tag_ids=exclude_tag_ids,
            **date_filters,  # type: ignore POINT OF POTENTIAL PROBLEMS!
        )

        notes_out = [self._format_note_result(n) for n in notes]
        return {"total_count": total, "notes": notes_out}

    async def _handle_get_note(self, args: dict[str, Any]) -> dict[str, Any]:
        note_id = self._parse_uuid(args.get("note_id"))
        if note_id is None:
            return {"error": "validation_error", "details": "Invalid note_id"}

        note = await self.notes_repo.get_active_note(note_id, self.user_id)
        if not note:
            return {"error": "note_not_found"}

        return {
            "note_id": str(note.id),
            "title": note.title,
            "content": note.content,
            "tags": [t.name for t in note.tags],
            "version": note.version,
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat(),
        }

    async def _handle_list_tags(self, args: Any) -> list[dict[str, Any]]:
        tags, _ = await self.tags_repo.list_tags(
            self.user_id,
            limit=settings.max_tags_per_user,
        )
        result: list[dict[str, Any]] = []
        for tag in tags:
            notes_count = len(tag.notes) if tag.notes else 0  # type: ignore
            result.append(
                {
                    "tag_id": str(tag.id),
                    "name": tag.name,
                    "notes_count": notes_count,
                }
            )
        return result

    # --- Proposal tools ---

    async def _handle_propose_edit_note(self, args: dict[str, Any]) -> dict[str, Any]:
        note_id = self._parse_uuid(args.get("note_id"))
        if note_id is None:
            return {"error": "validation_error", "details": "Invalid note_id"}

        title = args.get("title")
        content = args.get("content")
        if title is None and content is None:
            return {
                "error": "validation_error",
                "details": "At least title or content required",
            }

        note = await self.notes_repo.get_active_note(note_id, self.user_id)
        if not note:
            return {"error": "note_not_found"}

        key = ("edit_note", str(note_id))
        if key in self._proposal_keys:
            return {"error": "duplicate_proposal"}
        self._proposal_keys.add(key)

        proposal = make_proposal(
            "edit_note",
            str(note_id),
            {"title": title, "content": content},
        )
        self.actions.append(proposal)
        return {"proposal_id": proposal["id"], "status": "registered"}

    async def _handle_propose_create_note(self, args: dict[str, Any]) -> dict[str, Any]:
        tags = args.get("tags", [])
        if len(tags) > settings.max_tags_per_note:
            return {
                "error": "validation_error",
                "details": f"Maximum {settings.max_tags_per_note} tags allowed",
            }

        proposal = make_proposal(
            "create_note",
            None,
            {
                "title": args.get("title"),
                "content": args.get("content"),
                "tags": tags,
            },
        )
        self.actions.append(proposal)
        return {"proposal_id": proposal["id"], "status": "registered"}

    async def _handle_propose_delete_note(self, args: dict[str, Any]) -> dict[str, Any]:
        note_id = self._parse_uuid(args.get("note_id"))
        if note_id is None:
            return {"error": "validation_error", "details": "Invalid note_id"}

        note = await self.notes_repo.get_active_note(note_id, self.user_id)
        if not note:
            return {"error": "note_not_found"}

        key = ("delete_note", str(note_id))
        if key in self._proposal_keys:
            return {"error": "duplicate_proposal"}
        self._proposal_keys.add(key)

        proposal = make_proposal(
            "delete_note",
            str(note_id),
            {"note_title": note.title or "Untitled"},
        )
        self.actions.append(proposal)
        return {"proposal_id": proposal["id"], "status": "registered"}

    async def _handle_propose_add_tags(self, args: dict[str, Any]) -> dict[str, Any]:
        note_id = self._parse_uuid(args.get("note_id"))
        if note_id is None:
            return {"error": "validation_error", "details": "Invalid note_id"}

        tags = args.get("tags", [])
        if not tags:
            return {"error": "validation_error", "details": "tags required"}

        note = await self.notes_repo.get_active_note(note_id, self.user_id)
        if not note:
            return {"error": "note_not_found"}

        # Check tag limit
        current_count = len(note.tags) if note.tags else 0
        if current_count + len(tags) > settings.max_tags_per_note:
            return {
                "error": "validation_error",
                "details": f"Would exceed {settings.max_tags_per_note} tags limit",
            }

        key = ("add_tags", str(note_id))
        if key in self._proposal_keys:
            return {"error": "duplicate_proposal"}
        self._proposal_keys.add(key)

        proposal = make_proposal("add_tags", str(note_id), {"tags": tags})
        self.actions.append(proposal)
        return {"proposal_id": proposal["id"], "status": "registered"}

    async def _handle_propose_remove_tags(self, args: dict[str, Any]) -> dict[str, Any]:
        note_id = self._parse_uuid(args.get("note_id"))
        if note_id is None:
            return {"error": "validation_error", "details": "Invalid note_id"}

        tags = args.get("tags", [])
        if not tags:
            return {"error": "validation_error", "details": "tags required"}

        note = await self.notes_repo.get_active_note(note_id, self.user_id)
        if not note:
            return {"error": "note_not_found"}

        key = ("remove_tags", str(note_id))
        if key in self._proposal_keys:
            return {"error": "duplicate_proposal"}
        self._proposal_keys.add(key)

        proposal = make_proposal("remove_tags", str(note_id), {"tags": tags})
        self.actions.append(proposal)
        return {"proposal_id": proposal["id"], "status": "registered"}

    # --- Batch tools ---

    async def _handle_batch_add_tags(self, args: dict[str, Any]) -> dict[str, Any]:
        return await self._register_batch("add_tags", args, has_tags=True)

    async def _handle_batch_remove_tags(self, args: dict[str, Any]) -> dict[str, Any]:
        return await self._register_batch("remove_tags", args, has_tags=True)

    async def _handle_batch_delete(self, args: dict[str, Any]) -> dict[str, Any]:
        return await self._register_batch("delete", args)

    async def _handle_batch_replace(self, args: dict[str, Any]) -> dict[str, Any]:
        pattern = args.get("pattern", "")
        replacement = args.get("replacement", "")
        flags = args.get("flags", [])
        scope = args.get("scope", "content")

        # Validate RE2 pattern
        try:
            re2.compile(pattern)  # type: ignore
        except Exception as e:
            err_str = str(e)
            if any(kw in err_str for kw in ("lookbehind", "lookahead", "backreference")):
                return {"error": "unsupported_pattern", "details": err_str}
            return {"error": "invalid_pattern", "details": err_str}

        params = {
            "pattern": pattern,
            "replacement": replacement,
            "flags": flags,
            "scope": scope,
        }
        return await self._register_batch("replace", args, extra_params=params)

    async def _handle_batch_transform(self, args: dict[str, Any]) -> dict[str, Any]:
        instruction = args.get("instruction", "")
        if not instruction:
            return {
                "error": "validation_error",
                "details": "instruction required",
            }
        params = {"instruction": instruction}
        return await self._register_batch("transform", args, extra_params=params)

    async def _register_batch(
        self,
        operation_type: str,
        args: dict[str, Any],
        has_tags: bool = False,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Common batch registration: validate note_ids, enforce one-batch
        limit, register pending_confirmation."""
        if self._has_batch:
            return {
                "error": "validation_error",
                "details": "Only one batch operation per response",
            }

        raw_ids = args.get("note_ids", [])
        if len(raw_ids) > settings.max_notes_in_bulk:
            return {
                "error": "too_many_notes",
                "max": settings.max_notes_in_bulk,
            }

        valid_ids, excluded_ids = await self._validate_batch_note_ids(raw_ids)
        if not valid_ids:
            return {"error": "no_valid_notes"}

        params = extra_params or {}
        if has_tags:
            params["tags"] = args.get("tags", [])

        pc = make_pending_confirmation(operation_type, valid_ids, params)
        self.actions.append(pc)
        self._has_batch = True

        result: dict[str, Any] = {
            "confirmation_id": pc["id"],
            "status": "awaiting_confirmation",
            "valid_note_count": len(valid_ids),
        }
        if excluded_ids:
            result["excluded_note_ids"] = excluded_ids
        return result

    # --- Private helpers ---

    async def _validate_batch_note_ids(
        self,
        raw_ids: list[str],
    ) -> tuple[list[str], list[str]]:
        """Validate note_ids: return (valid_ids, excluded_ids)."""
        parsed: dict[str, uuid.UUID] = {}
        excluded: list[str] = []
        for raw in raw_ids:
            nid = self._parse_uuid(raw)
            if nid is None:
                excluded.append(raw)
            else:
                parsed[str(nid)] = nid

        if not parsed:
            return [], excluded

        notes = await self.notes_repo.get_active_notes_by_ids(
            list(parsed.values()),
            self.user_id,
        )
        found_ids = {str(n.id) for n in notes}
        valid = [sid for sid in parsed if sid in found_ids]
        excluded.extend(sid for sid in parsed if sid not in found_ids)
        return valid, excluded

    async def _resolve_tag_ids(
        self,
        tag_names: list[str],
    ) -> list[uuid.UUID] | None:
        """Resolve tag names to IDs. Returns None if no names given."""
        if not tag_names:
            return None
        tags = await self.tags_repo.get_tags_by_names(self.user_id, tag_names)
        return [t.id for t in tags] if tags else None

    @staticmethod
    def _parse_uuid(value: Any) -> uuid.UUID | None:
        if value is None:
            return None
        try:
            return uuid.UUID(str(value))
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _format_note_result(
        note: Note,
        relevance_score: float | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "note_id": str(note.id),
            "title": note.title,
            "content_preview": truncate_at_word(note.content or "", 100),
            "tags": [t.name for t in note.tags],
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat(),
        }
        if relevance_score is not None:
            result["relevance_score"] = relevance_score
        return result

    @staticmethod
    def _parse_date_filters(args: dict[str, Any]) -> dict[str, datetime | None]:
        """Parse ISO 8601 date strings into datetime objects for SQL filters."""
        result: dict[str, datetime | None] = {}
        for field in ("created_from", "created_to", "updated_from", "updated_to"):
            val = args.get(field)
            if not val:
                continue
            try:
                result[field] = datetime.fromisoformat(val)
            except ValueError:
                continue
        return result


# endregion
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# region Deterministic bulk proposal generation


async def generate_deterministic_proposals(
    db: AsyncSession,
    user_id: uuid.UUID,
    confirmation: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate proposals for deterministic batch operations (no LLM)."""
    op = confirmation["operation_type"]
    note_ids = confirmation["note_ids"]
    params = confirmation.get("params", {})
    notes_repo = NotesRepository(db)

    proposals: list[dict[str, Any]] = []

    for raw_id in note_ids:
        nid = _safe_uuid(raw_id)
        if nid is None:
            continue
        note = await notes_repo.get_active_note(nid, user_id)
        if not note:
            continue

        if op == "add_tags":
            proposals.append(
                make_proposal(
                    "add_tags",
                    str(nid),
                    {"tags": params.get("tags", [])},
                )
            )
        elif op == "remove_tags":
            proposals.append(
                make_proposal(
                    "remove_tags",
                    str(nid),
                    {"tags": params.get("tags", [])},
                )
            )
        elif op == "delete":
            proposals.append(
                make_proposal(
                    "delete_note",
                    str(nid),
                    {"note_title": note.title or "Untitled"},
                )
            )
        elif op == "replace":
            new_proposals = _apply_replace(note, params)
            proposals.extend(new_proposals)

    return proposals


def _apply_replace(note: Note, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply regex replacement and return edit_note proposal if changed."""
    pattern = params.get("pattern", "")
    replacement = params.get("replacement", "")
    flags_list = params.get("flags", [])
    scope = params.get("scope", "content")

    opts = re2.Options()
    for f in flags_list:
        if f == "i":
            opts.case_sensitive = False
        elif f == "s":
            opts.dot_nl = True
        elif f == "m":
            opts.one_line = False

    compiled = re2.compile(pattern, opts)  # type: ignore
    new_title = note.title
    new_content = note.content
    changed = False

    if scope in ("title", "both") and note.title:
        replaced = compiled.sub(replacement, note.title)  # _Regexp # type: ignore
        if replaced != note.title:
            new_title = replaced  # str # type: ignore
            changed = True

    if scope in ("content", "both") and note.content:
        replaced = compiled.sub(replacement, note.content)  # _Regexp # type: ignore
        if replaced != note.content:
            new_content = replaced  # str # type: ignore
            changed = True

    if not changed:
        return []

    data: dict[str, Any] = {}
    if new_title != note.title:
        data["title"] = new_title
    if new_content != note.content:
        data["content"] = new_content
    return [make_proposal("edit_note", str(note.id), data)]


def _safe_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None


# endregion
# ---------------------------------------------------------------------------
