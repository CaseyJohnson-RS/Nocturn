import { useUIStore, tabKey, type TabId, type SidebarPanel } from '@/stores/ui';
import { useChatStore } from '@/stores/chat';
import { lazy, Suspense, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { notesApi } from '@/api/notes';
import { t } from '@/i18n';
import type { NoteResponse, Proposal } from '@/types/api';

const NoteList    = lazy(() => import('@/features/notes/NoteList'));
const SearchPanel = lazy(() => import('@/features/notes/SearchPanel'));
const TagsPanel   = lazy(() => import('@/features/notes/TagsPanel'));
const TrashPanel  = lazy(() => import('@/features/notes/TrashPanel'));
const NoteEditor  = lazy(() => import('@/features/notes/NoteEditor'));
const AdminPanel  = lazy(() => import('@/features/admin/AdminPanel'));

function panelTabLabel(panel: SidebarPanel): string {
  const s = t();
  const labels: Record<SidebarPanel, string> = {
    notes:  s.notes.notes,
    search: s.notes.search,
    tags:   s.notes.tags,
    trash:  s.notes.trash,
    admin:  s.admin.admin,
  };
  return labels[panel];
}

function NoteTabLabel({ noteId }: { noteId: string }) {
  const s = t();
  const { data } = useQuery<NoteResponse>({
    queryKey: ['note', noteId],
    queryFn: () => notesApi.get(noteId),
    staleTime: Infinity,
  });
  return <>{data?.title || s.notes.untitled}</>;
}

function TabLabel({ tab }: { tab: TabId }) {
  if (tab.type === 'panel') return <>{panelTabLabel(tab.panel)}</>;
  if (tab.type === 'note') return <NoteTabLabel noteId={tab.id} />;
  return <>Diff</>;
}

function TabIcon({ tab }: { tab: TabId }) {
  const sz = { width: 12, height: 12, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.75, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, flexShrink: 0 };
  if (tab.type === 'note') return (
    <svg {...sz}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
    </svg>
  );
  if (tab.type === 'diff') return (
    <svg {...sz}>
      <line x1="5" y1="12" x2="19" y2="12"/>
      <polyline points="12 5 19 12 12 19"/>
    </svg>
  );
  // panel
  const panel = tab.panel;
  if (panel === 'notes') return (
    <svg {...sz}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
    </svg>
  );
  if (panel === 'search') return (
    <svg {...sz}>
      <circle cx="11" cy="11" r="8"/>
      <line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
  );
  if (panel === 'tags') return (
    <svg {...sz}>
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>
      <line x1="7" y1="7" x2="7.01" y2="7"/>
    </svg>
  );
  if (panel === 'trash') return (
    <svg {...sz}>
      <polyline points="3 6 5 6 21 6"/>
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
    </svg>
  );
  if (panel === 'admin') return (
    <svg {...sz}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
  );
  return null;
}

function NoteTabStatusDot({ noteId }: { noteId: string }) {
  const saveStatus = useUIStore((s) => s.noteTabStatus[noteId] ?? null);
  const messages = useChatStore((s) => s.messages);

  let hasDeleteProposal = false;
  let hasAIProposal = false;
  for (const msg of messages) {
    for (const action of msg.actions ?? []) {
      const p = action as Proposal;
      if (p.type === 'proposal' && p.note_id === noteId && p.status === 'pending') {
        if (p.proposal_type === 'delete_note') hasDeleteProposal = true;
        else hasAIProposal = true;
      }
    }
  }

  let color: string;
  let pulse = false;
  if (saveStatus === 'conflict' || hasDeleteProposal) {
    color = 'var(--color-danger)';
  } else if (saveStatus === 'saving') {
    color = 'var(--color-warning)';
    pulse = true;
  } else if (saveStatus === 'dirty') {
    color = 'var(--color-warning)';
  } else if (hasAIProposal) {
    color = 'var(--color-accent)';
  } else {
    color = 'var(--color-success)';
  }

  return (
    <span
      className={pulse ? 'save-dot-pulse' : undefined}
      style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: color, flexShrink: 0 }}
    />
  );
}

export function CenterPanel() {
  const { openTabs, activeTabKey, closeTab, setActiveTab, reorderTabs } = useUIStore();

  const dragIndexRef = useRef<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const activeTab = openTabs.find((tab) => tabKey(tab) === activeTabKey) ?? null;

  return (
    <div className="flex-1 flex flex-col overflow-hidden min-w-0">
      {/* Tab bar */}
      {openTabs.length > 0 && (
        <div
          className="flex-shrink-0 flex overflow-x-auto border-b border-border"
          style={{ height: 'var(--tabbar-h)', background: 'var(--color-bg-tab)' }}
        >
          {openTabs.map((tab, index) => {
            const key = tabKey(tab);
            const isActive = key === activeTabKey;
            const isDropTarget = dragOverIndex === index && dragIndexRef.current !== index;
            return (
              <div
                key={key}
                draggable
                className={`relative flex-shrink-0 flex items-center gap-2 cursor-pointer border-r border-border select-none
                  ${isActive ? 'bg-bg-base text-fg border-t-2 border-t-accent' : 'text-fg-muted hover:bg-bg-hover hover:text-fg'}`}
                style={{ padding: '0 14px 0 12px', maxWidth: '200px', minWidth: '80px' }}
                onClick={() => setActiveTab(tab)}
                onDragStart={() => { dragIndexRef.current = index; }}
                onDragOver={(e) => { e.preventDefault(); setDragOverIndex(index); }}
                onDrop={(e) => {
                  e.preventDefault();
                  if (dragIndexRef.current !== null) reorderTabs(dragIndexRef.current, index);
                  setDragOverIndex(null);
                }}
                onDragEnd={() => { dragIndexRef.current = null; setDragOverIndex(null); }}
                onDragLeave={() => setDragOverIndex(null)}
              >
                {isDropTarget && (
                  <div className="absolute left-0 inset-y-0 w-0.5 bg-accent z-10" />
                )}
                <TabIcon tab={tab} />
                {tab.type === 'note' && <NoteTabStatusDot noteId={tab.id} />}
                <span
                  className="text-[12px] flex-1 min-w-0 truncate"
                  style={{ lineHeight: '1' }}
                >
                  <TabLabel tab={tab} />
                </span>
                <button
                  className="flex-shrink-0 flex items-center justify-center rounded w-4 h-4 text-[13px] leading-none text-fg-disabled hover:text-fg hover:bg-bg-hover transition-colors"
                  onClick={(e) => { e.stopPropagation(); closeTab(tab); }}
                >
                  ×
                </button>
              </div>
            );
          })}

          {/* Trailing drop zone — allows dropping after the last tab */}
          <div
            className="relative flex-1 min-w-4"
            onDragOver={(e) => { e.preventDefault(); setDragOverIndex(openTabs.length); }}
            onDrop={(e) => {
              e.preventDefault();
              if (dragIndexRef.current !== null) reorderTabs(dragIndexRef.current, openTabs.length);
              setDragOverIndex(null);
            }}
            onDragLeave={() => setDragOverIndex(null)}
          >
            {dragOverIndex === openTabs.length && (
              <div className="absolute left-0 inset-y-0 w-0.5 bg-accent" />
            )}
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        <Suspense fallback={null}>
          {activeTab === null && <EmptyState />}
          {activeTab?.type === 'note' && <NoteEditor key={activeTab.id} noteId={activeTab.id} />}
          {activeTab?.type === 'diff' && <EmptyState />}
          {activeTab?.type === 'panel' && <PanelView panel={activeTab.panel} />}
        </Suspense>
      </div>
    </div>
  );
}

function PanelView({ panel }: { panel: SidebarPanel }) {
  switch (panel) {
    case 'notes':  return <NoteList />;
    case 'search': return <SearchPanel />;
    case 'tags':   return <TagsPanel />;
    case 'trash':  return <TrashPanel />;
    case 'admin':  return <AdminPanel />;
  }
}

function EmptyState() {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 text-fg-disabled">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
      </svg>
      <span className="text-[13px]">Откройте заметку или выберите раздел</span>
    </div>
  );
}
