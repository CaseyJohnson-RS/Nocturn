import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/api/admin';
import { t } from '@/i18n';
import type { UserListItem } from '@/types/api';

export default function AdminPanel() {
  const s = t();
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [submitted, setSubmitted] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', submitted],
    queryFn: () => adminApi.listUsers({ limit: 100, search: submitted || undefined }),
  });

  const activeMut = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      adminApi.setActive(id, { is_active: active }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  const roleMut = useMutation({
    mutationFn: ({ id, role }: { id: string; role: 'user' | 'admin' }) =>
      adminApi.setRole(id, { role }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  const users: UserListItem[] = data?.items ?? [];

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div
        className="flex-shrink-0 flex items-center px-3 border-b border-border"
        style={{ height: 'var(--tabbar-h)' }}
      >
        <span className="text-[12px] font-medium text-fg-muted uppercase tracking-wide">
          {s.admin.users}
        </span>
      </div>

      {/* Search */}
      <div className="flex-shrink-0 p-3 border-b border-border">
        <form
          className="flex gap-2"
          onSubmit={(e) => { e.preventDefault(); setSubmitted(search); }}
        >
          <input
            className="flex-1 bg-bg-input border border-border rounded px-3 py-1.5 text-[13px] text-fg outline-none placeholder:text-fg-muted focus:border-border-focus"
            placeholder={s.admin.searchUsers}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </form>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="flex items-center justify-center h-24 text-fg-muted text-[12px]">
            {s.common.loading}
          </div>
        )}

        {/* Column headers */}
        {!isLoading && users.length > 0 && (
          <div className="flex items-center gap-3 px-3 py-1.5 border-b border-border bg-bg-tab text-[11px] text-fg-muted uppercase tracking-wide">
            <span className="flex-1">{s.auth.email}</span>
            <span className="w-24">{s.admin.role}</span>
            <span className="w-24">{s.admin.status}</span>
            <span className="w-28">{s.admin.registeredAt}</span>
            <span className="w-32"></span>
          </div>
        )}

        {users.map((user) => (
          <UserRow
            key={user.id}
            user={user}
            onSetActive={(active) => activeMut.mutate({ id: user.id, active })}
            onSetRole={(role) => roleMut.mutate({ id: user.id, role })}
            loading={activeMut.isPending || roleMut.isPending}
          />
        ))}

        {!isLoading && users.length === 0 && (
          <div className="flex items-center justify-center h-24 text-fg-muted text-[12px]">
            {s.notes.noResults}
          </div>
        )}
      </div>
    </div>
  );
}

interface UserRowProps {
  user: UserListItem;
  onSetActive: (v: boolean) => void;
  onSetRole: (v: 'user' | 'admin') => void;
  loading: boolean;
}

function UserRow({ user, onSetActive, onSetRole, loading }: UserRowProps) {
  const s = t();
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 border-b border-border/50 hover:bg-bg-hover text-[12px]">
      {/* Email + nickname */}
      <div className="flex-1 min-w-0">
        <div className="truncate text-fg">{user.email}</div>
        <div className="text-fg-muted text-[11px]">{user.nickname}</div>
      </div>

      {/* Role */}
      <div className="w-24">
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium
          ${user.role === 'admin' ? 'bg-warning/20 text-warning' : 'bg-bg-input text-fg-muted'}`}>
          {user.role}
        </span>
      </div>

      {/* Status */}
      <div className="w-24">
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium
          ${user.is_active ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'}`}>
          {user.is_active ? s.admin.active : s.admin.inactive}
        </span>
        {!user.is_email_confirmed && (
          <span className="ml-1 text-[10px] text-fg-disabled">{s.admin.unconfirmed}</span>
        )}
      </div>

      {/* Registered */}
      <div className="w-28 text-fg-muted text-[11px]">
        {new Date(user.created_at).toLocaleDateString()}
      </div>

      {/* Actions */}
      <div className="w-32 flex gap-1.5 justify-end">
        <button
          disabled={loading}
          onClick={() => onSetActive(!user.is_active)}
          className={`text-[11px] px-2 py-0.5 rounded font-medium
            ${user.is_active
              ? 'text-danger hover:bg-danger/10'
              : 'text-success hover:bg-success/10'}`}
        >
          {user.is_active ? s.admin.block : s.admin.unblock}
        </button>
        <button
          disabled={loading}
          onClick={() => onSetRole(user.role === 'admin' ? 'user' : 'admin')}
          className="text-[11px] px-2 py-0.5 rounded text-fg-muted hover:text-fg hover:bg-bg-input"
        >
          {user.role === 'admin' ? s.admin.makeUser : s.admin.makeAdmin}
        </button>
      </div>
    </div>
  );
}
