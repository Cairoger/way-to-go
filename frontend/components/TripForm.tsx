'use client';
import { useState, type FormEvent } from 'react';
import { Check, Compass } from 'lucide-react';
import { api } from '../lib/api';
import { covers, errorText, statusLabels, type Trip, type Status } from '../lib/trips';
import { Modal } from './ui/dialog';
import { Button } from './ui/button';

export default function TripForm({
  trip: initialTrip,
  onClose,
  onSaved,
}: {
  trip?: Trip;
  onClose: () => void;
  onSaved: (t: Trip) => void;
}) {
  // Keep the version that belongs to the draft, even if a WebSocket refresh arrives.
  const [trip] = useState(initialTrip);
  const [cover, setCover] = useState(trip?.cover || 'valley');
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const value = (k: string) => String(f.get(k) ?? '').trim();
    if (!value('title')) {
      setError('請輸入旅程名稱。');
      return;
    }
    if (value('end_date') && (!value('start_date') || value('end_date') < value('start_date'))) {
      setError('請確認開始和結束日期。');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const data = {
        title: value('title'),
        destinations: value('destinations')
          .split(/[,，、]/)
          .map((s) => s.trim())
          .filter(Boolean),
        description: value('description'),
        start_date: value('start_date') || null,
        end_date: value('end_date') || null,
        currency: value('currency').toUpperCase(),
        status: value('status'),
        cover,
        ...(trip ? { version: trip.version } : {}),
      };
      onSaved(
        await api<Trip>(trip ? '/trips/' + trip.id : '/trips', trip ? 'PATCH' : 'POST', data),
      );
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={trip ? '旅程設定' : '建立旅程'} onClose={onClose}>
      <form onSubmit={submit} className="stack">
        <label className="field">
          旅程名稱
          <input
            name="title"
            required
            autoFocus
            maxLength={120}
            defaultValue={trip?.title}
            placeholder="例如：京都秋日散策"
          />
        </label>
        <label className="field">
          目的地
          <input
            name="destinations"
            defaultValue={trip?.destinations.join('、')}
            placeholder="輸入國家或城市，以頓號分隔"
          />
        </label>
        <div className="form-row">
          <label className="field">
            開始日期
            <input type="date" name="start_date" defaultValue={trip?.start_date ?? ''} />
          </label>
          <label className="field">
            結束日期
            <input type="date" name="end_date" defaultValue={trip?.end_date ?? ''} />
          </label>
        </div>
        <label className="field">
          旅程介紹
          <textarea rows={2} name="description" defaultValue={trip?.description} maxLength={4000} />
        </label>
        <div className="form-row">
          <label className="field">
            主要幣別
            <input
              name="currency"
              maxLength={3}
              pattern="[a-zA-Z]{3}"
              required
              defaultValue={trip?.currency || 'TWD'}
            />
          </label>
          <label className="field">
            狀態
            <select name="status" defaultValue={trip?.status || 'planning'}>
              {Object.entries(statusLabels).map(([k, v]) => (
                <option key={k} value={k as Status}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        </div>
        <fieldset>
          <legend>旅程封面</legend>
          <div className="cover-picker">
            {covers.map((c) => (
              <button
                type="button"
                key={c.id}
                className={cover === c.id ? 'selected' : ''}
                aria-label={c.name}
                aria-pressed={cover === c.id}
                onClick={() => setCover(c.id)}
              >
                <img src={c.path} alt={c.name} />
                {cover === c.id && <Check size={19} />}
              </button>
            ))}
          </div>
        </fieldset>
        {error && (
          <p className="error-inline" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions">
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button type="submit" disabled={busy}>
            <Compass size={16} />
            {busy ? '儲存中…' : trip ? '儲存設定' : '建立旅程'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
