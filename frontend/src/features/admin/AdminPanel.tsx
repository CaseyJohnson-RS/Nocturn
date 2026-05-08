import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/api/admin';
import { useAuthStore } from '@/stores/auth';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { t } from '@/i18n';
import type { UserListItem, UserListResponse } from '@/types/api';

export default function AdminPanel() {
  const s = t();
  const qc = useQueryClient();
  const currentUser = useAuthStore((st) => st.user);

  const [search, setSearch] = useState('');
  const [submitted, setSubmitted] = useState('');

  const [blockTarget, setBlockTarget] = useState<UserListItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<UserListItem | null>(null);
  const [pendingRole, setPendingRole] = useState<{ user: UserListItem; newRole: 'user' | 'admin' } | null>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-users', submitted],
    queryFn: () => adminApi.listUsers({ limit: 200, search: submitted || undefined }),
  });

  function patchUser(updated: UserListItem) {
    qc.setQueryData<UserListResponse>(['admin-users', submitted], (old) =>
      old ? { ...old, items: old.items.map((u) => (u.id === updated.id ? updated : u)) } : old,
    );
  }

  function removeUser(id: string) {
    qc.setQueryData<UserListResponse>(['admin-users', submitted], (old) =>
      old ? { ...old, items: old.items.filter((u) => u.id !== id), total: old.total - 1 } : old,
    );
  }

  const activeMut = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      adminApi.setActive(id, { is_active: active }),
    onSuccess: (updated) => { patchUser(updated); setBlockTarget(null); },
  });

  const roleMut = useMutation({
    mutationFn: ({ id, role }: { id: string; role: 'user' | 'admin' }) =>
      adminApi.setRole(id, { role }),
    onSuccess: (updated) => { patchUser(updated); setPendingRole(null); },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => adminApi.deleteUser(id),
    onSuccess: (_, id) => { removeUser(id); setDeleteTarget(null); },
  });

  const users = data?.items ?? [];

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div
        className="flex-shrink-0 flex items-center justify-between border-b border-border"
        style={{ height: '40px', padding: '0 16px' }}
      >
        <span className="text-[11px] font-semibold uppercase tracking-widest text-fg-disabled select-none">
          {s.admin.users}
        </span>
        <div className="flex items-center gap-2">
          {data && (
            <span
              className="text-[11px] leading-none rounded-full font-medium"
              style={{
                padding: '3px 7px',
                background: 'rgba(0,122,204,0.12)',
                color: 'var(--color-fg-link)',
                border: '1px solid rgba(0,122,204,0.25)',
              }}
            >
              {data.total}
            </span>
          )}
          <button
            className="flex items-center justify-center rounded hover:bg-bg-hover transition-colors"
            style={{ width: '26px', height: '26px', color: 'var(--color-fg-muted)' }}
            onClick={() => void refetch()}
            title="Refresh"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 .49-4" />
            </svg>
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="flex-shrink-0 border-b border-border" style={{ padding: '8px 12px' }}>
        <form onSubmit={(e) => { e.preventDefault(); setSubmitted(search); }} className="relative">
          <svg
            style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--color-fg-disabled)', pointerEvents: 'none' }}
            width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          >
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            className="w-full bg-bg-input border border-border rounded text-[13px] text-fg outline-none placeholder:text-fg-muted focus:border-border-focus transition-colors"
            style={{ padding: '6px 10px 6px 30px' }}
            placeholder={s.admin.searchUsers}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </form>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <SkeletonRows />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '620px' }}>
            <thead>
              <tr>
                <Th>Email</Th>
                <Th>{s.auth.nickname}</Th>
                <Th>{s.admin.role}</Th>
                <Th>{s.admin.status}</Th>
                <Th>{s.admin.registeredAt}</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="text-fg-muted text-[13px]"
                    style={{ textAlign: 'center', padding: '48px 16px' }}
                  >
                    {s.notes.noResults}
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    isSelf={user.id === currentUser?.id}
                    pendingRole={pendingRole?.user.id === user.id ? pendingRole.newRole : null}
                    onBlock={() => setBlockTarget(user)}
                    onDelete={() => setDeleteTarget(user)}
                    onChangeRole={(newRole) => setPendingRole({ user, newRole })}
                    loading={
                      (activeMut.isPending && activeMut.variables?.id === user.id) ||
                      (roleMut.isPending && roleMut.variables?.id === user.id) ||
                      (deleteMut.isPending && deleteMut.variables === user.id)
                    }
                  />
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Block / Unblock confirm */}
      {blockTarget && (
        <ConfirmDialog
          title={blockTarget.is_active ? s.admin.block : s.admin.unblock}
          message={
            blockTarget.is_active
              ? s.admin.blockConfirm.replace('{nickname}', blockTarget.nickname)
              : s.admin.unblockConfirm.replace('{nickname}', blockTarget.nickname)
          }
          confirmLabel={blockTarget.is_active ? s.admin.block : s.admin.unblock}
          danger={blockTarget.is_active}
          loading={activeMut.isPending}
          onConfirm={() => activeMut.mutate({ id: blockTarget.id, active: !blockTarget.is_active })}
          onCancel={() => setBlockTarget(null)}
        />
      )}

      {/* Delete user confirm */}
      {deleteTarget && (
        <ConfirmDialog
          title={s.admin.deleteUser}
          message={s.admin.deleteUserConfirm.replace('{nickname}', deleteTarget.nickname)}
          confirmLabel={s.admin.deleteUser}
          danger
          loading={deleteMut.isPending}
          onConfirm={() => deleteMut.mutate(deleteTarget.id)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      {/* Role change confirm */}
      {pendingRole && (
        <ConfirmDialog
          title={s.admin.changeRole}
          message={s.admin.changeRoleConfirm
            .replace('{role}', pendingRole.newRole)
            .replace('{nickname}', pendingRole.user.nickname)}
          loading={roleMut.isPending}
          onConfirm={() => roleMut.mutate({ id: pendingRole.user.id, role: pendingRole.newRole })}
          onCancel={() => setPendingRole(null)}
        />
      )}
    </div>
  );
}

// ── Table helpers ──────────────────────────────────────────────────────────────

function Th({ children }: { children?: React.ReactNode }) {
  return (
    <th
      style={{
        padding: '8px 12px',
        textAlign: 'left',
        fontSize: '11px',
        fontWeight: 600,
        color: 'var(--color-fg-muted)',
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-bg-tab)',
        position: 'sticky',
        top: 0,
        whiteSpace: 'nowrap',
        zIndex: 1,
      }}
    >
      {children}
    </th>
  );
}

// ── UserRow ────────────────────────────────────────────────────────────────────

interface UserRowProps {
  user: UserListItem;
  isSelf: boolean;
  pendingRole: 'user' | 'admin' | null;
  onBlock: () => void;
  onDelete: () => void;
  onChangeRole: (newRole: 'user' | 'admin') => void;
  loading: boolean;
}

function UserRow({ user, isSelf, pendingRole, onBlock, onDelete, onChangeRole, loading }: UserRowProps) {
  const s = t();
  return (
    <tr
      className="group border-b border-border/50 hover:bg-bg-hover"
      style={{ opacity: loading ? 0.6 : 1, transition: 'opacity 0.15s' }}
    >
      {/* Email */}
      <td style={{ padding: '10px 12px', fontSize: '13px', color: isSelf ? 'var(--color-fg-muted)' : 'var(--color-fg)' }}>
        {user.email}
      </td>

      {/* Nickname */}
      <td style={{ padding: '10px 12px' }}>
        <span className="text-[12px]" style={{ color: 'var(--color-fg-muted)' }}>
          {user.nickname}
          {isSelf && (
            <span className="text-[11px] ml-1" style={{ color: 'var(--color-fg-disabled)' }}>
              ({s.admin.you})
            </span>
          )}
        </span>
      </td>

      {/* Role select */}
      <td style={{ padding: '10px 12px' }}>
        <select
          value={pendingRole ?? user.role}
          disabled={isSelf || loading}
          onChange={(e) => onChangeRole(e.target.value as 'user' | 'admin')}
          className="bg-bg-input border border-border rounded text-[12px] text-fg outline-none transition-colors focus:border-border-focus disabled:opacity-40 disabled:cursor-not-allowed"
          style={{
            padding: '3px 6px',
            borderColor: pendingRole ? 'var(--color-warning)' : undefined,
          }}
        >
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
      </td>

      {/* Status badge */}
      <td style={{ padding: '10px 12px' }}>
        <StatusBadge user={user} />
      </td>

      {/* Registered */}
      <td
        className="text-[11px] whitespace-nowrap"
        style={{ padding: '10px 12px', color: 'var(--color-fg-muted)' }}
      >
        {new Date(user.created_at).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })}
      </td>

      {/* Actions */}
      <td style={{ padding: '10px 12px' }}>
        <div className="flex items-center gap-1 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            disabled={isSelf || loading}
            onClick={onBlock}
            className={`text-[11px] px-2 py-1 rounded font-medium transition-colors disabled:opacity-30 disabled:cursor-not-allowed
              ${user.is_active ? 'text-danger hover:bg-danger/10' : 'text-success hover:bg-success/10'}`}
          >
            {user.is_active ? s.admin.block : s.admin.unblock}
          </button>
          <button
            disabled={isSelf || loading}
            onClick={onDelete}
            className="flex items-center justify-center rounded transition-colors text-fg-disabled hover:text-danger hover:bg-danger/10 disabled:opacity-30 disabled:cursor-not-allowed"
            style={{ width: '26px', height: '26px' }}
            title={s.admin.deleteUser}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
            </svg>
          </button>
        </div>
      </td>
    </tr>
  );
}

// ── StatusBadge ────────────────────────────────────────────────────────────────

function StatusBadge({ user }: { user: UserListItem }) {
  const s = t();

  let bg: string;
  let color: string;
  let label: string;

  if (!user.is_email_confirmed) {
    bg = 'rgba(204,167,0,0.15)';
    color = 'var(--color-warning)';
    label = s.admin.unconfirmed;
  } else if (!user.is_active) {
    bg = 'rgba(244,71,71,0.15)';
    color = 'var(--color-danger)';
    label = s.admin.inactive;
  } else {
    bg = 'rgba(78,201,176,0.15)';
    color = 'var(--color-success)';
    label = s.admin.active;
  }

  return (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', gap: '5px',
        background: bg, color,
        padding: '2px 8px', borderRadius: '10px',
        fontSize: '11px', fontWeight: 500, whiteSpace: 'nowrap',
      }}
    >
      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'currentColor', flexShrink: 0 }} />
      {label}
    </span>
  );
}

// ── Skeleton ───────────────────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <div>
      {[1, 0.8, 0.6, 0.4].map((opacity, i) => (
        <div
          key={i}
          className="flex items-center gap-4 border-b border-border/50"
          style={{ padding: '12px 12px', opacity }}
        >
          <span className="skel" style={{ width: '160px', height: '13px' }} />
          <span className="skel" style={{ width: '80px', height: '13px' }} />
          <span className="skel" style={{ width: '50px', height: '13px' }} />
          <span className="skel" style={{ width: '90px', height: '18px', borderRadius: '10px' }} />
          <span className="skel" style={{ width: '90px', height: '13px' }} />
        </div>
      ))}
    </div>
  );
}
