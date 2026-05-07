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
      if (isAxiosError(err) && err.response?.status === 400) {
        setPwdError('Неверный текущий пароль.');
      } else {
        setPwdError(s.common.error);
      }
    },
  });

  // ── Delete account ────────────────────────────────────────────────────────
  const [delPwd, setDelPwd] = useState('');
  const [delError, setDelError] = useState('');
  const deleteMut = useMutation({
    mutationFn: () => profileApi.deleteAccount({ password: delPwd }),
    onSuccess: () => { logout(); window.location.href = '/auth/login'; },
    onError: (err) => {
      if (isAxiosError(err) && err.response?.status === 400) {
        setDelError('Неверный пароль.');
      } else {
        setDelError(s.common.error);
      }
    },
  });

  // ── Logout ────────────────────────────────────────────────────────────────
  const logoutMut = useMutation({
    mutationFn: () => authApi.logout(),
    onSettled: () => { logout(); window.location.href = '/auth/login'; },
  });

  function close() { setProfileOpen(false); }

  return (
    <div className="fixed inset-0 bg-bg-overlay flex items-center justify-center z-50">
      <div className="bg-bg-card border border-border rounded-lg w-[420px] max-h-[90vh] overflow-y-auto relative flex flex-col">
        {/* Close */}
        <button
          className="absolute top-4 right-4 w-6 h-6 flex items-center justify-center text-fg-muted hover:text-fg rounded hover:bg-bg-hover text-lg leading-none"
          onClick={close}
        >
          ×
        </button>

        <div className="p-6 flex flex-col gap-5">
          <h2 className="text-[16px] font-semibold">{s.profile.profile}</h2>

          {/* ── Main section ── */}
          {section === 'main' && (
            <>
              {/* User info */}
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-[#4a4a8a] flex items-center justify-center text-white font-semibold text-[16px]">
                  {user?.nickname?.[0]?.toUpperCase()}
                </div>
                <div>
                  <div className="text-[14px] font-medium">{user?.nickname}</div>
                  <div className="text-[12px] text-fg-muted">{user?.email}</div>
                  <div className="text-[11px] text-fg-disabled mt-0.5">
                    {user?.role === 'admin' ? '👑 Admin' : ''}
                    {!user?.is_email_confirmed && ' · Email не подтверждён'}
                  </div>
                </div>
              </div>

              <hr className="border-border" />

              {/* Actions */}
              <div className="flex flex-col gap-2">
                <ProfileAction label={s.profile.editNickname} onClick={() => setSection('nickname')} />
                <ProfileAction label={s.profile.changePassword} onClick={() => setSection('password')} />
              </div>

              <hr className="border-border" />

              {/* Language */}
              <div className="flex items-center justify-between">
                <span className="text-[13px] text-fg-muted">{s.profile.language}</span>
                <div className="flex gap-1">
                  {(['ru', 'en'] as const).map((lang) => (
                    <button
                      key={lang}
                      className={`px-2.5 py-1 rounded text-[12px] font-medium
                        ${getLocale() === lang ? 'bg-bg-selected text-fg' : 'text-fg-muted hover:text-fg hover:bg-bg-hover'}`}
                      onClick={() => { setLocale(lang); close(); }}
                    >
                      {lang.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              <hr className="border-border" />

              {/* Bottom actions */}
              <div className="flex flex-col gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full"
                  onClick={() => logoutMut.mutate()}
                  loading={logoutMut.isPending}
                >
                  {s.auth.logout}
                </Button>
                <button
                  className="text-[12px] text-danger hover:underline text-center"
                  onClick={() => setSection('delete')}
                >
                  {s.profile.deleteAccount}
                </button>
              </div>
            </>
          )}

          {/* ── Nickname section ── */}
          {section === 'nickname' && (
            <>
              <BackButton onClick={() => setSection('main')} />
              <h3 className="text-[14px] font-medium">{s.profile.editNickname}</h3>
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
            </>
          )}

          {/* ── Password section ── */}
          {section === 'password' && (
            <>
              <BackButton onClick={() => setSection('main')} />
              <h3 className="text-[14px] font-medium">{s.profile.changePassword}</h3>
              {pwdSuccess ? (
                <p className="text-[13px] text-success">{s.auth.passwordChanged}</p>
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
                    <Button variant="ghost" size="sm" onClick={() => setSection('main')}>
                      {s.profile.cancel}
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => { setPwdError(''); pwdMut.mutate(); }}
                      loading={pwdMut.isPending}
                      disabled={!curPwd || newPwd.length < 8}
                    >
                      {s.profile.save}
                    </Button>
                  </div>
                </>
              )}
            </>
          )}

          {/* ── Delete section ── */}
          {section === 'delete' && (
            <>
              <BackButton onClick={() => setSection('main')} />
              <h3 className="text-[14px] font-medium text-danger">{s.profile.deleteAccount}</h3>
              <p className="text-[13px] text-fg-muted">{s.profile.deleteAccountConfirm}</p>
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
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ProfileAction({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      className="flex items-center justify-between w-full px-3 py-2 rounded-md hover:bg-bg-hover text-[13px] text-fg-muted hover:text-fg"
      onClick={onClick}
    >
      {label}
      <span className="text-fg-disabled">›</span>
    </button>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      className="flex items-center gap-1 text-[12px] text-fg-muted hover:text-fg -mt-2"
      onClick={onClick}
    >
      ← назад
    </button>
  );
}
