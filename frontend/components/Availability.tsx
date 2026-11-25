'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { CalendarCheck, Check, Pencil, Plus, Trash2 } from 'lucide-react';
import { api } from '../lib/api';
import { errorText, formatDates, type Member, type Trip } from '../lib/trips';
import './decisions.css';

const labels = { yes: '可以', maybe: '可能', no: '不行' } as const;
type Status = keyof typeof labels;
type Period = { start_date: string; end_date: string };
type Entry = Period & { id: string; user_id: string; status: Status; version: number };
type Suggestion = Period & { yes: number; maybe: number; no: number; unknown: number };
type Snapshot = { entries: Entry[]; recommendations: Suggestion[]; member_count: number };
type Props = {
  trip: Trip;
  userId: string;
  members: Member[];
  refresh: number;
  onChange: () => void;
  setError: (message: string) => void;
};

export default function Availability({
  trip,
  userId,
  members,
  refresh,
  onChange,
  setError,
}: Props) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [fetchError, setFetchError] = useState('');
  const [revision, setRevision] = useState(0);
  const [editing, setEditing] = useState<Entry | 'new' | null>(null);
  const [selected, setSelected] = useState<(Period & { version: number }) | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [showAll, setShowAll] = useState(false);
  const path = '/trips/' + trip.id + '/availability';
  const owner = userId === trip.owner_id;
  useEffect(() => {
    let active = true;
    api<Snapshot>(path)
      .then((data) => {
        if (active) {
          setSnapshot(data);
          setFetchError('');
        }
      })
      .catch((e) => {
        if (active) setFetchError(errorText(e));
      });
    return () => {
      active = false;
    };
  }, [path, refresh, revision]);

  async function write(url: string, method: string, body: unknown, message: string) {
    setBusy(true);
    setNotice('');
    try {
      await api(url, method, body);
      setNotice(message);
      onChange();
      return true;
    } catch (error) {
      setError(errorText(error));
      return false;
    } finally {
      setBusy(false);
      setRevision((n) => n + 1);
    }
  }
  async function saveEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const entry = editing && editing !== 'new' ? editing : null;
    const body = {
      start_date: data.get('start'),
      end_date: data.get('end') || data.get('start'),
      status: data.get('status'),
      ...(entry ? { version: entry.version } : {}),
    };
    if (
      await write(
        entry ? path + '/' + entry.id : path,
        entry ? 'PATCH' : 'POST',
        body,
        '已儲存日期標記。',
      )
    )
      setEditing(null);
  }
  async function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    const data = new FormData(event.currentTarget);
    if (
      await write(
        '/trips/' + trip.id,
        'PATCH',
        { start_date: data.get('start'), end_date: data.get('end'), version: selected.version },
        '已更新旅程日期及每日行程的對應日期。',
      )
    )
      setSelected(null);
  }
  const draft = editing && editing !== 'new' ? editing : null;
  const suggestions = snapshot?.recommendations ?? [];
  return (
    <section className="dc-root">
      <fieldset className="dc-layout" disabled={busy} aria-busy={busy}>
        <legend className="dc-sr">日期協調</legend>
        <div className="dc-heading">
          <h2>日期協調</h2>
          {!editing && (
            <button className="dc-primary" onClick={() => setEditing('new')}>
              <Plus size={16} /> 標記我的日期
            </button>
          )}
        </div>
        {notice && (
          <p role="status" className="dc-feedback">
            <Check size={16} />
            {notice}
          </p>
        )}
        {fetchError && (
          <p role="alert" className="dc-alert">
            {fetchError} <button onClick={() => setRevision((n) => n + 1)}>重試</button>
          </p>
        )}
        {editing && (
          <form className="dc-panel dc-form" key={draft?.id ?? 'new'} onSubmit={saveEntry}>
            <h3>{draft ? '修改日期標記' : '標記我的日期'}</h3>
            <div className="dc-cols">
              <label>
                開始日期
                <input type="date" name="start" required defaultValue={draft?.start_date} />
              </label>
              <label>
                結束日期（單日可留白）
                <input type="date" name="end" defaultValue={draft?.end_date} />
              </label>
            </div>
            <label>
              我的狀態
              <select name="status" defaultValue={draft?.status ?? 'yes'}>
                {Object.entries(labels).map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </select>
            </label>
            <div className="dc-actions">
              <button className="dc-primary">儲存標記</button>
              <button type="button" onClick={() => setEditing(null)}>
                取消
              </button>
            </div>
          </form>
        )}
        <div className="dc-panel dc-card">
          <h3>旅程日期</h3>
          <p>{formatDates(trip.start_date, trip.end_date)}</p>
          {owner && !selected && (
            <div>
              <button
                onClick={() =>
                  setSelected({
                    start_date: trip.start_date || '',
                    end_date: trip.end_date || '',
                    version: trip.version,
                  })
                }
              >
                設定旅程日期
              </button>
            </div>
          )}
          {selected && owner && (
            <form
              key={selected.start_date + '/' + selected.end_date}
              className="dc-form"
              onSubmit={apply}
            >
              <div className="dc-cols">
                <label>
                  旅程開始日
                  <input type="date" required name="start" defaultValue={selected.start_date} />
                </label>
                <label>
                  旅程結束日
                  <input type="date" required name="end" defaultValue={selected.end_date} />
                </label>
              </div>
              <p className="dc-note">
                Day 1 將對應開始日。原有行程項目會保留，超出新區間的安排可在每日行程調整。
              </p>
              <div className="dc-actions">
                <button className="dc-primary">
                  <CalendarCheck size={15} /> 確認套用日期
                </button>
                <button type="button" onClick={() => setSelected(null)}>
                  取消套用
                </button>
              </div>
            </form>
          )}
        </div>
        {!snapshot && !fetchError && <p role="status">載入日期標記中…</p>}
        {snapshot && (
          <>
            <div className="dc-panel dc-card">
              <h3>建議日期</h3>
              {!suggestions.length ? (
                <p className="dc-note">旅伴標記「可以」或「可能」後，就能比較共同時段。</p>
              ) : (
                <>
                  <small>依可以人數排序，同分時優先列出不行人數較少、可能人數較多的區間。</small>
                  {(showAll ? suggestions : suggestions.slice(0, 5)).map((s) => (
                    <div className="dc-availability-row" key={s.start_date}>
                      <div>
                        <strong>{formatDates(s.start_date, s.end_date)}</strong>
                        <small>
                          {s.yes === snapshot.member_count ? '全員可以 · ' : ''}
                          {s.yes} 可以 · {s.maybe} 可能 · {s.no} 不行 · {s.unknown} 未填
                        </small>
                      </div>
                      {owner && (
                        <button
                          onClick={() => {
                            setSelected({ ...s, version: trip.version });
                            document.querySelector('.dc-root')?.scrollIntoView({ block: 'start' });
                          }}
                        >
                          選用區間
                        </button>
                      )}
                    </div>
                  ))}
                  {suggestions.length > 5 && (
                    <button onClick={() => setShowAll(!showAll)}>
                      {showAll ? '收合' : '查看全部區間'}
                    </button>
                  )}
                </>
              )}
            </div>
            <div className="dc-panel dc-card">
              <h3>旅伴的日期標記</h3>
              {!snapshot.entries.length && <p className="dc-note">目前還沒有日期標記。</p>}
              {snapshot.entries.map((entry) => (
                <div className="dc-availability-row" key={entry.id}>
                  <div>
                    <strong>{formatDates(entry.start_date, entry.end_date)}</strong>
                    <small>
                      {members.find((m) => m.id === entry.user_id)?.nickname || '旅伴'} ·{' '}
                      {labels[entry.status]}
                    </small>
                  </div>
                  {entry.user_id === userId && (
                    <div className="dc-actions">
                      <button
                        onClick={() => {
                          setEditing(entry);
                          document.querySelector('.dc-root')?.scrollIntoView({ block: 'start' });
                        }}
                      >
                        <Pencil size={14} /> 修改
                      </button>
                      <button
                        className="dc-danger"
                        onClick={async () => {
                          if (
                            window.confirm('確定移除這筆日期標記？') &&
                            (await write(
                              path + '/' + entry.id + '?version=' + entry.version,
                              'DELETE',
                              undefined,
                              '已刪除日期標記。',
                            )) &&
                            draft?.id === entry.id
                          )
                            setEditing(null);
                        }}
                      >
                        <Trash2 size={14} /> 刪除
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </fieldset>
    </section>
  );
}
