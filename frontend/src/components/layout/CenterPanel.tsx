import { useUIStore, tabKey, type TabId, type SidebarPanel } from '@/stores/ui';
import { lazy, Suspense } from 'react';
import { useQuery } from '@tanstack/react-query';
import { notesApi } from '@/api/notes';
import { t } from '@/i18n';
import type { NoteResponse } from '@/types/api';

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

export function CenterPanel() {
  const { openTabs, activeTabKey, closeTab, setActiveTab } = useUIStore();

  const activeTab = openTabs.find((tab) => tabKey(tab) === activeTabKey) ?? null;

  return (
    <div className="flex-1 flex flex-col overflow-hidden min-w-0">
      {/* Tab bar */}
      {openTabs.length > 0 && (
        <div
          className="flex-shrink-0 flex overflow-x-auto border-b border-border"
          style={{ height: 'var(--tabbar-h)', background: 'var(--color-bg-tab)' }}
        >
          {openTabs.map((tab) => {
            const key = tabKey(tab);
            const isActive = key === activeTabKey;
            return (
              <div
                key={key}
                className={`flex-shrink-0 flex items-center gap-2 px-3 text-[12px] cursor-pointer border-r border-border
                  ${isActive ? 'bg-bg-base text-fg border-t border-t-accent' : 'text-fg-muted hover:bg-bg-hover hover:text-fg'}`}
                onClick={() => setActiveTab(tab)}
              >
                <span><TabLabel tab={tab} /></span>
                <button
                  className="text-fg-disabled hover:text-fg text-[14px] leading-none"
                  onClick={(e) => { e.stopPropagation(); closeTab(tab); }}
                >
                  ×
                </button>
              </div>
            );
          })}
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
