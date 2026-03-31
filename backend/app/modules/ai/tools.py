"""Planner & Executor tool definitions and backend handlers.

This module defines:
- PLANNER_TOOLS: 13 OpenAI function-calling schemas for the Planner LLM
- EXECUTOR_TOOLS: 4 tool schemas for the Executor LLM (batch_transform)
- ToolExecutor: class that executes tool calls, returning results or
  registering proposals / pending_confirmations in the actions list.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import re2
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.notes.models import Note
from app.modules.notes.repository import NotesRepository
from app.modules.rag.service import RAGService
from app.modules.tags.repository import TagsRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Planner tool schemas (OpenAI function-calling format)
# ---------------------------------------------------------------------------

_SEARCH_NOTES: dict = {
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

_GET_NOTE: dict = {
    "type": "function",
    "function": {
        "name": "get_note",
        "description": (
            "Get the full content of a note. Use only when full content is needed "
            "(editing, detailed analysis). For general answers use content_preview from search_notes."
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

_LIST_TAGS: dict = {
    "type": "function",
    "function": {
        "name": "list_tags",
        "description": "Get all of the user's tags with note counts.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

_PROPOSE_EDIT_NOTE: dict = {
    "type": "function",
    "function": {
        "name": "propose_edit_note",
        "description": "Propose editing an existing note. At least one of title or content must be provided.",
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

_PROPOSE_CREATE_NOTE: dict = {
    "type": "function",
    "function": {
        "name": "propose_create_note",
        "description": "Propose creating a new note.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": 200},
                "content": {"type": "string", "maxLength": 20000},
                "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            },
            "required": [],
        },
    },
}

_PROPOSE_DELETE_NOTE: dict = {
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

_PROPOSE_ADD_TAGS: dict = {
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

_PROPOSE_REMOVE_TAGS: dict = {
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

_BATCH_ADD_TAGS: dict = {
    "type": "function",
    "function": {
        "name": "batch_add_tags",
        "description": "Add tags to multiple notes. Requires user confirmation before execution.",
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

_BATCH_REMOVE_TAGS: dict = {
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

_BATCH_DELETE: dict = {
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

_BATCH_REPLACE: dict = {
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
                "scope": {"type": "string", "enum": ["content", "title", "both"]},
            },
            "required": ["note_ids", "pattern", "replacement"],
        },
    },
}

_BATCH_TRANSFORM: dict = {
    "type": "function",
    "function": {
        "name": "batch_transform",
        "description": (
            "Transform multiple notes using a natural-language instruction. "
            "Each note is processed by a separate LLM call. Requires user confirmation."
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

PLANNER_TOOLS: list[dict] = [
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
# Executor tool schemas (for batch_transform one-shot calls)
# ---------------------------------------------------------------------------

_EXEC_EDIT_NOTE: dict = {
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

_EXEC_ADD_TAGS: dict = {
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

_EXEC_REMOVE_TAGS: dict = {
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

_EXEC_DELETE_NOTE: dict = {
    "type": "function",
    "function": {
        "name": "delete_note",
        "description": "Delete this note.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

EXECUTOR_TOOLS: list[dict] = [
    _EXEC_EDIT_NOTE,
    _EXEC_ADD_TAGS,
    _EXEC_REMOVE_TAGS,
    _EXEC_DELETE_NOTE,
]

# ---------------------------------------------------------------------------
# Read-only tool names (results go back into Planner context)
# ---------------------------------------------------------------------------

READ_TOOL_NAMES = {"search_notes", "get_note", "list_tags"}

# Proposal tool names (register a proposal, return confirmation to Planner)
PROPOSE_TOOL_NAMES = {
    "propose_edit_note",
    "propose_create_note",
    "propose_delete_note",
    "propose_add_tags",
    "propose_remove_tags",
}

# Bulk tool names (register a pending_confirmation)
BATCH_TOOL_NAMES = {
    "batch_add_tags",
    "batch_remove_tags",
    "batch_delete",
    "batch_replace",
    "batch_transform",
}


# ---------------------------------------------------------------------------
# Proposal / confirmation helpers
# ---------------------------------------------------------------------------

def make_proposal(
    proposal_type: str,
    note_id: str | None,
    data: dict,
) -> dict:
    """Create a proposal dict with pending status."""
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
    params: dict,
) -> dict:
    """Create a pending_confirmation dict."""
    return {
        "type": "pending_confirmation",
        "id": str(uuid.uuid4()),
        "status": "pending",
        "operation_type": operation_type,
        "note_ids": note_ids,
        "params": params,
        "summary": None,
    }


# ---------------------------------------------------------------------------
# Summary templates (AIS 2.5)
# ---------------------------------------------------------------------------

def _build_summary(action: dict, new_status: str) -> str:
    """Generate a deterministic summary string when status changes."""
    atype = action.get("type")

    if atype == "proposal":
        ptype = action.get("proposal_type", "")
        data = action.get("data") or {}
        title = data.get("title") or data.get("note_title") or "Untitled"

        templates = {
            ("edit_note", "applied"): f"Edited note \"{title}\"",
            ("edit_note", "dismissed"): f"Dismissed edit for note \"{title}\"",
            ("create_note", "applied"): f"Created note \"{title}\"",
            ("create_note", "dismissed"): "Dismissed note creation",
            ("delete_note", "applied"): f"Deleted note \"{title}\"",
            ("delete_note", "dismissed"): f"Dismissed deletion of note \"{title}\"",
            ("add_tags", "applied"): (
                f"Added tags [{', '.join(data.get('tags', []))}] "
                f"to note \"{title}\""
            ),
            ("add_tags", "dismissed"): f"Dismissed tag addition for note \"{title}\"",
            ("remove_tags", "applied"): (
                f"Removed tags [{', '.join(data.get('tags', []))}] "
                f"from note \"{title}\""
            ),
            ("remove_tags", "dismissed"): f"Dismissed tag removal for note \"{title}\"",
        }
        return templates.get((ptype, new_status), f"{ptype} — {new_status}")

    elif atype == "pending_confirmation":
        op = action.get("operation_type", "")
        n = len(action.get("note_ids", []))
        if new_status == "dismissed":
            return f"{op} for {n} notes — dismissed"
        # confirmed summary is set after proposals are generated
        return f"{op} for {n} notes — confirmed"

    return f"{atype} — {new_status}"


# ---------------------------------------------------------------------------
# ToolExecutor — handles tool calls from Planner
# ---------------------------------------------------------------------------

class ToolExecutor:
    """Executes Planner tool calls, returning JSON results or registering
    proposals/confirmations in the actions accumulator."""

    def __init__(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        actions: list[dict],
    ):
        self.db = db
        self.user_id = user_id
        self.actions = actions
        self.notes_repo = NotesRepository(db)
        self.tags_repo = TagsRepository(db)
        self.rag = RAGService(db)
        # Track proposals per (type, note_id) for dedup
        self._proposal_keys: set[tuple[str, str | None]] = set()

    async def execute(self, name: str, arguments: str) -> str:
        """Execute a tool call and return the JSON result string."""
        try:
            args = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            return json.dumps({"error": "invalid_json", "details": "Could not parse tool arguments"})

        handler = getattr(self, f"_handle_{name}", None)
        if handler is None:
            return json.dumps({"error": "unknown_tool", "details": f"Tool '{name}' not found"})

        try:
            result = await handler(args)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.exception("Tool %s failed", name)
            return json.dumps({"error": "tool_error", "details": str(e)})

    # --- Read tools ---

    async def _handle_search_notes(self, args: dict) -> dict:
        query = args.get("query")
        search_mode = args.get("search_mode")
        limit = min(args.get("limit", 5), settings.max_sources_per_response)
        sort_by = args.get("sort_by")
        sort_order = args.get("sort_order", "desc")

        if sort_by == "relevance" and not query:
            return {"error": "validation_error", "details": "relevance sort requires query"}
        if query and not search_mode:
            return {"error": "validation_error", "details": "search_mode required when query is set"}

        # Semantic search via RAG
        if query and search_mode == "semantic":
            try:
                search_resp = await self.rag.search(self.user_id, query, limit=limit)
                notes_out = []
                for r in search_resp.results:
                    note = await self.notes_repo.get_active_note(r.note_id, self.user_id)
                    if note:
                        notes_out.append({
                            "note_id": str(note.id),
                            "title": note.title,
                            "content_preview": (note.content or "")[:100],
                            "tags": [t.name for t in note.tags],
                            "created_at": note.created_at.isoformat(),
                            "updated_at": note.updated_at.isoformat(),
                            "relevance_score": r.score,
                        })
                return {"total_count": len(notes_out), "notes": notes_out}
            except Exception as e:
                logger.warning("Semantic search failed: %s", e)
                return {"error": "embedding_unavailable", "details": str(e)}

        # Fulltext / filter-based search
        tag_names = args.get("tags", [])
        tag_ids = None
        if tag_names:
            tags = []
            for tn in tag_names:
                t = await self.tags_repo.get_tag_by_name(self.user_id, tn)
                if t:
                    tags.append(t)
            tag_ids = [t.id for t in tags]
            if not tag_ids:
                return {"total_count": 0, "notes": []}

        notes, total = await self.notes_repo.list_notes(
            user_id=self.user_id,
            limit=limit,
            offset=0,
            search=query if (query and search_mode == "fulltext") else None,
            tag_ids=tag_ids,
        )

        # Apply date filters in-memory (simple for small scale)
        notes = self._apply_date_filters(notes, args)

        # Apply exclude_tags filter
        exclude_tag_names = {t.lower() for t in args.get("exclude_tags", [])}
        if exclude_tag_names:
            notes = [
                n for n in notes
                if not any(t.name.lower() in exclude_tag_names for t in n.tags)
            ]

        notes_out = []
        for note in notes[:limit]:
            notes_out.append({
                "note_id": str(note.id),
                "title": note.title,
                "content_preview": (note.content or "")[:100],
                "tags": [t.name for t in note.tags],
                "created_at": note.created_at.isoformat(),
                "updated_at": note.updated_at.isoformat(),
            })

        return {"total_count": total, "notes": notes_out}

    def _apply_date_filters(self, notes: list[Note], args: dict) -> list[Note]:
        result = notes
        for field, attr in [
            ("created_from", "created_at"),
            ("created_to", "created_at"),
            ("updated_from", "updated_at"),
            ("updated_to", "updated_at"),
        ]:
            val = args.get(field)
            if not val:
                continue
            try:
                dt = datetime.fromisoformat(val)
            except ValueError:
                continue
            if "from" in field:
                result = [n for n in result if getattr(n, attr) >= dt]
            else:
                result = [n for n in result if getattr(n, attr) <= dt]
        return result

    async def _handle_get_note(self, args: dict) -> dict:
        try:
            note_id = uuid.UUID(args["note_id"])
        except (KeyError, ValueError):
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

    async def _handle_list_tags(self, args: dict) -> list[dict]:
        from sqlalchemy import func, select
        from app.modules.notes.models import NoteTag

        tags, _ = await self.tags_repo.list_tags(self.user_id, limit=settings.max_tags_per_user)
        result = []
        for tag in tags:
            result.append({
                "tag_id": str(tag.id),
                "name": tag.name,
                "notes_count": len(tag.notes) if hasattr(tag, "notes") and tag.notes else 0,
            })
        return result

    # --- Proposal tools ---

    async def _handle_propose_edit_note(self, args: dict) -> dict:
        try:
            note_id = uuid.UUID(args["note_id"])
        except (KeyError, ValueError):
            return {"error": "validation_error", "details": "Invalid note_id"}

        title = args.get("title")
        content = args.get("content")
        if title is None and content is None:
            return {"error": "validation_error", "details": "At least title or content required"}

        note = await self.notes_repo.get_active_note(note_id, self.user_id)
        if not note:
            return {"error": "note_not_found"}

        key = ("edit_note", str(note_id))
        if key in self._proposal_keys:
            return {"error": "duplicate_proposal"}
        self._proposal_keys.add(key)

        data = {"title": title, "content": content}
        proposal = make_proposal("edit_note", str(note_id), data)
        self.actions.append(proposal)
        return {"proposal_id": proposal["id"], "status": "registered"}

    async def _handle_propose_create_note(self, args: dict) -> dict:
        data = {
            "title": args.get("title"),
            "content": args.get("content"),
            "tags": args.get("tags", []),
        }
        proposal = make_proposal("create_note", None, data)
        self.actions.append(proposal)
        return {"proposal_id": proposal["id"], "status": "registered"}

    async def _handle_propose_delete_note(self, args: dict) -> dict:
        try:
            note_id = uuid.UUID(args["note_id"])
        except (KeyError, ValueError):
            return {"error": "validation_error", "details": "Invalid note_id"}

        note = await self.notes_repo.get_active_note(note_id, self.user_id)
        if not note:
            return {"error": "note_not_found"}

        key = ("delete_note", str(note_id))
        if key in self._proposal_keys:
            return {"error": "duplicate_proposal"}
        self._proposal_keys.add(key)

        data = {"note_title": note.title or "Untitled"}
        proposal = make_proposal("delete_note", str(note_id), data)
        self.actions.append(proposal)
        return {"proposal_id": proposal["id"], "status": "registered"}

    async def _handle_propose_add_tags(self, args: dict) -> dict:
        try:
            note_id = uuid.UUID(args["note_id"])
        except (KeyError, ValueError):
            return {"error": "validation_error", "details": "Invalid note_id"}

        tags = args.get("tags", [])
        if not tags:
            return {"error": "validation_error", "details": "tags required"}

        note = await self.notes_repo.get_active_note(note_id, self.user_id)
        if not note:
            return {"error": "note_not_found"}

        key = ("add_tags", str(note_id))
        if key in self._proposal_keys:
            return {"error": "duplicate_proposal"}
        self._proposal_keys.add(key)

        data = {"tags": tags}
        proposal = make_proposal("add_tags", str(note_id), data)
        self.actions.append(proposal)
        return {"proposal_id": proposal["id"], "status": "registered"}

    async def _handle_propose_remove_tags(self, args: dict) -> dict:
        try:
            note_id = uuid.UUID(args["note_id"])
        except (KeyError, ValueError):
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

        data = {"tags": tags}
        proposal = make_proposal("remove_tags", str(note_id), data)
        self.actions.append(proposal)
        return {"proposal_id": proposal["id"], "status": "registered"}

    # --- Batch tools ---

    async def _validate_batch_note_ids(
        self, raw_ids: list[str],
    ) -> tuple[list[str], list[str]]:
        """Validate note_ids: return (valid_ids, excluded_ids)."""
        if len(raw_ids) > settings.max_notes_in_bulk:
            raise ValueError(f"too_many_notes: max {settings.max_notes_in_bulk}")

        valid, excluded = [], []
        for raw in raw_ids:
            try:
                nid = uuid.UUID(raw)
            except ValueError:
                excluded.append(raw)
                continue
            note = await self.notes_repo.get_active_note(nid, self.user_id)
            if note:
                valid.append(str(nid))
            else:
                excluded.append(raw)
        return valid, excluded

    async def _handle_batch_add_tags(self, args: dict) -> dict:
        return await self._register_batch("add_tags", args, has_tags=True)

    async def _handle_batch_remove_tags(self, args: dict) -> dict:
        return await self._register_batch("remove_tags", args, has_tags=True)

    async def _handle_batch_delete(self, args: dict) -> dict:
        return await self._register_batch("delete", args)

    async def _handle_batch_replace(self, args: dict) -> dict:
        pattern = args.get("pattern", "")
        replacement = args.get("replacement", "")
        flags = args.get("flags", [])
        scope = args.get("scope", "content")

        # Validate RE2 pattern
        try:
            re2.compile(pattern)
        except Exception as e:
            err_str = str(e)
            if "lookbehind" in err_str or "lookahead" in err_str or "backreference" in err_str:
                return {"error": "unsupported_pattern", "details": err_str}
            return {"error": "invalid_pattern", "details": err_str}

        params = {
            "pattern": pattern,
            "replacement": replacement,
            "flags": flags,
            "scope": scope,
        }
        return await self._register_batch("replace", args, extra_params=params)

    async def _handle_batch_transform(self, args: dict) -> dict:
        instruction = args.get("instruction", "")
        if not instruction:
            return {"error": "validation_error", "details": "instruction required"}

        params = {"instruction": instruction}
        return await self._register_batch("transform", args, extra_params=params)

    async def _register_batch(
        self,
        operation_type: str,
        args: dict,
        has_tags: bool = False,
        extra_params: dict | None = None,
    ) -> dict:
        raw_ids = args.get("note_ids", [])
        try:
            valid_ids, excluded_ids = await self._validate_batch_note_ids(raw_ids)
        except ValueError as e:
            return {"error": str(e).split(":")[0], "max": settings.max_notes_in_bulk}

        if not valid_ids:
            return {"error": "no_valid_notes"}

        params = extra_params or {}
        if has_tags:
            params["tags"] = args.get("tags", [])

        pc = make_pending_confirmation(operation_type, valid_ids, params)
        self.actions.append(pc)

        result: dict[str, Any] = {
            "confirmation_id": pc["id"],
            "status": "awaiting_confirmation",
            "valid_note_count": len(valid_ids),
        }
        if excluded_ids:
            result["excluded_note_ids"] = excluded_ids
        return result


# ---------------------------------------------------------------------------
# Bulk operation executor (runs after user confirmation)
# ---------------------------------------------------------------------------

async def generate_deterministic_proposals(
    db: AsyncSession,
    user_id: uuid.UUID,
    confirmation: dict,
) -> list[dict]:
    """Generate proposals for deterministic batch operations (no LLM needed)."""
    op = confirmation["operation_type"]
    note_ids = confirmation["note_ids"]
    params = confirmation.get("params", {})
    notes_repo = NotesRepository(db)

    proposals: list[dict] = []

    for raw_id in note_ids:
        try:
            nid = uuid.UUID(raw_id)
        except ValueError:
            continue
        note = await notes_repo.get_active_note(nid, user_id)
        if not note:
            continue

        if op == "add_tags":
            proposals.append(make_proposal(
                "add_tags", str(nid), {"tags": params.get("tags", [])},
            ))

        elif op == "remove_tags":
            proposals.append(make_proposal(
                "remove_tags", str(nid), {"tags": params.get("tags", [])},
            ))

        elif op == "delete":
            proposals.append(make_proposal(
                "delete_note", str(nid), {"note_title": note.title or "Untitled"},
            ))

        elif op == "replace":
            new_proposals = _apply_replace(note, params)
            proposals.extend(new_proposals)

    return proposals


def _apply_replace(note: Note, params: dict) -> list[dict]:
    """Apply regex replacement and return an edit_note proposal if changed."""
    pattern = params.get("pattern", "")
    replacement = params.get("replacement", "")
    flags_list = params.get("flags", [])
    scope = params.get("scope", "content")

    re2_flags = 0
    # RE2 Python binding: re2.IGNORECASE etc.
    flag_map = {"i": re2.IGNORECASE, "m": re2.MULTILINE, "s": re2.DOTALL}
    for f in flags_list:
        if f in flag_map:
            re2_flags |= flag_map[f]

    compiled = re2.compile(pattern, re2_flags)
    new_title = note.title
    new_content = note.content
    changed = False

    if scope in ("title", "both") and note.title:
        replaced = compiled.sub(replacement, note.title)
        if replaced != note.title:
            new_title = replaced
            changed = True

    if scope in ("content", "both") and note.content:
        replaced = compiled.sub(replacement, note.content)
        if replaced != note.content:
            new_content = replaced
            changed = True

    if changed:
        data: dict = {}
        if new_title != note.title:
            data["title"] = new_title
        if new_content != note.content:
            data["content"] = new_content
        return [make_proposal("edit_note", str(note.id), data)]
    return []
