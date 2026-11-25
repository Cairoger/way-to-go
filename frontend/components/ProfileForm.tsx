'use client';
import { useState, type FormEvent } from 'react';
import { api } from '../lib/api';
import { errorText, type User } from '../lib/trips';
import { Button } from './ui/button';

export default function ProfileForm({ user, onSaved }: { user: User; onSaved: (u: User) => void }) {
  const [name, setName] = useState(user.nickname),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !name.trim()) return;
    setBusy(true);
    setMessage('');
    try {
      const updated = await api<User>('/auth/me', 'PATCH', { nickname: name.trim() });
      setName(updated.nickname);
      onSaved(updated);
      setMessage('暱稱已儲存。');
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
            setMessage('');
          }}
        />
      </label>
      <Button
        variant="outline"
        type="submit"
        disabled={busy || !name.trim() || name.trim() === user.nickname}
      >
        儲存暱稱
      </Button>
      {message && <p role="status">{message}</p>}
    </form>
  );
}
