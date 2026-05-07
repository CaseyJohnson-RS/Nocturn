import { Sidebar } from './Sidebar';
import { CenterPanel } from './CenterPanel';
import { useUIStore } from '@/stores/ui';
import { ProfilePopup } from '@/features/profile/ProfilePopup';
import { lazy, Suspense } from 'react';

const ChatPanel = lazy(() => import('@/features/chat/ChatPanel'));

export default function AppShell() {
  const { chatOpen, profileOpen, offlineBanner, readonlyBanner } = useUIStore();

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Banners */}
      {offlineBanner && (
        <div className="flex-shrink-0 px-4 py-1.5 bg-[#0d2e4a] text-fg-link text-[12px] font-medium flex items-center justify-center gap-3 border-b border-border">
          ⚡ Нет подключения — изменения сохранены локально
          <button
            className="bg-[#1a1a1a] text-fg-link text-[11px] font-semibold px-2 py-0.5 rounded"
            onClick={() => useUIStore.getState().setOfflineBanner(false)}
          >
            Скрыть
          </button>
        </div>
      )}
      {readonlyBanner && (
        <div className="flex-shrink-0 px-4 py-1.5 bg-warning text-[#1a1a1a] text-[12px] font-medium flex items-center justify-center gap-3">
          ⚠ Режим чтения — email не подтверждён
          <button
            className="bg-[#1a1a1a] text-warning text-[11px] font-semibold px-2 py-0.5 rounded"
            onClick={() => useUIStore.getState().setReadonlyBanner(false)}
          >
            Скрыть
          </button>
        </div>
      )}

      {/* Main shell */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <CenterPanel />
        {chatOpen && (
          <Suspense fallback={null}>
            <ChatPanel />
          </Suspense>
        )}
      </div>

      {profileOpen && <ProfilePopup />}
    </div>
  );
}
