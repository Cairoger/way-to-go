'use client';

import { useEffect, useState } from 'react';
import { forgetOfflineTrip, offlineSavedAt, saveOfflineTrip } from '../lib/offlineTrips';
import './offlineTrip.css';

export default function OfflineTrip({ userId, tripId }: { userId: string; tripId: string }) {
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const sync = () => setSavedAt(offlineSavedAt(userId, tripId));
    sync();
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, [userId, tripId]);
  async function save() {
    setBusy(true);
    setError('');
    try {
      setSavedAt(await saveOfflineTrip(userId, tripId));
    } catch (reason) {
      setError(
        reason instanceof Error && reason.name === 'Error'
          ? reason.message
          : '無法儲存，請確認裝置儲存空間與瀏覽器設定。',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="offline-trip">
      <summary>離線閱讀</summary>
      <p>
        將旅程日期、目的地、活動時間與景點地址儲存在此裝置。斷網後可重新開啟旅程唯讀查看，登出時會清除。
      </p>
      <div className="offline-trip-actions">
        <button className="btn btn-secondary" disabled={busy} onClick={save}>
          {busy ? '儲存中…' : savedAt ? '更新離線旅程' : '儲存離線旅程'}
        </button>
        {savedAt && (
          <button
            className="text-btn"
            disabled={busy}
            onClick={() => {
              forgetOfflineTrip(tripId);
              setSavedAt(null);
              setError('');
            }}
          >
            清除此旅程的離線資料
          </button>
        )}
      </div>
      {savedAt && <p role="status">已儲存於 {new Date(savedAt).toLocaleString('zh-TW')}</p>}
      {error && <p role="alert">{error}</p>}
    </details>
  );
}
