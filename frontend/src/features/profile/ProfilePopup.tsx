import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { profileApi } from '@/api/profile';
import { authApi } from '@/api/auth';
import { useAuthStore } from '@/stores/auth';
import { useUIStore } from '@/stores/ui';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { isAxiosError } from '@/api/client';
import { t, getLocale, setLocale } from '@/i18n';

type Section = 'main' | 'nickname' | 'password' | 'delete';

export function ProfilePopup() {
  const s = t();
  const { user, setUser, logout } = useAuthStore();
  const { setProfileOpen } = useUIStore();
  const [section, setSection] = useState<Section>('main');

  // ── Nickname ──────────────────────────────────────────────────────────────
  const [nickname, setNickname] = useState(user?.nickname ?? '');
  const [nicknameError, setNicknameError] = useState('');
  const nicknameMut = useMutation({
    mutationFn: () => profileApi.updateNickname({ nickname }),
    onSuccess: (updated) => { setUser(updated); setSection('main'); },
    onError: () => setNicknameError(s.common.error),
  });

  // ── Password ──────────────────────────────────────────────────────────────
  const [curPwd, setCurPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [pwdError, setPwdError] = useState('');
  const [pwdSuccess, setPwdSuccess] = useState(false);
  const pwdMut = useMutation({
    mutationFn: () =>
      profileApi.changePassword({ current_password: curPwd, new_password: newPwd }),
    onSuccess: () => { setPwdSuccess(true); setCurPwd(''); setNewPwd(''); },
    onError: (err) => {
      setPwdError(
        isAxiosError(err) && err.response?.status === 400
          ? s.auth.wrongPassword
          : s.common.error,
      );
    },
  });

  // ── Delete account ────────────────────────────────────────────────────────
  const [delPwd, setDelPwd] = useState('');
  const [delError, setDelError] = useState('');
  const deleteMut = useMutation({
    mutationFn: () => profileApi.deleteAccount({ password: delPwd }),
    onSuccess: () => { logout(); window.location.href = '/auth/login'; },
    onError: (err) => {
      setDelError(
        isAxiosError(err) && err.response?.status === 400
          ? s.auth.wrongPassword
          : s.common.error,
      );
    },
  });

  // ── Logout ────────────────────────────────────────────────────────────────
  const logoutMut = useMutation({
    mutationFn: () => authApi.logout(),
    onSettled: () => { logout(); window.location.href = '/auth/login'; },
  });

  function close() { setProfileOpen(false); }

  const initial = user?.nickname?.[0]?.toUpperCase() ?? '?';

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: 'rgba(0,0,0,0.6)' }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}
    >
      <div
        className="bg-bg-card border border-border rounded-lg flex flex-col overflow-hidden"
        style={{ width: '360px', maxHeight: '90vh', boxShadow: '0 24px 48px rgba(0,0,0,0.45)' }}
      >
        {/* ── Main section ── */}
        {section === 'main' && (
          <>
            {/* User banner */}
            <div className="flex items-center gap-3" style={{ padding: '18px 16px 14px' }}>
              <div
                className="flex-shrink-0 flex items-center justify-center rounded-full text-white font-semibold select-none"
                style={{
                  width: '44px', height: '44px', fontSize: '18px',
                  background: 'linear-gradient(135deg, #007acc 0%, #0a5a9e 100%)',
                  boxShadow: '0 2px 8px rgba(0,122,204,0.3)',
                }}
              >
                {initial}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-[14px] font-semibold truncate" style={{ color: 'var(--color-fg)' }}>
                    {user?.nickname}
                  </span>
                  {user?.role === 'admin' && (
                    <span
                      className="text-[10px] font-semibold leading-none rounded"
                      style={{
                        padding: '2px 6px',
                        background: 'rgba(0,122,204,0.18)',
                        color: 'var(--color-fg-link)',
                        border: '1px solid rgba(0,122,204,0.3)',
                      }}
                    >
                      ADMIN
                    </span>
                  )}
                </div>
                <div className="text-[12px] truncate" style={{ color: 'var(--color-fg-muted)', marginTop: '2px' }}>
                  {user?.email}
                </div>
                {!user?.is_email_confirmed && (
                  <div
                    className="flex items-center gap-1 text-[11px] leading-none"
                    style={{ color: 'var(--color-warning)', marginTop: '5px' }}
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                      <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                    {s.profile.emailUnconfirmed}
                  </div>
                )}
              </div>

              <button
                className="flex-shrink-0 flex items-center justify-center rounded hover:bg-bg-hover transition-colors"
                style={{ width: '28px', height: '28px', color: 'var(--color-fg-muted)' }}
                onClick={close}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <div className="border-t border-border" />

            {/* Action rows */}
            <div style={{ padding: '6px 8px' }}>
              <ProfileAction
                icon={
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                }
                label={s.profile.editNickname}
                onClick={() => setSection('nickname')}
              />
              <ProfileAction
                icon={
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                }
                label={s.profile.changePassword}
                onClick={() => setSection('password')}
              />
            </div>

            <div className="border-t border-border" />

            {/* Language */}
            <div className="flex items-center justify-between" style={{ padding: '10px 16px' }}>
              <div className="flex items-center gap-2" style={{ color: 'var(--color-fg-muted)' }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="2" y1="12" x2="22" y2="12" />
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                </svg>
                <span className="text-[12px]">{s.profile.language}</span>
              </div>
              <div
                className="flex rounded overflow-hidden"
                style={{ border: '1px solid var(--color-border)' }}
              >
                {(['ru', 'en'] as const).map((lang) => (
                  <button
                    key={lang}
                    className={`text-[11px] font-medium transition-colors
                      ${getLocale() === lang
                        ? 'bg-bg-selected text-white'
                        : 'text-fg-muted hover:text-fg hover:bg-bg-hover'}`}
                    style={{ padding: '4px 11px' }}
                    onClick={() => { setLocale(lang); close(); }}
                  >
                    {lang.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div className="border-t border-border" />

            {/* Bottom actions */}
            <div style={{ padding: '10px 16px 16px' }} className="flex flex-col gap-1.5">
              <button
                className="flex items-center justify-center gap-2 w-full rounded text-[12px] font-medium transition-colors border border-border text-fg-muted hover:text-fg hover:bg-bg-hover disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ padding: '7px 0' }}
                onClick={() => logoutMut.mutate()}
                disabled={logoutMut.isPending}
              >
                {logoutMut.isPending ? (
                  <span className="inline-block w-3.5 h-3.5 border-2 border-fg-disabled border-t-fg rounded-full animate-spin" />
                ) : (
                  <>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                      <polyline points="16 17 21 12 16 7" />
                      <line x1="21" y1="12" x2="9" y2="12" />
                    </svg>
                    {s.auth.logout}
                  </>
                )}
              </button>
              <button
                className="text-[12px] text-center text-danger hover:opacity-70 transition-opacity"
                style={{ padding: '4px 0' }}
                onClick={() => setSection('delete')}
              >
                {s.profile.deleteAccount}
              </button>
            </div>
          </>
        )}

        {/* ── Nickname section ── */}
        {section === 'nickname' && (
          <SubSection title={s.profile.editNickname} backLabel={s.profile.back} onBack={() => setSection('main')}>
            <Input
              id="nickname"
              label={s.auth.nickname}
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              minLength={2}
              maxLength={32}
              error={nicknameError}
            />
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" size="sm" onClick={() => setSection('main')}>
                {s.profile.cancel}
              </Button>
              <Button size="sm" onClick={() => nicknameMut.mutate()} loading={nicknameMut.isPending}>
                {s.profile.save}
              </Button>
            </div>
          </SubSection>
        )}

        {/* ── Password section ── */}
        {section === 'password' && (
          <SubSection title={s.profile.changePassword} backLabel={s.profile.back} onBack={() => setSection('main')}>
            {pwdSuccess ? (
              <p className="text-[13px]" style={{ color: 'var(--color-success)' }}>
                {s.auth.passwordChanged}
              </p>
            ) : (
              <>
                <Input
                  id="cur-pwd"
                  label={s.auth.currentPassword}
                  type="password"
                  value={curPwd}
                  onChange={(e) => setCurPwd(e.target.value)}
                  error={pwdError}
                />
                <Input
                  id="new-pwd"
                  label={s.auth.newPassword}
                  type="password"
                  value={newPwd}
                  onChange={(e) => setNewPwd(e.target.value)}
                  minLength={8}
                  maxLength={128}
                />
                <div className="flex gap-2 justify-end">
                  <Button variant="ghost" size="sm" style={{ padding: '8px 20px' }} onClick={() => setSection('main')}>
                    {s.profile.cancel}
                  </Button>
                  <Button
                    size="sm"
                    style={{ padding: '8px 20px' }}
                    onClick={() => { setPwdError(''); pwdMut.mutate(); }}
                    loading={pwdMut.isPending}
                    disabled={!curPwd || newPwd.length < 8}
                  >
                    {s.profile.save}
                  </Button>
                </div>
              </>
            )}
          </SubSection>
        )}

        {/* ── Delete section ── */}
        {section === 'delete' && (
          <SubSection
            title={s.profile.deleteAccount}
            titleDanger
            backLabel={s.profile.back}
            onBack={() => setSection('main')}
          >
            <p className="text-[12px]" style={{ color: 'var(--color-fg-muted)', lineHeight: '1.55' }}>
              {s.profile.deleteAccountConfirm}
            </p>
            <Input
              id="del-pwd"
              label={s.auth.password}
              type="password"
              value={delPwd}
              onChange={(e) => setDelPwd(e.target.value)}
              error={delError}
            />
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" size="sm" onClick={() => setSection('main')}>
                {s.profile.cancel}
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => { setDelError(''); deleteMut.mutate(); }}
                loading={deleteMut.isPending}
                disabled={!delPwd}
              >
                {s.profile.deleteAccount}
              </Button>
            </div>
          </SubSection>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

interface ProfileActionProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}

function ProfileAction({ icon, label, onClick }: ProfileActionProps) {
  return (
    <button
      className="group flex items-center gap-2.5 w-full rounded text-[13px] transition-colors text-fg-muted hover:text-fg hover:bg-bg-hover"
      style={{ padding: '8px 10px' }}
      onClick={onClick}
    >
      <span className="flex-shrink-0 text-fg-disabled group-hover:text-fg-muted transition-colors">
        {icon}
      </span>
      <span className="flex-1 text-left">{label}</span>
      <svg
        width="12" height="12" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="2.5"
        className="flex-shrink-0 text-fg-disabled"
      >
        <polyline points="9 18 15 12 9 6" />
      </svg>
    </button>
  );
}

interface SubSectionProps {
  title: string;
  titleDanger?: boolean;
  backLabel: string;
  onBack: () => void;
  children: React.ReactNode;
}

function SubSection({ title, titleDanger, backLabel, onBack, children }: SubSectionProps) {
  return (
    <div style={{ padding: '16px 20px 20px' }} className="flex flex-col gap-4">
      <div className="flex items-center gap-2.5">
        <button
          className="flex-shrink-0 flex items-center justify-center rounded transition-colors border border-border text-fg-muted hover:bg-bg-hover hover:text-fg"
          style={{ width: '26px', height: '26px' }}
          onClick={onBack}
          title={backLabel}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <h3
          className="text-[14px] font-semibold"
          style={{ color: titleDanger ? 'var(--color-danger)' : 'var(--color-fg)' }}
        >
          {title}
        </h3>
      </div>
      {children}
    </div>
  );
}
