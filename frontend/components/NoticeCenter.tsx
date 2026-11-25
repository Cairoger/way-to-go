'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Bell, Check, MessageCircle } from 'lucide-react';
import { api, ApiError } from '../lib/api';
import { errorText } from '../lib/trips';
import { Modal } from './ui/dialog';
import { Button } from './ui/button';
import './notice.css';

type Preferences = { mentions: boolean; push: boolean; version: number; public_key: string | null };
type Notice = {
  id: string;
  comment_id: string;
  trip_id: string;
  trip: string;
  actor: string;
  read: boolean;
  created_at: string;
};
type Inbox = { preferences: Preferences; items: Notice[]; device_registered: boolean };
function supported() {
  return (
    window.isSecureContext &&
    'PushManager' in window &&
    'serviceWorker' in navigator &&
    'Notification' in window
  );
}
function keyBytes(value: string) {
  return Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));
}
async function waitForPushService<T>(request: Promise<T>) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error('瀏覽器推播服務連線逾時，請稍後重試。')), 20000);
  });
  try {
    return await Promise.race([request, timeout]);
  } finally {
    clearTimeout(timer);
  }
}
export default function NoticeCenter({
  openTrip,
}: {
  openTrip: (id: string, comment: string) => void;
}) {
  const [open, setOpen] = useState(false),
    [data, setData] = useState<Inbox | null>(null),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    [device, setDevice] = useState(false);
  const serial = useRef(0);
  const targetedNotice = useRef<string | null>(null);
  const load = useCallback(async () => {
    const id = ++serial.current;
    try {
      const result = await api<Inbox>('/notifications');
      if (id === serial.current) {
        setData(result);
        setError('');
      }
    } catch (e) {
      if (id === serial.current) setError(errorText(e));
    }
  }, []);
  useEffect(() => {
    const url = new URL(location.href);
    if (url.searchParams.has('notifications')) {
      setOpen(true);
      targetedNotice.current = new URLSearchParams(url.hash.slice(1)).get('notice');
      url.searchParams.delete('notifications');
      url.hash = '';
      history.replaceState(null, '', url.pathname + url.search + url.hash);
    }
    void load();
    const reload = () => {
      if (document.visibilityState === 'visible') void load();
    };
    const timer = setInterval(reload, 60000);
    window.addEventListener('focus', reload);
    document.addEventListener('visibilitychange', reload);
    window.addEventListener('waytogo-notices', load);
    return () => {
      clearInterval(timer);
      window.removeEventListener('focus', reload);
      document.removeEventListener('visibilitychange', reload);
      window.removeEventListener('waytogo-notices', load);
    };
  }, [load]);
  useEffect(() => {
    if (!data || !targetedNotice.current) return;
    const item = data.items.find((entry) => entry.id === targetedNotice.current);
    targetedNotice.current = null;
    if (!item) return;
    const read = item.read
      ? Promise.resolve()
      : api('/notifications/' + item.id + '/read', 'POST', {});
    void read
      .then(() => {
        setOpen(false);
        openTrip(item.trip_id, item.comment_id);
        void load();
      })
      .catch((e) => setError(errorText(e)));
  }, [data, openTrip, load]);
  useEffect(() => {
    if (!open || !data?.preferences.public_key || !data.device_registered || !supported()) return;
    let active = true;
    navigator.serviceWorker
      .getRegistration()
      .then((r) => r?.pushManager.getSubscription())
      .then((s) => {
        if (active) setDevice(!!s);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [open, data?.preferences.public_key, data?.device_registered]);
  async function mutate(fn: () => Promise<void>) {
    setBusy(true);
    setError('');
    try {
      await fn();
      await load();
    } catch (e) {
      await load();
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  async function updatePref(mentions: boolean, push: boolean) {
    await api('/notifications/preferences', 'PUT', {
      mentions,
      push,
      version: data!.preferences.version,
    });
  }
  async function enablePush() {
    if (!data?.preferences.public_key || !supported()) return;
    if ((await Notification.requestPermission()) !== 'granted')
      throw new Error('請在瀏覽器設定中允許本站顯示通知。');
    await waitForPushService(navigator.serviceWorker.register('/sw.js'));
    const registration = await waitForPushService(navigator.serviceWorker.ready);
    const key = keyBytes(data.preferences.public_key);
    const subscribe = () =>
      waitForPushService(
        registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: key,
        }),
      );
    let sub = await waitForPushService(registration.pushManager.getSubscription());
    const current = sub?.options.applicationServerKey;
    if (sub && (!current || new Uint8Array(current).join() !== key.join())) {
      await waitForPushService(sub.unsubscribe());
      sub = null;
    }
    sub ??= await subscribe();
    try {
      await api('/notifications/device', 'PUT', { endpoint: sub.endpoint });
    } catch (error) {
      if (!(error instanceof ApiError) || error.code !== 'DEVICE_IN_USE') throw error;
      await waitForPushService(sub.unsubscribe());
      sub = await subscribe();
      await api('/notifications/device', 'PUT', { endpoint: sub.endpoint });
    }
    await updatePref(data.preferences.mentions, true);
    setDevice(true);
  }
  async function disablePush() {
    await updatePref(data!.preferences.mentions, false);
    await api('/notifications/device', 'DELETE');
    const reg = await navigator.serviceWorker.getRegistration();
    const sub = await reg?.pushManager.getSubscription();
    if (sub) await sub.unsubscribe();
    setDevice(false);
  }
  const unread = data?.items.filter((n) => !n.read).length ?? 0;
  const pushEnabled = data?.preferences.push && data.device_registered && device;
  return (
    <>
      <button
        className="notice-bell icon-button"
        aria-label={unread ? '通知中心，' + unread + ' 則未讀' : '通知中心'}
        onClick={() => {
          setOpen(true);
          void load();
        }}
      >
        <Bell size={19} />
        {unread > 0 && <i aria-hidden="true" />}
      </button>
      {open && (
        <Modal title="通知中心" onClose={() => setOpen(false)}>
          <div className="stack notice-list">
            {error && (
              <p role="alert" className="error-inline">
                {error} <button onClick={() => void load()}>重新整理</button>
              </p>
            )}
            {!data && !error && <p role="status">讀取通知中…</p>}
            {data && (
              <>
                <section aria-label="通知紀錄">
                  {!data.items.length && (
                    <p className="muted">旅伴在討論中提及你時，通知會出現在這裡。</p>
                  )}
                  {data.items.map((n) => (
                    <article key={n.id} className={n.read ? 'read' : ''}>
                      <button
                        className="notice-link"
                        disabled={busy}
                        onClick={() =>
                          void mutate(async () => {
                            if (!n.read) await api('/notifications/' + n.id + '/read', 'POST', {});
                            setOpen(false);
                            openTrip(n.trip_id, n.comment_id);
                          })
                        }
                      >
                        <MessageCircle size={17} />
                        <span>
                          <b>
                            {n.actor} 在「{n.trip}」提及你
                          </b>
                          <small>{new Date(n.created_at).toLocaleString('zh-TW')}</small>
                        </span>
                      </button>
                      {!n.read && (
                        <button
                          className="text-btn"
                          disabled={busy}
                          onClick={() =>
                            void mutate(async () => {
                              await api('/notifications/' + n.id + '/read', 'POST', {});
                            })
                          }
                        >
                          <Check size={15} />
                          標為已讀
                        </button>
                      )}
                    </article>
                  ))}
                </section>
                <fieldset className="notice-prefs">
                  <legend>通知偏好</legend>
                  <label>
                    <input
                      type="checkbox"
                      checked={data.preferences.mentions}
                      disabled={busy}
                      onChange={(e) =>
                        void mutate(() => updatePref(e.target.checked, data.preferences.push))
                      }
                    />{' '}
                    接收旅伴提及通知
                  </label>
                  {data.preferences.public_key && supported() ? (
                    <>
                      <Button
                        variant="outline"
                        disabled={busy}
                        onClick={() => void mutate(pushEnabled ? disablePush : enablePush)}
                      >
                        {pushEnabled ? '關閉推播' : '啟用這台裝置的推播'}
                      </Button>
                      {pushEnabled && <small>關閉後，此帳號的所有裝置都會暫停推播。</small>}
                    </>
                  ) : (
                    <small>
                      {data.preferences.public_key
                        ? '此瀏覽器目前無法接收推播。'
                        : '此站台尚未設定瀏覽器推播。'}
                    </small>
                  )}
                </fieldset>
              </>
            )}
          </div>
        </Modal>
      )}
    </>
  );
}
