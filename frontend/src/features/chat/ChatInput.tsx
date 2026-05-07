import { useRef, useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { notesApi } from '@/api/notes';
import { useChatStore } from '@/stores/chat';
import { useUIStore } from '@/stores/ui';
import { t } from '@/i18n';
import type { NoteListItem } from '@/types/api';

interface ChatInputProps {
  onSend: (content: string, attachedNoteIds: string[]) => void;
  disabled: boolean;
  onStop: () => void;
}

export function ChatInput({ onSend, disabled, onStop }: ChatInputProps) {
  const s = t();
  const { isGenerating } = useChatStore();
  const { attachedNoteIds, detachNote, clearAttachedNotes } = useUIStore();
  const [text, setText] = useState('');
  const taRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
  }, [text]);

  const { data } = useQuery({
    queryKey: ['notes'],
    queryFn: () => notesApi.list({ limit: 200 }),
    staleTime: 60_000,
  });

  const allNotes: NoteListItem[] = data?.items ?? [];
  const attachedNotes = allNotes.filter((n) => attachedNoteIds.includes(n.id));

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    if (!text.trim() || disabled || isGenerating) return;
    onSend(text.trim(), attachedNoteIds);
    setText('');
    clearAttachedNotes();
  }

  const charCount = text.length;
  const isOverLimit = charCount > 4000;

  return (
    <div className="flex-shrink-0 border-t border-border px-3 py-3">
      {/* Attached chips */}
      {attachedNotes.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {attachedNotes.map((n) => (
            <span
              key={n.id}
              className="inline-flex items-center gap-1 px-2 py-0.5 bg-bg-selected rounded text-[11px] text-fg-link"
            >
              📄 {n.title ?? s.notes.untitled}
              <button
                className="text-fg-muted hover:text-fg ml-0.5"
                onClick={() => detachNote(n.id)}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Input row */}
      <div
        className={`flex items-end gap-2 bg-bg-input border rounded-md px-2.5 py-1.5
          ${isOverLimit ? 'border-danger' : 'border-border focus-within:border-border-focus'}`}
      >
        <textarea
          ref={taRef}
          rows={1}
          className="flex-1 bg-transparent border-none outline-none resize-none text-[13px] text-fg placeholder:text-fg-muted min-h-[20px] max-h-[120px] leading-relaxed py-0.5"
          placeholder={s.chat.placeholder}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled && !isGenerating}
          maxLength={4100}
        />

        {/* Char hint */}
        {charCount > 3500 && (
          <span className={`text-[10px] flex-shrink-0 mb-0.5 ${isOverLimit ? 'text-danger' : 'text-fg-muted'}`}>
            {s.chat.maxCharsHint.replace('{count}', String(charCount))}
          </span>
        )}

        {/* Send / Stop button */}
        <button
          className={`flex-shrink-0 w-7 h-7 flex items-center justify-center rounded text-white mb-0.5
            ${isGenerating ? 'bg-danger hover:opacity-90' : 'bg-accent hover:opacity-90 disabled:opacity-40'}`}
          disabled={!isGenerating && (disabled || !text.trim() || isOverLimit)}
          onClick={isGenerating ? onStop : submit}
          title={isGenerating ? s.chat.stop : s.chat.send}
        >
          {isGenerating ? (
            <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
              <rect x="3" y="3" width="18" height="18" rx="2" />
            </svg>
          ) : (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
