import type { ReactNode } from 'react';
import { useAuthStore } from '@/stores/auth';
import { useUIStore, type SidebarPanel } from '@/stores/ui';

function Ic({ children }: { children: ReactNode }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ display: 'block' }}>
      {children}
    </svg>
  );
}

const ICONS: Record<string, ReactNode> = {
  notes: <Ic><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></Ic>,
  search: <Ic><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></Ic>,
  tags:   <Ic><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></Ic>,
  trash:  <Ic><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></Ic>,
  chat:   <Ic><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></Ic>,
  admin:  <Ic><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></Ic>,
};

const NAV_ITEMS: { id: SidebarPanel; label: string }[] = [
  { id: 'notes',  label: 'Заметки' },
  { id: 'search', label: 'Поиск'   },
  { id: 'tags',   label: 'Теги'    },
];

export function Sidebar() {
  const { openTab, activeTabKey, chatOpen, toggleChat, setProfileOpen } = useUIStore();
  const user = useAuthStore((s) => s.user);

  return (
    <aside
      className="flex flex-col items-center flex-shrink-0 border-r border-border"
      style={{ width: 'var(--sidebar-w)', background: 'var(--color-bg-sidebar)', padding: '8px 0' }}
    >
      {/* Logo */}
      <div className="w-8 h-8 flex items-center justify-center text-accent font-bold text-lg" style={{ marginBottom: '6px' }}>
        N
      </div>

      {/* Top nav — grows to push bottom section down */}
      <nav className="flex flex-col items-center flex-1" style={{ gap: '2px' }}>
        {NAV_ITEMS.map((item) => (
          <NavIcon
            key={item.id}
            icon={ICONS[item.id]}
            label={item.label}
            active={activeTabKey === `panel:${item.id}`}
            onClick={() => openTab({ type: 'panel', panel: item.id })}
          />
        ))}

        {/* Divider */}
        <div style={{ width: '24px', height: '1px', background: 'var(--color-border)', margin: '4px 0' }} />

        <NavIcon
          icon={ICONS.trash}
          label="Корзина"
          active={activeTabKey === 'panel:trash'}
          onClick={() => openTab({ type: 'panel', panel: 'trash' })}
        />
      </nav>

      {/* Bottom section */}
      <div className="flex flex-col items-center" style={{ gap: '2px' }}>
        {user?.role === 'admin' && (
          <NavIcon
            icon={ICONS.admin}
            label="Администратор"
            active={activeTabKey === 'panel:admin'}
            onClick={() => openTab({ type: 'panel', panel: 'admin' })}
          />
        )}

        <NavIcon
          icon={ICONS.chat}
          label="AI-чат"
          active={chatOpen}
          highlight={chatOpen}
          onClick={toggleChat}
        />

        {/* Avatar / profile */}
        <button
          className="w-10 h-10 flex items-center justify-center rounded-md hover:bg-bg-hover"
          onClick={() => setProfileOpen(true)}
          title={user?.nickname}
        >
          <span
            className="w-6 h-6 rounded-full text-white text-[11px] font-semibold flex items-center justify-center"
            style={{ background: '#4a4a8a' }}
          >
            {user?.nickname?.[0]?.toUpperCase() ?? '?'}
          </span>
        </button>
      </div>
    </aside>
  );
}

interface NavIconProps {
  icon: ReactNode;
  label: string;
  active?: boolean;
  highlight?: boolean;
  onClick?: () => void;
}

function NavIcon({ icon, label, active, highlight, onClick }: NavIconProps) {
  return (
    <button
      title={label}
      onClick={onClick}
      className={`relative w-10 h-10 flex items-center justify-center rounded-md transition-colors
        ${active || highlight ? 'text-accent' : 'text-fg-muted hover:bg-bg-hover hover:text-fg'}`}
    >
      {(active || highlight) && (
        <span className="absolute top-1/2 -translate-y-1/2 w-0.5 h-5 bg-accent rounded-r" style={{ left: '-8px' }} />
      )}
      {icon}
    </button>
  );
}
