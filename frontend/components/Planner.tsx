'use client';

import { AttachmentButton } from './Attachments';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowDownUp,
  CalendarDays,
  ChevronRight,
  Clock3,
  ExternalLink,
  GripVertical,
  ListPlus,
  MapPin,
  Navigation,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-react';
import { api } from '../lib/api';
import PlannerMap from './PlannerMap';
import { DayWeather, PlannerTools } from './PlannerTools';
import { ItemForm, PlaceForm, PlanningDialog } from './PlannerForms';
import {
  CategoryIcon,
  categories,
  mapLink,
  statusNames,
  type Editable,
  type Lease,
  type Place,
  type PlanItem,
  type TripDay,
} from './plannerTypes';
import './planner.css';

type Props = {
  tripId: string;
  userId: string;
  section: 'places' | 'map' | 'plan';
  refresh: number;
  onChange(): void;
  startDate: string | null;
  currency: string;
  setError(message: string): void;
};
type Dialog =
  | { type: 'day' }
  | { type: 'place'; place?: Place; lease?: Lease }
  | { type: 'detail'; place: Place }
  | { type: 'item'; dayId: string; initialPlace?: Place; item?: PlanItem; lease?: Lease }
  | { type: 'move'; item: PlanItem; lease: Lease }
  | { type: 'remove'; target: Place | PlanItem; lease: Lease; original?: boolean };
type Revision = {
  actor: string;
  action: string;
  changes: Record<string, { before: string; after: string }>;
  created_at: string;
};
const actions: Record<string, string> = {
  'place.created': '新增景點',
  'place.updated': '更新景點',
  'place.deleted': '移除原始景點',
  'place.restored': '復原版本',
  'candidate.removed': '移出候選',
  'candidate.restored': '復原候選',
};
const fieldNames: Record<string, string> = {
  restored_version: '復原版本',
  name: '名稱',
  address: '地址',
  latitude: '緯度',
  longitude: '經度',
  country: '國家',
  city: '城市',
  category: '分類',
  status: '意願',
  tags: '標籤',
  duration: '停留時間',
  cost: '預估費用',
  opening_hours: '營業時間',
  website: '官方網站',
  photo_url: '照片',
  notes: '備註',
};

function PlaceDetails({ place, currency }: { place: Place; currency: string }) {
  const [history, setHistory] = useState<Revision[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    api<Revision[]>(`/places/${place.id}/history`)
      .then((rows) => {
        if (alive) setHistory(rows);
      })
      .catch((reason) => {
        if (alive) setError(reason.message);
      });
    return () => {
      alive = false;
    };
  }, [place.id]);
  const metadata = [
    ['分類', categories[place.category]],
    ['意願', statusNames[place.status]],
    ['地址', place.address],
    ['地區', [place.country, place.city].filter(Boolean).join(' · ')],
    ['標籤', place.tags.join('、')],
    ['停留時間', place.duration && `${place.duration} 分鐘`],
    ['預估費用', place.cost != null && `${currency} ${place.cost}`],
    ['營業時間', place.opening_hours],
    ['座標', place.latitude != null && `${place.latitude}, ${place.longitude}`],
    ['備註', place.notes],
  ];
  return (
    <div className="wp-detail">
      {place.photo_url && (
        <img
          src={place.photo_url}
          alt={place.name}
          className="wp-detail-photo"
          referrerPolicy="no-referrer"
        />
      )}
      <dl>
        {metadata
          .filter(([, value]) => value !== false && value != null && value !== '')
          .map(([label, value]) => (
            <div key={String(label)}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
      </dl>
      <div className="wp-actions">
        <a href={mapLink(place)} target="_blank" rel="noreferrer" className="wp-text">
          Google Maps <ExternalLink size={14} />
        </a>
        <a href={mapLink(place, true)} target="_blank" rel="noreferrer" className="wp-text">
          導航 <Navigation size={14} />
        </a>
        {place.website && (
          <a href={place.website} target="_blank" rel="noreferrer" className="wp-text">
            官方網站 <ExternalLink size={14} />
          </a>
        )}
      </div>
      <details>
        <summary>修改紀錄</summary>
        <ul className="wp-history">
          {!history && <li>{error || '載入中…'}</li>}
          {history?.map((r, i) => (
            <li key={i}>
              <strong>
                {r.actor} · {actions[r.action] ?? r.action}
              </strong>
              <small>{new Date(r.created_at).toLocaleString('zh-TW')}</small>
              {Object.entries(r.changes).map(([key, change]) => (
                <small key={key}>
                  {fieldNames[key] || key}：{change.before} → {change.after}
                </small>
              ))}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function MoveForm({
  item,
  days,
  busy,
  save,
}: {
  item: PlanItem;
  days: TripDay[];
  busy: boolean;
  save(day: string, pos: number): void;
}) {
  const [dayId, setDayId] = useState(item.day_id);
  const choices = days.find((d) => d.id === dayId)?.items.filter((i) => i.id !== item.id) || [];
  return (
    <form
      className="wp-form"
      onSubmit={(event) => {
        event.preventDefault();
        save(dayId, Number(new FormData(event.currentTarget).get('position')));
      }}
    >
      <label>
        移至日期
        <select value={dayId} onChange={(e) => setDayId(e.target.value)}>
          {days.map((day) => (
            <option key={day.id} value={day.id}>
              Day {day.day_number}
              {day.date ? ` · ${day.date}` : ''}
            </option>
          ))}
        </select>
      </label>
      <label>
        放置位置
        <select
          key={dayId}
          name="position"
          defaultValue={
            dayId === item.day_id ? Math.min(item.position, choices.length) : choices.length
          }
        >
          {choices.map((row, i) => (
            <option key={row.id} value={i}>
              在「{row.title}」之前
            </option>
          ))}
          <option value={choices.length}>當天最後一項</option>
        </select>
      </label>
      <button className="btn btn-primary wp-save" disabled={busy}>
        確認移動
      </button>
    </form>
  );
}

function Workspace({ tripId, userId, section, refresh, onChange, currency, setError }: Props) {
  const [days, setDays] = useState<TripDay[]>([]);
  const [places, setPlaces] = useState<Place[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [reload, setReload] = useState(0);
  const [dayId, setDayId] = useState('');
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState('');
  const [dragged, setDragged] = useState<PlanItem | null>(null);
  const activeLease = useRef<string | null>(null);
  const mounted = useRef(true);
  const activeDay = days.find((d) => d.id === dayId) || days[0];
  const candidates = places.filter((p) => p.candidate);
  const referenced = new Set(days.flatMap((d) => d.items.map((i) => i.place_id)));
  const editing =
    places.some((p) => p.editing_by) || days.some((d) => d.items.some((i) => i.editing_by));
  useEffect(() => {
    // An abandoned tab sends no release event. Refresh visible locks until the lease expires.
    if (!editing) return;
    const timer = setInterval(() => setReload((n) => n + 1), 15000);
    return () => clearInterval(timer);
  }, [editing]);
  useEffect(() => {
    let alive = true;
    Promise.all([api<TripDay[]>(`/trips/${tripId}/days`), api<Place[]>(`/trips/${tripId}/places`)])
      .then(([d, p]) => {
        if (alive) {
          setDays(d);
          setPlaces(p);
          setLoaded(true);
          setLoadError('');
        }
      })
      .catch((error) => {
        if (alive) setLoadError(error.message || '行程資料載入失敗。');
      });
    return () => {
      alive = false;
    };
  }, [tripId, refresh, reload]);
  const release = useCallback(() => {
    const id = activeLease.current;
    activeLease.current = null;
    if (id) void api(`/edit-leases/${id}`, 'DELETE').catch(() => {});
  }, []);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      release();
    };
  }, [release]);
  const lease = dialog && 'lease' in dialog ? dialog.lease : undefined;
  useEffect(() => {
    if (!lease) return;
    const timer = setInterval(() => {
      void api(`/edit-leases/${lease.id}/renew`, 'POST').catch((error) => {
        if (activeLease.current === lease.id)
          setFormError(error.message || '鎖定已失效，請重新開啟編輯。');
      });
    }, 35000);
    return () => clearInterval(timer);
  }, [lease]);

  function open(next: Dialog) {
    setFormError('');
    setDialog(next);
  }
  function close() {
    if (!busy) {
      release();
      setDialog(null);
    }
  }
  async function acquire(target: Editable, type: 'item' | 'place') {
    const lock = await api<Lease>('/edit-leases', 'POST', {
      resource_type: type,
      resource_id: target.id,
    });
    activeLease.current = lock.id;
    if (!mounted.current || lock.version !== target.version) {
      release();
      setReload((n) => n + 1);
      throw new Error('資料已更新，請重新開啟。');
    }
    return lock;
  }
  async function edit(target: Place | PlanItem, action: 'edit' | 'remove' | 'original' | 'move') {
    if (busy) return;
    setBusy(true);
    try {
      const lock = await acquire(target, 'candidate' in target ? 'place' : 'item');
      if (action === 'remove' || action === 'original')
        open({ type: 'remove', target, lease: lock, original: action === 'original' });
      else if ('candidate' in target) open({ type: 'place', place: target, lease: lock });
      else if (action === 'move') open({ type: 'move', item: target, lease: lock });
      else open({ type: 'item', item: target, dayId: target.day_id, lease: lock });
    } catch (error) {
      setError(error instanceof Error ? error.message : '無法取得編輯鎖。');
    } finally {
      setBusy(false);
    }
  }
  async function write(path: string, method: string, body: unknown) {
    if (busy) return;
    setBusy(true);
    setFormError('');
    try {
      const result = await api<{ id?: string }>(path, method, body);
      if (dialog?.type === 'day' && result?.id) setDayId(result.id);
      activeLease.current = null;
      setDialog(null);
      setReload((n) => n + 1);
      onChange();
    } catch (error) {
      const text = error instanceof Error ? error.message : '儲存失敗，請再試一次。';
      if (dialog) setFormError(text);
      else setError(text);
    } finally {
      setBusy(false);
    }
  }
  async function drop(day: TripDay, before?: PlanItem) {
    const item = dragged;
    setDragged(null);
    if (!item || item.id === before?.id || busy) return;
    setBusy(true);
    const ordered = day.items.filter((i) => i.id !== item.id);
    const position = before ? ordered.findIndex((i) => i.id === before.id) : ordered.length;
    try {
      const lock = await acquire(item, 'item');
      await api(`/itinerary-items/${item.id}/move`, 'POST', {
        day_id: day.id,
        position,
        version: item.version,
        lease_id: lock.id,
      });
      activeLease.current = null;
      setDayId(day.id);
      setReload((n) => n + 1);
      onChange();
    } catch (error) {
      release();
      setError(error instanceof Error ? error.message : '移動失敗，請再試一次。');
    } finally {
      setBusy(false);
    }
  }
  function schedule(place?: Place) {
    if (!activeDay) {
      setError('請先在每日行程新增日期。');
      return;
    }
    open({ type: 'item', dayId: activeDay.id, initialPlace: place });
  }
  const dialogTitle =
    dialog?.type === 'day'
      ? '新增日期'
      : dialog?.type === 'detail'
        ? dialog.place.name
        : dialog?.type === 'remove'
          ? '確認移除'
          : dialog?.type === 'move'
            ? '移動活動'
            : dialog?.type === 'place'
              ? dialog.place
                ? '編輯景點'
                : '新增候選景點'
              : dialog?.type === 'item' && dialog.item
                ? '編輯活動'
                : '新增活動';
  return (
    <section className="wp-planner">
      <header className="wp-header">
        <div>
          <h2>
            {section === 'plan' ? '每日行程' : section === 'places' ? '候選景點' : '景點地圖'}
          </h2>
          {loaded && (
            <p>
              {section === 'plan'
                ? `共 ${days.length} 天 · ${days.reduce((n, d) => n + d.items.length, 0)} 個活動`
                : section === 'places'
                  ? `已收藏 ${candidates.length} 個地點`
                  : '查看景點位置與導航'}
            </p>
          )}
        </div>
        {section !== 'map' && (
          <button
            className="btn btn-primary"
            onClick={() => open(section === 'places' ? { type: 'place' } : { type: 'day' })}
          >
            <Plus size={16} />
            {section === 'places' ? '新增景點' : '新增日期'}
          </button>
        )}
      </header>
      {section === 'plan' && loaded && (
        <PlannerTools
          tripId={tripId}
          days={days}
          places={places}
          refresh={refresh}
          onChange={onChange}
        />
      )}
      {loadError && (
        <p className="wp-notice" role="alert">
          {loadError}{' '}
          <button className="wp-text" onClick={() => setReload((n) => n + 1)}>
            重試
          </button>
        </p>
      )}
      {!loaded && !loadError && <p role="status">載入旅程資料中…</p>}
      {loaded && section === 'map' && (
        <PlannerMap
          days={days}
          places={places.filter((p) => p.candidate || referenced.has(p.id))}
        />
      )}
      {loaded && section === 'places' && (
        <>
          {!!candidates.length && (
            <label className="wp-filter">
              <span>篩選景點</span>
              <input
                type="search"
                placeholder="搜尋名稱、城市或標籤"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
            </label>
          )}
          <div className="wp-place-grid">
            {candidates
              .filter((p) =>
                [p.name, p.city, ...p.tags].join(' ').toLowerCase().includes(filter.toLowerCase()),
              )
              .map((p) => (
                <article className="wp-place-card" key={p.id}>
                  {p.photo_url && (
                    <img
                      className="wp-place-photo"
                      src={p.photo_url}
                      alt={p.name}
                      loading="lazy"
                      referrerPolicy="no-referrer"
                    />
                  )}
                  <div className="wp-card-top">
                    <span className={`wp-symbol wp-${p.category}`}>
                      <CategoryIcon type={p.category} />
                    </span>
                    <span className="wp-badge">{statusNames[p.status]}</span>
                  </div>
                  <button className="wp-name" onClick={() => open({ type: 'detail', place: p })}>
                    {p.name}
                  </button>
                  <p className="wp-meta">
                    {[p.city, p.country].filter(Boolean).join(' · ') ||
                      p.address ||
                      categories[p.category]}
                  </p>
                  {p.tags.length > 0 && (
                    <div className="wp-tags">
                      {p.tags.map((tag, i) => (
                        <span key={i}>#{tag}</span>
                      ))}
                    </div>
                  )}
                  {p.editing_by && <small>{p.editing_by} 編輯中</small>}
                  <div className="wp-actions">
                    <button className="wp-text" onClick={() => schedule(p)}>
                      <ListPlus size={16} /> 排入行程
                    </button>
                    <a
                      href={mapLink(p, true)}
                      target="_blank"
                      rel="noreferrer"
                      className="wp-icon"
                      aria-label={`導航至${p.name}`}
                    >
                      <Navigation size={15} />
                    </a>
                    {p.editable_by === userId && (
                      <>
                        <button
                          className="wp-icon"
                          disabled={busy || !!p.editing_by}
                          aria-label={`編輯${p.name}`}
                          onClick={() => void edit(p, 'edit')}
                        >
                          <Pencil size={15} />
                        </button>
                        <button
                          className="wp-icon"
                          disabled={busy || !!p.editing_by}
                          aria-label={`將${p.name}移出候選`}
                          onClick={() => void edit(p, 'remove')}
                        >
                          <Trash2 size={15} />
                        </button>
                      </>
                    )}
                  </div>
                </article>
              ))}
          </div>
          {!candidates.length && (
            <div className="wp-empty">
              <MapPin />
              <h3>還沒有候選景點</h3>
              <p>搜尋想去的地方，或手動新增第一個景點。</p>
              <button className="btn btn-secondary" onClick={() => open({ type: 'place' })}>
                <Plus size={15} />
                新增景點
              </button>
            </div>
          )}
          {filter &&
            !candidates.some((p) =>
              [p.name, p.city, ...p.tags].join(' ').toLowerCase().includes(filter.toLowerCase()),
            ) && <p>找不到符合條件的景點。</p>}
          {places.some((p) => !p.candidate) && (
            <details>
              <summary>已移出候選的景點</summary>
              {places
                .filter((p) => !p.candidate)
                .map((p) => (
                  <button
                    key={p.id}
                    className="wp-text"
                    onClick={() => open({ type: 'detail', place: p })}
                  >
                    {p.name}
                  </button>
                ))}
            </details>
          )}
        </>
      )}
      {loaded && section === 'plan' && (
        <>
          <div className="wp-day-tabs" aria-label="選擇行程日">
            {days.map((day) => (
              <button
                key={day.id}
                className={`wp-day-tab ${day.id === activeDay?.id ? 'wp-active' : ''}`}
                aria-pressed={day.id === activeDay?.id}
                onClick={() => setDayId(day.id)}
                onDragOver={(e) => {
                  if (dragged) e.preventDefault();
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  void drop(day);
                }}
              >
                <span>Day {String(day.day_number).padStart(2, '0')}</span>
                <small>{day.date || '日期未定'}</small>
              </button>
            ))}
          </div>
          {activeDay && (
            <div
              className="wp-day-card"
              onDragOver={(e) => {
                if (dragged) e.preventDefault();
              }}
              onDrop={(e) => {
                e.preventDefault();
                void drop(activeDay);
              }}
            >
              <div className="wp-day-heading">
                <div className="wp-day-title">
                  <CalendarDays size={22} />
                  <div>
                    <h3>{activeDay.title || `第 ${activeDay.day_number} 天`}</h3>
                    <small>
                      {[activeDay.date, activeDay.timezone].filter(Boolean).join(' · ')}
                    </small>
                  </div>
                </div>
                <button className="btn btn-secondary" onClick={() => schedule()}>
                  <Plus size={15} /> 新增活動
                </button>
              </div>
              <DayWeather day={activeDay} places={places} />
              {!activeDay.items.length && (
                <div className="wp-empty">
                  <CalendarDays />
                  <h3>這天還沒有安排行程</h3>
                  <p>從候選景點選擇，或加入交通、用餐與自訂活動。</p>
                </div>
              )}
              <ol className="wp-timeline">
                {activeDay.items.map((i) => {
                  const place = places.find((p) => p.id === i.place_id);
                  const own = i.editable_by === userId;
                  return (
                    <li
                      key={i.id}
                      draggable={own && !i.editing_by && !busy}
                      onDragStart={(e) => {
                        e.dataTransfer.setData('text/plain', i.id);
                        e.dataTransfer.effectAllowed = 'move';
                        setDragged(i);
                      }}
                      onDragEnd={() => setDragged(null)}
                      onDragOver={(e) => {
                        if (dragged) e.preventDefault();
                      }}
                      onDrop={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        void drop(activeDay, i);
                      }}
                    >
                      <div className="wp-time">
                        {i.start_time || i.suggested_time || '未定'}
                        {i.suggested_time && <small>建議</small>}
                        {i.end_time && <small>{i.end_time}</small>}
                      </div>
                      <span className={`wp-symbol wp-${i.item_type}`}>
                        <CategoryIcon type={i.item_type} />
                      </span>
                      <div className="wp-item-body">
                        <small>
                          {categories[i.item_type]}
                          {' · '}
                          {i.local_timezone || activeDay.timezone}
                          {i.duration ? ` · ${i.duration} 分鐘` : ''}
                        </small>
                        <h4>{i.title}</h4>
                        <AttachmentButton tripId={tripId} kind="item" targetId={i.id} />
                        {i.clock_note && <small>{i.clock_note}</small>}
                        {i.start_instant &&
                          i.local_timezone !== Intl.DateTimeFormat().resolvedOptions().timeZone && (
                            <small>
                              裝置時間 ·{' '}
                              {new Date(i.start_instant).toLocaleString('zh-TW', {
                                month: 'numeric',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                                hourCycle: 'h23',
                                timeZoneName: 'short',
                              })}
                            </small>
                          )}
                        {place && (
                          <button
                            className="wp-text wp-address"
                            onClick={() => open({ type: 'detail', place })}
                          >
                            <MapPin size={13} />
                            {place.address || place.name}
                            <ChevronRight size={13} />
                          </button>
                        )}
                        {i.notes && <p>{i.notes}</p>}
                        {i.archived_place && (
                          <small>
                            已移除景點 ·{' '}
                            {[i.archived_place.name, i.archived_place.address]
                              .filter(Boolean)
                              .join(' · ')}
                          </small>
                        )}
                        {i.overlap && (
                          <span className="wp-overlap">
                            <Clock3 size={12} />
                            時間重疊
                          </span>
                        )}
                        {i.editing_by && <small>{i.editing_by} 編輯中</small>}
                      </div>
                      {own && (
                        <div className="wp-item-actions">
                          <GripVertical size={16} className="wp-grip" aria-label="可拖曳排序" />
                          <button
                            className="wp-icon"
                            disabled={busy || !!i.editing_by}
                            aria-label={`移動${i.title}`}
                            onClick={() => void edit(i, 'move')}
                          >
                            <ArrowDownUp size={15} />
                          </button>
                          <button
                            className="wp-icon"
                            disabled={busy || !!i.editing_by}
                            aria-label={`編輯${i.title}`}
                            onClick={() => void edit(i, 'edit')}
                          >
                            <Pencil size={15} />
                          </button>
                          <button
                            className="wp-icon"
                            disabled={busy || !!i.editing_by}
                            aria-label={`刪除${i.title}`}
                            onClick={() => void edit(i, 'remove')}
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ol>
            </div>
          )}
          {!activeDay && (
            <div className="wp-empty">
              <CalendarDays />
              <h3>新增第一天，開始安排行程。</h3>
            </div>
          )}
        </>
      )}
      {dialog && (
        <PlanningDialog title={dialogTitle} close={close}>
          {formError && (
            <p className="wp-notice" role="alert">
              {formError}
            </p>
          )}
          {dialog.type === 'day' && (
            <form
              className="wp-form"
              onSubmit={(e) => {
                e.preventDefault();
                const data = Object.fromEntries(new FormData(e.currentTarget));
                void write(`/trips/${tripId}/days`, 'POST', data);
              }}
            >
              <label>
                當日主題（選填）
                <input name="title" maxLength={150} placeholder={`第 ${days.length + 1} 天`} />
              </label>
              <label>
                當地時區
                <input
                  name="timezone"
                  required
                  maxLength={64}
                  defaultValue={
                    activeDay?.timezone ||
                    Intl.DateTimeFormat().resolvedOptions().timeZone ||
                    'Asia/Taipei'
                  }
                />
              </label>
              <button className="btn btn-primary wp-save" disabled={busy}>
                新增日期
              </button>
            </form>
          )}
          {dialog.type === 'detail' && (
            <>
              <PlaceDetails place={dialog.place} currency={currency} />
              {dialog.place.editable_by === userId && (
                <button
                  className="btn btn-secondary"
                  disabled={busy || !!dialog.place.editing_by}
                  onClick={() => void edit(dialog.place, 'original')}
                >
                  移除原始景點
                </button>
              )}
            </>
          )}
          {dialog.type === 'place' && (
            <PlaceForm
              tripId={tripId}
              place={dialog.place}
              currency={currency}
              busy={busy}
              save={async (values) => {
                if (dialog.place && dialog.lease)
                  await write(`/places/${dialog.place.id}`, 'PATCH', {
                    ...values,
                    version: dialog.place.version,
                    lease_id: dialog.lease.id,
                  });
                else await write(`/trips/${tripId}/places`, 'POST', values);
              }}
            />
          )}
          {dialog.type === 'item' && (
            <ItemForm
              days={days}
              dayId={dialog.dayId}
              item={dialog.item}
              initialPlace={dialog.initialPlace}
              places={places}
              busy={busy}
              save={async ({ day_id, ...values }) => {
                if (dialog.item && dialog.lease)
                  await write(`/itinerary-items/${dialog.item.id}`, 'PATCH', {
                    ...values,
                    version: dialog.item.version,
                    lease_id: dialog.lease.id,
                  });
                else await write(`/days/${day_id}/items`, 'POST', values);
              }}
            />
          )}
          {dialog.type === 'move' && (
            <MoveForm
              item={dialog.item}
              days={days}
              busy={busy}
              save={(day, position) =>
                void write(`/itinerary-items/${dialog.item.id}/move`, 'POST', {
                  day_id: day,
                  position,
                  version: dialog.item.version,
                  lease_id: dialog.lease.id,
                })
              }
            />
          )}
          {dialog.type === 'remove' && (
            <div className="wp-form">
              <p>
                {'candidate' in dialog.target
                  ? dialog.original
                    ? `移除原始景點「${dialog.target.name}」？已排入的活動會保留地點名稱與地址，可從變更紀錄復原。`
                    : `將「${dialog.target.name}」移出候選景點？已排入的行程會保留。`
                  : `刪除活動「${dialog.target.title}」？`}
              </p>
              <div className="wp-actions">
                <button className="btn btn-secondary" onClick={close} disabled={busy}>
                  取消
                </button>
                <button
                  className="btn wp-danger"
                  disabled={busy}
                  onClick={() =>
                    void write(
                      'candidate' in dialog.target
                        ? dialog.original
                          ? `/places/${dialog.target.id}`
                          : `/trips/${tripId}/candidates/${dialog.target.candidate_id}`
                        : `/itinerary-items/${dialog.target.id}`,
                      'DELETE',
                      { version: dialog.target.version, lease_id: dialog.lease.id },
                    )
                  }
                >
                  確認移除
                </button>
              </div>
            </div>
          )}
        </PlanningDialog>
      )}
    </section>
  );
}

export default function Planner(props: Props) {
  return <Workspace key={`${props.tripId}-${props.section}`} {...props} />;
}
