'use client';
import { useEffect, useState, type FormEvent } from 'react';
import { Compass, Link2, LogIn } from 'lucide-react';
import { Button } from './ui/button';
import { Modal } from './ui/dialog';
import { api } from '../lib/api';
import { type Trip, type User, errorText } from '../lib/trips';
export default function AccessDialog({
  mode,
  user,
  invite,
  onClose,
  onJoined,
  onJoin,
  onSignedIn,
  createAfterLogin,
}: {
  mode: 'login' | 'join';
  user: User | null;
  invite: string;
  onClose: () => void;
  onJoined: (t: Trip) => void;
  onJoin: () => void;
  onSignedIn: (account: User) => void;
  createAfterLogin: boolean;
}) {
  const [pending, setPending] = useState<'google' | 'local' | 'join' | null>(null);
  const [error, setError] = useState('');
  const [localEnabled, setLocalEnabled] = useState(false);
  const busy = pending !== null;
  useEffect(() => {
    if (mode !== 'login') return;
    let active = true;
    api<{ enabled: boolean }>('/auth/local-test')
      .then(({ enabled }) => {
        if (active) setLocalEnabled(enabled === true);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [mode]);
  async function signIn() {
    setPending('google');
    setError('');
    try {
      const { url } = await api<{ url: string }>('/auth/google', 'POST', {
        return_to: createAfterLogin ? '/?action=create' : location.pathname + location.search,
      });
      window.location.assign(url);
    } catch (e) {
      setError(errorText(e));
      setPending(null);
    }
  }
  async function signInLocally(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    setPending('local');
    setError('');
    try {
      const account = await api<User>('/auth/local-test', 'POST', {
        username: fields.get('username'),
        password: fields.get('password'),
      });
      onSignedIn(account);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setPending(null);
    }
  }
  async function join(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    let code = String(f.get('code') ?? '').trim();
    try {
      code = new URL(code).searchParams.get('invite') || code;
    } catch {}
    setPending('join');
    setError('');
    try {
      const t = await api<Trip>(user ? '/invitations/accept' : '/auth/guest', 'POST', {
        code,
        ...(user ? {} : { nickname: String(f.get('nickname')).trim() }),
      });
      onJoined(t);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setPending(null);
    }
  }
  return (
    <Modal title={mode === 'join' ? '加入旅程' : '登入 WayToGo'} onClose={onClose}>
      {mode === 'login' ? (
        <div className="stack">
          <div className="access-note">
            <Compass size={28} />
            <p>登入後即可建立旅程，並邀請旅伴一起規劃。</p>
          </div>
          <Button onClick={signIn} disabled={busy}>
            <LogIn size={17} />
            {pending === 'google' ? '連線中…' : '使用 Google 登入'}
          </Button>
          <Button variant="outline" onClick={onJoin} disabled={busy}>
            <Link2 size={17} />
            我有邀請碼
          </Button>
          {localEnabled && (
            <form
              className="local-login stack"
              onSubmit={signInLocally}
              aria-label="本機測試帳號登入"
            >
              <h3>本機測試帳號</h3>
              {user?.account_type === 'guest' && (
                <p className="muted">
                  切換帳號會登出目前的訪客「{user.nickname}」，之後可能無法取回這個訪客身分。
                </p>
              )}
              <label className="field">
                測試帳號
                <input
                  name="username"
                  required
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                />
              </label>
              <label className="field">
                密碼
                <input name="password" type="password" required autoComplete="current-password" />
              </label>
              <Button type="submit" disabled={busy}>
                {pending === 'local' ? '登入中…' : '使用測試帳號登入'}
              </Button>
            </form>
          )}
        </div>
      ) : (
        <form onSubmit={join} className="stack">
          <p className="muted">輸入旅伴分享的邀請碼或邀請連結。</p>
          <label className="field">
            邀請碼或連結
            <input
              name="code"
              autoFocus={!invite}
              required
              defaultValue={invite}
              autoComplete="off"
            />
          </label>
          {!user && (
            <>
              <label className="field">
                你的暱稱
                <input name="nickname" required maxLength={50} placeholder="旅伴將看到這個名字" />
              </label>
              <small className="muted">
                訪客身分保存在此瀏覽器。清除瀏覽器資料或登出後，可能無法取回原身分。
              </small>
            </>
          )}
          <Button type="submit" disabled={busy}>
            {busy ? '加入中…' : '加入旅程'}
          </Button>
        </form>
      )}
      {error && (
        <div className="error-inline" role="alert">
          {error}
        </div>
      )}
    </Modal>
  );
}
