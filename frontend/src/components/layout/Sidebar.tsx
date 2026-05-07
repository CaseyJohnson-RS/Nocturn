import { useAuthStore } from '@/stores/auth';
import { useUIStore, type SidebarPanel } from '@/stores/ui';

const NAV_ITEMS: { id: SidebarPanel; label: string; icon: string }[] = [
  { id: 'notes',  label: 'Заметки',  icon: '📝' },
  { id: 'search', label: 'Поиск',    icon: '🔍' },
  { id: 'tags',   label: 'Теги',     icon: '🏷'  },
  { id: 'trash',  label: 'Корзина',  icon: '🗑'  },
];

export function Sidebar() {
  const { openTab, activeTabKey, chatOpen, toggleChat, setProfileOpen } = useUIStore();
  const user = useAuthStore((s) => s.user);

  return (
    <aside
      className="flex flex-col items-center py-2 flex-shrink-0 border-r border-border"
      style={{ width: 'var(--sidebar-w)', background: 'var(--color-bg-sidebar)' }}
    >
      {/* Logo */}
      <div className="w-8 h-8 flex items-center justify-center text-accent font-bold text-lg mb-1.5">
        N
      </div>

      {/* Top nav */}
      <nav className="flex flex-col items-center gap-0.5 flex-1">
        {NAV_ITEMS.map((item) => (
          <NavIcon
            key={item.id}
            icon={item.icon}
            label={item.label}
            active={activeTabKey === `panel:${item.id}`}
            onClick={() => openTab({ type: 'panel', panel: item.id })}
          />
        ))}

        {user?.role === 'admin' && (
          <NavIcon
            icon="⚙"
            label="Администратор"
            active={activeTabKey === 'panel:admin'}
            onClick={() => openTab({ type: 'panel', panel: 'admin' })}
          />
        )}
      </nav>

      {/* Bottom */}
      <div className="flex flex-col items-center gap-0.5">
        {/* Chat toggle */}
        <NavIcon
          icon="💬"
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
          <span className="w-6 h-6 rounded-full bg-[#4a4a8a] text-white text-[11px] font-semibold flex items-center justify-center">
            {user?.nickname?.[0]?.toUpperCase() ?? '?'}
          </span>
        </button>
      </div>
    </aside>
  );
}

interface NavIconProps {
  icon: string;
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
      className={`relative w-10 h-10 flex items-center justify-center rounded-md text-base
        ${active || highlight ? 'text-accent' : 'text-fg-muted hover:bg-bg-hover hover:text-fg'}`}
    >
      {(active || highlight) && (
        <span
          className="absolute left-[-8px] top-1/2 -translate-y-1/2 w-0.5 h-5 bg-accent rounded-r"
        />
      )}
      {icon}
    </button>
  );
}
