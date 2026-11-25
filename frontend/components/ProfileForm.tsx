'use client';
import { useState, type FormEvent } from 'react';
import { api, ApiError } from '../lib/api';
import { errorText, type User } from '../lib/trips';
import { Button } from './ui/button';

export default function ProfileForm({ user, onSaved }: { user: User; onSaved: (u: User) => void }) {
  const [base, setBase] = useState(user),
    [name, setName] = useState(user.nickname),
    [conflict, setConflict] = useState(false),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || conflict || !name.trim()) return;
    setBusy(true);
    setMessage('');
    try {
      const updated = await api<User>('/auth/me', 'PATCH', {
        nickname: name.trim(),
        version: base.version,
      });
      setBase(updated);
      setName(updated.nickname);
      onSaved(updated);
      setMessage('暱稱已儲存。');
    } catch (error) {
      setConflict(error instanceof ApiError && error.code === 'VERSION_CONFLICT');
      setMessage(errorText(error));
    } finally {
      setBusy(false);
    }
  }
  async function reloadProfile() {
    setBusy(true);
    try {
      const latest = await api<User>('/auth/me');
      setBase(latest);
      onSaved(latest);
      setConflict(false);
      setMessage(`目前儲存的暱稱是「${latest.nickname}」。已保留你的輸入。`);
    } catch (error) {
      setMessage(errorText(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="stack">
      <label className="field">
        顯示暱稱
        <input
          name="nickname"
          required
          maxLength={80}
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (!conflict) setMessage('');
          }}
        />
      </label>
      <Button
        variant="outline"
        type="submit"
        disabled={busy || conflict || !name.trim() || name.trim() === base.nickname}
      >
        儲存暱稱
      </Button>
      {message && <p role="status">{message}</p>}
      {conflict && (
        <Button type="button" variant="outline" disabled={busy} onClick={reloadProfile}>
          重新讀取最新暱稱
        </Button>
      )}
    </form>
  );
}
