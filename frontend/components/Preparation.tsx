'use client';
import { useEffect, useState, type FormEvent } from 'react';
import {
  CalendarDays,
  CheckCheck,
  ClipboardList,
  Flag,
  LockKeyhole,
  Plus,
  UsersRound,
} from 'lucide-react';
import { api } from '../lib/api';
import { errorText, type Member } from '../lib/trips';
import { Button } from './ui/button';
import { AttachmentButton } from './Attachments';
import { Modal } from './ui/dialog';
import Bookings, { type Booking } from './Reservations';
import './preparation.css';

import { ItemOptions, type DayRef, type PrepProps } from './preparationTypes';
type PlaceRef = { id: string; name: string };
type Person = { user_id: string; nickname: string; state: State };
type State = 'todo' | 'doing' | 'done';
type Scope = 'shared' | 'personal';
type Priority = 'low' | 'normal' | 'high';
type Task = {
  id: string;
  title: string;
  description: string;
  scope: Scope;
  priority: Priority;
  due_date: string | null;
  recurrence: 'none' | 'daily' | 'weekly' | 'monthly';
  period: number;
  completed_periods: {
    period: number;
    due_date: string;
    progress: { user_id: string; state: State }[];
  }[];
  state: State;
  assignees: Person[];
  created_by: string;
  version: number;
  item_id: string | null;
  place_id: string | null;
};
const priorities = { low: '低', normal: '一般', high: '高' };
const states = { todo: '待處理', doing: '進行中', done: '已完成' };
const cycleNames = { none: '不重複', daily: '每天', weekly: '每週', monthly: '每月' };
function TaskEditor({
  task,
  scope,
  userId,
  members,
  days,
  places,
  close,
  save,
}: {
  task?: Task;
  scope: Scope;
  userId: string;
  members: Member[];
  days: DayRef[];
  places: PlaceRef[];
  close: () => void;
  save: (payload: unknown) => Promise<void>;
}) {
  const [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const people = [
    ...members.map((m) => ({ id: m.id, name: m.nickname })),
    ...(task?.assignees ?? [])
      .filter((p) => !members.some((m) => m.id === p.user_id))
      .map((p) => ({ id: p.user_id, name: p.nickname + '（已退出）' })),
  ];
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError('');
    try {
      await save({
        title: f.get('title'),
        description: f.get('description'),
        scope,
        priority: f.get('priority'),
        due_date: f.get('due_date') || null,
        recurrence: f.get('recurrence') || 'none',
        assignees: scope === 'personal' ? [userId] : f.getAll('assignee'),
        place_id: f.get('place_id') || null,
        item_id: f.get('item_id') || null,
        ...(task ? { version: task.version } : {}),
      });
      close();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={task ? '編輯任務' : '新增' + (scope === 'shared' ? '共用任務' : '個人任務')}
      onClose={close}
    >
      <form onSubmit={submit} className="stack">
        <label className="field">
          任務名稱
          <input required name="title" maxLength={160} defaultValue={task?.title} autoFocus />
        </label>
        <label className="field">
          說明
          <textarea name="description" rows={2} maxLength={4000} defaultValue={task?.description} />
        </label>
        <div className="form-row">
          <label className="field">
            截止日期
            <input type="date" name="due_date" defaultValue={task?.due_date ?? ''} />
          </label>
          <label className="field">
            優先程度
            <select name="priority" defaultValue={task?.priority ?? 'normal'}>
              {Object.entries(priorities).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="field">
          重複週期
          <select
            name="recurrence"
            defaultValue={task?.recurrence || 'none'}
            aria-describedby="prep-recurrence-description"
          >
            {Object.entries(cycleNames).map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <small id="prep-recurrence-description">
          所有負責人完成後會保留本期紀錄，並依截止日期開啟下一期。
        </small>
        {scope === 'shared' && (
          <fieldset>
            <legend>負責人</legend>
            <div className="prep-choices">
              {people.map((p) => (
                <label key={p.id}>
                  <input
                    type="checkbox"
                    name="assignee"
                    value={p.id}
                    defaultChecked={
                      task ? task.assignees.some((a) => a.user_id === p.id) : p.id === userId
                    }
                  />
                  {p.name}
                </label>
              ))}
            </div>
          </fieldset>
        )}
        <label className="field">
          關聯景點
          <select name="place_id" defaultValue={task?.place_id ?? ''}>
            <option value="">無關聯景點</option>
            {task?.place_id && !places.some((p) => p.id === task.place_id) && (
              <option value={task.place_id}>已移除的原始景點</option>
            )}
            {places.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          關聯活動
          <select name="item_id" defaultValue={task?.item_id ?? ''}>
            <ItemOptions days={days} linkedId={task?.item_id} />
          </select>
        </label>
        {error && (
          <p className="error-inline" role="alert">
            {error}
          </p>
        )}
        <div className="form-actions">
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button type="submit" disabled={busy}>
            儲存任務
          </Button>
        </div>
      </form>
    </Modal>
  );
}
function Tasks({
  rows,
  days,
  places,
  ...props
}: PrepProps & { rows: Task[]; days: DayRef[]; places: PlaceRef[] }) {
  const { trip, userId, members, onChange, setError } = props;
  const [scope, setScope] = useState<Scope>('shared'),
    [editor, setEditor] = useState<Task | 'new' | null>(null),
    [busy, setBusy] = useState(false);
  const shown = rows.filter((t) => t.scope === scope);
  const complete = shown.filter((t) => t.state === 'done').length;
  const base = '/trips/' + trip.id + '/tasks';
  async function act(path: string, method: string, data: unknown) {
    setBusy(true);
    try {
      await api(path, method, data);
      onChange();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="prep-root">
      <div className="prep-heading">
        <h2>
          <ClipboardList />
          行前清單
        </h2>
        <Button onClick={() => setEditor('new')}>
          <Plus size={16} />
          新增任務
        </Button>
      </div>
      <div className="prep-toolbar">
        <div className="day-tabs">
          <button className={scope === 'shared' ? 'on' : ''} onClick={() => setScope('shared')}>
            <UsersRound size={15} />
            共用待辦
          </button>
          <button className={scope === 'personal' ? 'on' : ''} onClick={() => setScope('personal')}>
            <LockKeyhole size={15} />
            個人清單
          </button>
        </div>
        <span>
          {complete} / {shown.length} 已完成
        </span>
      </div>
      {!shown.length && (
        <div className="empty">
          <CheckCheck />
          <h3>{scope === 'shared' ? '還沒有共用待辦' : '你的行前清單是空的'}</h3>
          <p>
            {scope === 'shared'
              ? '新增任務並指派旅伴，例如購買車票。'
              : '這裡的任務只有你自己看得到。'}
          </p>
        </div>
      )}
      <div className="prep-list">
        {shown.map((t) => {
          const mine = t.assignees.find((p) => p.user_id === userId);
          const edit = t.created_by === userId || (scope === 'shared' && trip.owner_id === userId);
          const link = [
            t.place_id && (places.find((p) => p.id === t.place_id)?.name || '已移除的原始景點'),
            ...days.flatMap((d) =>
              d.items
                .filter((i) => i.id === t.item_id)
                .map((i) => 'Day ' + d.day_number + ' · ' + i.title),
            ),
          ]
            .filter(Boolean)
            .join(' / ');
          return (
            <article key={t.id} className="card prep-card">
              <div className="prep-line">
                <h3>{t.title}</h3>
                <span className={'badge ' + (t.state === 'done' ? 'badge-confirmed' : 'neutral')}>
                  {states[t.state]}
                </span>
              </div>
              {t.description && <p>{t.description}</p>}
              <div className="prep-meta">
                {t.recurrence && t.recurrence !== 'none' && (
                  <span>
                    {cycleNames[t.recurrence]} · 第 {t.period} 期
                  </span>
                )}
                <AttachmentButton tripId={trip.id} kind="task" targetId={t.id} />
                <span>
                  <Flag size={14} />
                  {priorities[t.priority]}優先
                </span>
                {t.due_date && (
                  <span>
                    <CalendarDays size={14} />
                    {t.due_date}
                  </span>
                )}
                {link && <span>{link}</span>}
              </div>
              {t.completed_periods?.length > 0 && (
                <details>
                  <summary>已完成期別（{t.completed_periods.length}）</summary>
                  <ul>
                    {t.completed_periods.map((p) => (
                      <li key={p.period}>
                        第 {p.period} 期 · {p.due_date} ·{' '}
                        {p.progress
                          .map(
                            (a) =>
                              (members.find((m) => m.id === a.user_id)?.nickname || '已退出旅伴') +
                              ' ' +
                              states[a.state],
                          )
                          .join('、')}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              <div className="prep-line">
                <span className="prep-assignees">
                  {t.assignees.length
                    ? t.assignees.map((p) => p.nickname + ' · ' + states[p.state]).join('、')
                    : '尚未指派'}
                </span>
                <div className="prep-buttons">
                  {mine && (
                    <label className="prep-state">
                      我的進度
                      <select
                        aria-label={t.title + ' 我的進度'}
                        value={mine.state}
                        disabled={busy}
                        onChange={(e) =>
                          void act(base + '/' + t.id + '/progress', 'PUT', {
                            state: e.target.value,
                            version: t.version,
                          })
                        }
                      >
                        {Object.entries(states).map(([k, v]) => (
                          <option key={k} value={k}>
                            {v}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  {edit && (
                    <>
                      <button onClick={() => setEditor(t)}>編輯</button>
                      <button
                        disabled={busy}
                        onClick={() => {
                          if (confirm('刪除「' + t.title + '」？'))
                            void act(base + '/' + t.id, 'DELETE', { version: t.version });
                        }}
                      >
                        刪除
                      </button>
                    </>
                  )}
                </div>
              </div>
            </article>
          );
        })}
      </div>
      {editor && (
        <TaskEditor
          task={editor === 'new' ? undefined : editor}
          scope={scope}
          userId={userId}
          members={members}
          days={days}
          places={places}
          close={() => setEditor(null)}
          save={async (data) => {
            await api(
              editor === 'new' ? base : base + '/' + editor.id,
              editor === 'new' ? 'POST' : 'PUT',
              data,
            );
            onChange();
          }}
        />
      )}
    </section>
  );
}
export default function Preparation(props: PrepProps & { section: 'tasks' | 'bookings' }) {
  const { trip, section, refresh } = props;
  const [data, setData] = useState<{
      tasks: Task[];
      bookings: Booking[];
      days: DayRef[];
      places: PlaceRef[];
    } | null>(null),
    [error, setError] = useState(''),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    let current = true;
    const base = '/trips/' + trip.id;
    Promise.all([
      section === 'tasks' ? api<Task[]>(base + '/tasks') : Promise.resolve([]),
      section === 'bookings' ? api<Booking[]>(base + '/bookings') : Promise.resolve([]),
      api<DayRef[]>(base + '/days'),
      section === 'tasks' ? api<PlaceRef[]>(base + '/places') : Promise.resolve([]),
    ])
      .then(([tasks, bookings, days, places]) => {
        if (current) {
          setData({ tasks, bookings, days, places });
          setError('');
        }
      })
      .catch((e) => {
        if (current) setError(errorText(e));
      });
    return () => {
      current = false;
    };
  }, [trip.id, section, refresh, retry]);
  return (
    <>
      {error && (
        <p role="alert" className="error-inline">
          {error} <button onClick={() => setRetry((n) => n + 1)}>重試</button>
        </p>
      )}
      {!data && !error && <p role="status">載入中…</p>}
      {data &&
        (section === 'tasks' ? (
          <Tasks {...props} rows={data.tasks} days={data.days} places={data.places} />
        ) : (
          <Bookings {...props} rows={data.bookings} days={data.days} />
        ))}
    </>
  );
}
