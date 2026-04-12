# Nocturn Frontend — Functional Requirements

> Implementation spec. Tech stack: React 19, TypeScript, Vite, Tailwind CSS, CodeMirror 6, Radix UI.
> Backend API docs: `GET /api/docs` (Swagger), `GET /api/openapi.json`.

---

## 1. Layout

The app has **three panels** arranged horizontally:

```
┌──────────┬────────────────────────────┬──────────────────┐
│          │                            │                  │
│  Navbar  │     Editor (tabs)          │   AI Chat        │
│  (fixed) │     (resizable)            │   (resizable)    │
│          │                            │                  │
└──────────┴────────────────────────────┴──────────────────┘
```

- **Navbar** — fixed width (~56–64px), not resizable. Vertical icon-based navigation.
- **Editor** — occupies the remaining space. Supports multiple tabs. Resizable border with Chat.
- **Chat** — collapsible right panel. Resizable border with Editor.

Panel borders between Editor and Chat are **draggable** (resizable).
Navbar width is fixed.

---

## 2. Navbar (left panel)

Minimal, icon-based vertical bar. Contains from top to bottom:

### 2.1 Top section
- **App logo / brand icon** — top of navbar.
- **New note button** — creates a blank note and opens it in a new Editor tab.

### 2.2 Middle section — navigation items
Each item opens a **list view as a tab** in the Editor area (see §3.3):

- **All notes** — opens a list-view tab showing all user's notes (with search and sort). This is the primary way to browse the full note collection.
- **Search** — opens a search tab in the Editor (see §3.4). Combines semantic search (`POST /api/rag/search`) with manual tag filtering. The search input sends the query to the RAG endpoint; results are displayed as a list of note chunks with relevance scores. A tag filter bar allows narrowing results by one or more tags (AND logic). Clicking a result opens the parent note in an Editor tab.
- **Recent notes** — shows 5 most recently edited notes (always visible as a small list, clicking a note opens it in an Editor tab).
- **Tags** — shows all user tags. Clicking a tag opens a list-view tab in the Editor filtered by that tag.
- **Trash** — opens a list-view tab in the Editor showing soft-deleted notes.

### 2.3 Proposal badge
- When there are **pending proposals** (status = `pending`) from any AI message, a **badge counter** is shown on the navbar — similar to the Source Control badge in VS Code.
- The badge shows the total count of unresolved proposals across all sessions.
- Clicking the badge opens/focuses the Chat panel.

### 2.4 Bottom section
- **Theme toggle** — switch between dark and light mode (see §8).
- **User menu** — avatar/icon with dropdown: nickname, logout, language switch.

---

## 3. Editor (center panel)

### 3.1 Tab bar
- Horizontal tab bar at the top. Each tab shows the note title (or "Untitled").
- **Unlimited tabs** — when they overflow, the tab bar scrolls horizontally.
- Active tab is visually highlighted.
- Each tab has a **close button** (`×`). Modified (unsaved) tabs show a dot indicator.
- Tabs can be **reordered** by drag & drop within the tab bar.

### 3.2 Note editing tab
When a note is opened, the tab contains:

- **Title input** — editable inline field at the top.
- **Tag bar** — shows attached tags as chips with `×` to remove. Has a `+` button to add tags (dropdown/autocomplete from user's tags, or create new).
- **Markdown editor** — CodeMirror 6 with:
  - Live Preview mode (hide markdown syntax on unfocused lines — already implemented).
  - Obsidian-like dark/light theme.
  - Auto-save with 600ms debounce.
  - Optimistic concurrency (send `version` on each save, handle 409 Conflict).

#### 3.2.1 Proposal overlay in editor
When a proposal of type `edit_note` targets the note currently open in a tab:

- The editor switches to **inline diff mode**:
  - **Deleted text** — highlighted in red background, **read-only** (cannot be edited by the user).
  - **Added text** — highlighted in green background, **editable** (user can tweak the proposed changes before applying).
  - Unchanged text is shown normally.
- A **toolbar** appears at the top of the editor:
  - **"Apply"** button — accepts the full proposed change (including any user tweaks to the green sections) and updates the note.
  - **"Dismiss"** button — rejects the proposal, restores the original content.
  - **Proposal summary** text (from `proposal.summary`).
- Applying or dismissing the proposal sends `PATCH /api/ai/sessions/{session_id}/messages/{message_id}/actions/{action_id}` with the corresponding status.
- **One proposal at a time per tab.** If multiple proposals target the same note, they queue.

### 3.3 List-view tab
Opened when clicking a tag or "Trash" in the Navbar. Shows:

- **Tab title** — tag name (e.g. `#work`) or "Trash".
- **Searchable list** of notes matching the filter.
- Each list item shows: title, date, preview snippet.
- Clicking a note **opens it in a new Editor tab** (or focuses the existing tab if already open).
- For Trash: each item has a **"Restore"** button and a **"Delete permanently"** button.

### 3.4 Search tab
Opened from the Search button in the Navbar. A dedicated tab for finding notes:

- **Search input** at the top — sends the query to `POST /api/rag/search` (semantic/vector search). Results update on submit (Enter or search button), not on every keystroke.
- **Tag filter bar** below the search input — shows all user tags as toggleable chips. Selecting tags filters results to notes that have **all** selected tags (AND logic). Tag filtering is applied client-side on top of the RAG results.
- **Results list** — each item shows:
  - Note title.
  - Matching chunk text (highlighted/truncated).
  - Relevance score (as a subtle indicator, e.g. bar or percentage).
  - Parent note's tags as small badges.
- Clicking a result **opens the parent note** in an Editor tab (or focuses it if already open).
- **Empty state**: "Enter a query to search" before first search; "No results found" after a search with no matches.
- The search tab is a singleton — opening Search again focuses the existing tab rather than creating a duplicate.

### 3.5 Tab behavior
- Opening a note that's already in a tab **focuses that tab** (no duplicates).
- Closing the last tab shows a welcome/empty state.
- Tab state (which tabs are open, which is active) is **persisted in localStorage** and restored on page load.

---

## 4. AI Chat (right panel)

### 4.1 Panel
- Collapsible — can be opened/closed via navbar icon or hotkey.
- When closed, the Editor takes the full remaining width.
- When open, resizable border with the Editor panel.

### 4.2 Session management
- **Session list** — accessible via a dropdown/popover in the Chat header. Shows all sessions sorted by `last_message_at` desc.
- **New session** button — creates a new session.
- **Delete session** — available in the session list (per-session action).
- **Current session title** — displayed in the Chat header. Editable on click.

### 4.3 Message display
- Messages are displayed chronologically (oldest first), scrollable.
- **User messages** — right-aligned or visually distinct. Show attached note titles (if any) as clickable chips that open the note in an Editor tab.
- **Assistant messages** — left-aligned. Rendered as Markdown.
- **Streaming** — incoming text appears token-by-token with a blinking cursor indicator.
- **Loading state** — bouncing dots when waiting for the first token.

### 4.4 Proposals in chat
Each assistant message may contain **actions** (`actions` array). They are rendered inline within the message:

#### 4.4.1 Proposal card
For actions with `type: "proposal"`:

- Shows: `summary`, `proposal_type`, and `status`.
- Status-specific rendering:
  - `pending` — "Apply" and "Dismiss" buttons visible.
  - `applied` — green checkmark, buttons disabled, text "Applied".
  - `dismissed` — grey strike-through, text "Dismissed".
- For `edit_note` proposals: an additional **"Preview"** button that opens/focuses the note tab and activates the inline diff overlay (§3.2.1).
- For `create_note` proposals: "Apply" creates the note and opens it in a new tab.
- For `delete_note` proposals: "Apply" soft-deletes the note. If the note is open in a tab, the tab closes.
- For `add_tags` / `remove_tags` proposals: "Apply" modifies the tags. If the note is open, the tag bar updates.

#### 4.4.2 Pending confirmation card
For actions with `type: "pending_confirmation"`:

- Shows: `summary`, `operation_type`, count of affected notes (`note_ids.length`).
- Status-specific rendering:
  - `pending` — "Confirm" and "Dismiss" buttons.
  - `confirmed` — shows the resulting individual proposals (streamed back via SSE).
  - `dismissed` — grey, "Dismissed".
- "Confirm" calls `POST /api/ai/sessions/{id}/confirm/{confirmation_id}` (SSE stream).
- "Dismiss" calls `POST /api/ai/sessions/{id}/dismiss/{confirmation_id}`.

#### 4.4.3 Cross-panel proposal sync
- When a proposal is **applied or dismissed from the Editor** (§3.2.1), the Chat panel **updates the corresponding proposal card** status in real time (no page reload).
- When a proposal is **applied or dismissed from the Chat**, the Editor tab (if the note is open) **updates accordingly** — removes the diff overlay or applies the change.
- This is done via shared state in the chat store — both panels read from and write to the same state.

### 4.5 Session locking
- When `POST /api/ai/sessions/{id}/messages` returns a `409 Conflict` (another generation is in progress), the Chat panel shows a **non-intrusive banner**: "Generation already in progress".
- The send button is disabled while `isStreaming = true`.
- `POST /api/ai/sessions/{id}/cancel` is available via a stop button during streaming.

### 4.6 Input area

#### 4.6.1 Message input
- Auto-expanding textarea (up to ~120px max height), then scrollable.
- `Enter` sends, `Shift+Enter` for newline.
- Send button on the right. Disabled when input is empty or streaming.
- Stop button replaces send button during streaming.

#### 4.6.2 Note attachment
Three ways to attach notes to a message:

1. **Drag & drop** — drag a note from the Navbar's recent list or from a list-view tab into the Chat input area. Visual drop zone indicator appears on drag-over.
2. **Inline search** — typing `@` in the input opens a popup search (autocomplete) of the user's notes. Selecting a note attaches it.
3. **Attach button** — `+` button next to the input → opens a searchable note picker popup.

Attached notes are shown as **chips** above the input area, each with:
- Note title (truncated).
- `×` button to detach.

**Notes do NOT detach after sending a message.** They persist until the user explicitly removes them. This allows the user to ask multiple follow-up questions about the same notes.

---

## 5. SSE Streaming Protocol

The frontend must handle the SSE stream from `POST /api/ai/sessions/{id}/messages`.

### 5.1 Pre-validation
Before SSE starts, the server may return a **JSON error** instead of a stream.
The client must check the response `Content-Type`:
- `application/json` — parse as error (`{detail: string}`), show as toast.
- `text/event-stream` — process as SSE.

### 5.2 SSE events

| Event | `data` payload | Frontend action |
|-------|----------------|-----------------|
| `ai:text_delta` | `{"delta": "..."}` | Append to streaming text buffer, render incrementally. |
| `ai:proposal` | `{Proposal object}` | Add to current message's actions list. If the target note is open in an Editor tab, show a notification badge. |
| `ai:pending_confirmation` | `{PendingConfirmation}` | Add to current message's actions list. Render confirmation card. |
| `ai:error` | `{"code": "...", "message": "..."}` | Show error toast. If `code === "conflict"`, show session lock banner. |
| `ai:done` | `{"message": {Message}}` | Replace optimistic messages with the server's final message. Clear streaming state. Refresh session title in the session list. |

### 5.3 Cancellation
- `AbortController` on the fetch request for client-side abort.
- `POST /api/ai/sessions/{id}/cancel` for server-side abort (Redis signal).
- Both should be triggered when the user clicks the stop button.

### 5.4 Reconnection
- SSE streams are **not reconnected** on disconnect — each message is a one-shot stream.
- On unexpected disconnect (no `ai:done` received), refresh the session messages via `GET /api/ai/sessions/{id}/messages` to sync state.

---

## 6. Trash

- Accessed via Trash icon in the Navbar → opens a list-view tab (§3.3).
- Lists soft-deleted notes (`GET /api/notes?deleted=true`).
- Each item shows title, deletion date, and two actions:
  - **Restore** → `POST /api/notes/{id}/restore` → removes from trash, note appears in recent.
  - **Delete permanently** → `DELETE /api/notes/{id}?permanent=true` → confirmation dialog first.
- Restored notes can be opened immediately in an Editor tab.

---

## 7. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | Create a new note and open in a new tab |
| `Ctrl+S` | Force-save the current note (flush debounce timer) |
| `Ctrl+W` | Close the active Editor tab |
| `Ctrl+Shift+P` | Toggle the AI Chat panel |
| `Ctrl+Delete` | Soft-delete the current note |
| `Ctrl+Z` | Undo (within CodeMirror — already built-in) |
| `Ctrl+Y` / `Ctrl+Shift+Z` | Redo (within CodeMirror — already built-in) |

- Shortcuts should be **configurable** in the future, but hardcoded for now.
- Shortcuts must not conflict with browser defaults where possible.
- On macOS: `Ctrl` → `Cmd`.

---

## 8. Theming

- **Two themes**: dark (current) and light.
- Toggle via the Navbar (§2.4).
- Theme preference is **persisted in localStorage**.
- On first visit, **respect system preference** (`prefers-color-scheme`).
- All colors must be defined via CSS custom properties (already the case with `@theme` in `index.css`). Switching themes swaps the property values.
- CodeMirror theme must also switch (separate highlight style for light mode).

---

## 9. Internationalization (i18n)

- **Two languages**: Russian (`ru`) and English (`en`).
- Language switcher in the user menu (Navbar §2.4).
- Language preference persisted in localStorage.
- Default: browser language, fallback to `ru`.
- All user-facing strings must be extracted into translation files — no hardcoded text in components.
- Date/time formatting respects the selected locale.

---

## 10. Notifications (Toasts)

- **Error toasts** — shown on API errors, SSE errors, network failures. Red/destructive style. Auto-dismiss after 5 seconds, with a close button.
- **Warning toasts** — shown on 409 Conflict (version mismatch, session lock). Yellow/amber style.
- **No success toasts** — avoid noise. Success is communicated by the UI state change itself (e.g. proposal status changes to "Applied").
- **Position**: bottom-right corner, stacked.
- **Max visible**: 3 toasts at a time, older ones are dismissed.

---

## 11. Authentication

### 11.1 Pages (public, no Navbar/Editor/Chat)
- **Login** — email + password form. Link to Register and Forgot Password.
- **Register** — email + password + nickname form. Link to Login.
- **Confirm Email** — reads token from URL query param, calls API, shows result.
- **Forgot Password** — email form → sends reset email.
- **Reset Password** — reads token from URL, new password form.

### 11.2 Token management
- Access token stored in memory (not localStorage — XSS protection).
- Refresh token in httponly cookie (set by backend).
- On 401 response: attempt `POST /api/auth/refresh`. If refresh fails → redirect to Login.
- On app load: call `GET /api/auth/me` to restore session. Show loading spinner until resolved.

### 11.3 Route guards
- **AuthGuard** — redirects to `/login` if not authenticated.
- **GuestOnly** — redirects to `/` if already authenticated (for login/register pages).

---

## 12. State Management

React Context-based stores (no Redux/Zustand):

### 12.1 AuthStore
- `user`, `loading`, `login()`, `register()`, `logout()`, `refresh()`.

### 12.2 NotesStore
- `notes[]`, `tags[]`, `currentNote`, `selectedNoteId`, `saving`.
- `createNote()`, `updateNote()`, `deleteNote()`, `restoreNote()`.
- `fetchNotes()`, `fetchTags()`, `selectNote()`.
- `addTagToNote()`, `removeTagFromNote()`, `createTag()`.
- Debounced save with optimistic updates and version-based concurrency.

### 12.3 ChatStore
- `sessions[]`, `currentSessionId`, `messages[]`, `streamingText`, `isStreaming`.
- `attachedNoteIds[]` — persists across messages until explicitly removed.
- `pendingProposalCount` — computed, drives the Navbar badge.
- `sendMessage()`, `cancelGeneration()`.
- `applyAction()`, `dismissAction()`, `confirmBulk()`, `dismissBulk()`.
- `attachNote()`, `detachNote()`.

### 12.4 TabStore (new)
- `tabs[]` — ordered list of open tabs. Each tab: `{id, type: "note" | "list", noteId?, filter?, title}`.
- `activeTabId`.
- `openNote(noteId)` — opens or focuses a tab.
- `openList(filter)` — opens a tag-filter or trash list tab.
- `closeTab(tabId)`.
- `reorderTabs(fromIndex, toIndex)`.
- Persisted in localStorage.

### 12.5 ThemeStore (new)
- `theme: "dark" | "light"`.
- `toggleTheme()`.
- Synced to `<html>` class and localStorage.

### 12.6 I18nStore (new)
- `locale: "ru" | "en"`.
- `t(key)` — translation function.
- `setLocale()`.

---

## 13. API Integration

### 13.1 HTTP client
- Base URL from Vite env or proxy config.
- JWT access token in `Authorization: Bearer` header.
- Auto-refresh on 401 (call `/api/auth/refresh`, retry original request).
- Typed error handling (`ApiError` class with status code and detail).

### 13.2 Endpoints used

**Auth**: register, login, refresh, logout, confirm-email, request-password-reset, reset-password, resend-confirmation, me.

**Notes**: create, list, get, update, delete (soft + permanent), restore, update-tags, batch-get.

**Tags**: create, list, get, update, delete.

**AI**: create-session, list-sessions, update-session, delete-session, get-messages, send-message (SSE), cancel, update-action, confirm-bulk (SSE), dismiss-bulk.

**RAG**: search (used by the AI backend, but may be exposed for client-side search in the future).

---

## 14. Proposal Lifecycle (end-to-end)

```
AI generates proposal
        │
        ▼
  ┌─────────────┐
  │   pending    │  ← shown in Chat card + badge on Navbar
  └──────┬──────┘
         │
    ┌────┴─────┐
    │          │
    ▼          ▼
 [Chat]    [Editor]     ← user can act from either place
    │          │
    ▼          ▼
  PATCH /actions/{id}   ← same API call from both
    │
    ├─► status: "applied"   → execute action, update note, sync both panels
    │
    └─► status: "dismissed" → no action, grey out in both panels
```

### 14.1 Proposal types and their UI

| `proposal_type` | Chat card | Editor behavior |
|---|---|---|
| `edit_note` | Summary + "Preview" / "Apply" / "Dismiss" | Inline diff overlay in the note tab (§3.2.1) |
| `create_note` | Summary + "Apply" / "Dismiss" | Apply → creates note, opens in new tab |
| `delete_note` | Summary + "Apply" / "Dismiss" | Apply → soft-deletes note, closes tab if open |
| `add_tags` | Summary + tag names + "Apply" / "Dismiss" | Apply → updates tag bar in the note tab |
| `remove_tags` | Summary + tag names + "Apply" / "Dismiss" | Apply → updates tag bar in the note tab |

### 14.2 Inline diff (edit_note proposals)

The diff is computed client-side by comparing `currentNote.content` with `proposal.data.content` (the proposed new content).

Visual rules:
- **Removed lines/words** — red background (`bg-red-500/20`), strikethrough, **read-only**.
- **Added lines/words** — green background (`bg-green-500/20`), **editable** by the user.
- **Unchanged text** — normal rendering.

The diff granularity should be **word-level** for readability (not character-level).

When the user clicks **"Apply"**:
- The final content is the proposed content **with any user edits** to the green sections.
- This content is sent to the backend via the proposal apply action.
- The note's `version` is incremented server-side.

When the user clicks **"Dismiss"**:
- The original content is restored. The diff overlay is removed.

---

## 15. Drag & Drop

### 15.1 Note → Chat attachment
- **Source**: note items in Navbar recent list or in list-view tabs.
- **Target**: Chat input area.
- **Visual feedback**: drop zone highlight on the Chat input when dragging over it.
- **Result**: note is added to `attachedNoteIds` in ChatStore.

### 15.2 Tab reordering
- **Source/Target**: tabs in the Editor tab bar.
- **Visual feedback**: drop indicator between tabs.
- **Result**: tab order is updated in TabStore.

---

## 16. Loading & Empty States

| Context | State |
|---------|-------|
| App startup | Full-screen spinner while checking auth (`GET /api/auth/me`) |
| Note list loading | Skeleton placeholders in list |
| Note content loading | Skeleton in editor area |
| Empty note list | "No notes yet" + "Create note" button |
| Empty trash | "Trash is empty" |
| Empty chat | "Ask the AI assistant a question" + hint text |
| No sessions | Same as empty chat |
| Search with no results | "Nothing found" |
