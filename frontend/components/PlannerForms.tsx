'use client';

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Search, X } from 'lucide-react';
import { api } from '../lib/api';
import {
  categories,
  parseGooglePlaceLink,
  statusNames,
  type Category,
  type Place,
  type PlanItem,
  type TripDay,
} from './plannerTypes';

export function PlanningDialog({
  title,
  close,
  children,
}: {
  title: string;
  close(): void;
  children: ReactNode;
}) {
  const element = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = element.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={element}
      className="wp-dialog"
      aria-labelledby="wp-dialog-title"
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
    >
      <div className="wp-dialog-head">
        <h2 id="wp-dialog-title">{title}</h2>
        <button type="button" className="wp-icon" aria-label="關閉" onClick={close}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

export type SaveForm = (values: Record<string, unknown>) => Promise<void>;
function valuesOf(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  return Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>;
}
function options(labels: Record<string, string>) {
  return Object.entries(labels).map(([value, label]) => (
    <option key={value} value={value}>
      {label}
    </option>
  ));
}
type SearchResult = { name: string; latitude: number; longitude: number; source: string };

export function PlaceForm({
  place,
  tripId,
  currency,
  busy,
  save,
}: {
  place?: Place;
  tripId: string;
  currency: string;
  busy: boolean;
  save: SaveForm;
}) {
  const [name, setName] = useState(place?.name ?? '');
  const [lat, setLat] = useState(String(place?.latitude ?? ''));
  const [lng, setLng] = useState(String(place?.longitude ?? ''));
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [looking, setLooking] = useState(false);
  const [message, setMessage] = useState('');
  async function search(event: FormEvent) {
    event.preventDefault();
    if (/^https?:\/\//i.test(query.trim())) {
      const parsed = parseGooglePlaceLink(query.trim());
      setResults([]);
      if (parsed) {
        if (parsed.name) setName(parsed.name);
        if (parsed.latitude != null) {
          setLat(String(parsed.latitude));
          setLng(String(parsed.longitude));
        }
        setMessage('已帶入連結中的資料，請確認並補充欄位。');
      } else setMessage('連結未包含可辨識的地點，請手動填寫名稱與座標。');
      return;
    }
    setLooking(true);
    setMessage('');
    try {
      const data = await api<SearchResult[]>(
        `/trips/${tripId}/place-search?q=${encodeURIComponent(query.trim())}`,
      );
      setResults(data);
      if (!data.length) setMessage('沒有找到附座標的地點，可直接手動填寫。');
    } catch (error) {
      setResults([]);
      setMessage(error instanceof Error ? error.message : '搜尋服務暫時無法使用，可直接手動填寫。');
    } finally {
      setLooking(false);
    }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    const v = valuesOf(event);
    void save({
      ...v,
      latitude: lat ? Number(lat) : null,
      longitude: lng ? Number(lng) : null,
      tags: v.tags
        .split(/[,，、]/)
        .map((tag) => tag.trim())
        .filter(Boolean),
      duration: v.duration ? Number(v.duration) : null,
      cost: v.cost || null,
    });
  }
  return (
    <>
      {!place && (
        <form className="wp-search" onSubmit={search}>
          <label htmlFor="wp-search">搜尋地點</label>
          <div>
            <input
              id="wp-search"
              type="search"
              maxLength={2048}
              placeholder="景點名稱或 Google Maps 連結"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button className="btn btn-secondary" disabled={looking || !query.trim()}>
              <Search size={16} />
              {looking ? '搜尋中' : '搜尋'}
            </button>
          </div>
          {message && <small role="status">{message}</small>}
          {results.length > 0 && (
            <ul>
              {results.map((result) => (
                <li key={result.source}>
                  <button
                    type="button"
                    className="wp-text"
                    onClick={() => {
                      setName(result.name);
                      setLat(String(result.latitude));
                      setLng(String(result.longitude));
                      setResults([]);
                    }}
                  >
                    {result.name}
                  </button>
                  <a href={result.source} target="_blank" rel="noreferrer">
                    維基百科
                  </a>
                </li>
              ))}
            </ul>
          )}
        </form>
      )}
      <form className="wp-form" onSubmit={submit}>
        <label>
          景點名稱
          <input
            name="name"
            required
            maxLength={150}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <div className="wp-form-pair">
          <label>
            分類
            <select name="category" defaultValue={place?.category ?? 'place'}>
              {options(categories)}
            </select>
          </label>
          <label>
            意願
            <select name="status" defaultValue={place?.status ?? 'want'}>
              {options(statusNames)}
            </select>
          </label>
        </div>
        <label>
          地址
          <input name="address" maxLength={800} defaultValue={place?.address} />
        </label>
        <div className="wp-form-pair">
          <label>
            緯度
            <input
              name="latitude"
              type="number"
              step="any"
              min={-90}
              max={90}
              required={!!lng}
              value={lat}
              onChange={(e) => setLat(e.target.value)}
            />
          </label>
          <label>
            經度
            <input
              name="longitude"
              type="number"
              step="any"
              min={-180}
              max={180}
              required={!!lat}
              value={lng}
              onChange={(e) => setLng(e.target.value)}
            />
          </label>
        </div>
        <details open={!!place}>
          <summary>詳細資料</summary>
          <div className="wp-form">
            <div className="wp-form-pair">
              <label>
                國家
                <input name="country" maxLength={100} defaultValue={place?.country} />
              </label>
              <label>
                城市
                <input name="city" maxLength={100} defaultValue={place?.city} />
              </label>
            </div>
            <label>
              標籤（以逗號分隔）
              <input name="tags" defaultValue={place?.tags.join('、')} />
            </label>
            <div className="wp-form-pair">
              <label>
                停留分鐘
                <input
                  name="duration"
                  type="number"
                  min="1"
                  max="1440"
                  defaultValue={place?.duration ?? ''}
                />
              </label>
              <label>
                預估費用（{currency}）
                <input
                  name="cost"
                  type="number"
                  min="0"
                  step="0.01"
                  defaultValue={place?.cost ?? ''}
                />
              </label>
            </div>
            <label>
              營業時間
              <input name="opening_hours" maxLength={400} defaultValue={place?.opening_hours} />
            </label>
            <label>
              官方網站
              <input name="website" type="url" maxLength={2000} defaultValue={place?.website} />
            </label>
            <label>
              照片網址
              <input name="photo_url" type="url" maxLength={2000} defaultValue={place?.photo_url} />
            </label>
            <label>
              備註
              <textarea name="notes" rows={3} maxLength={4000} defaultValue={place?.notes} />
            </label>
          </div>
        </details>
        <button className="btn btn-primary wp-save" disabled={busy}>
          {busy ? '儲存中…' : '儲存景點'}
        </button>
      </form>
    </>
  );
}

function clockMinute(clock: string) {
  return Number(clock.slice(0, 2)) * 60 + Number(clock.slice(3));
}
export function ItemForm({
  item,
  initialPlace,
  days,
  dayId,
  places,
  busy,
  save,
}: {
  item?: PlanItem;
  initialPlace?: Place;
  days: TripDay[];
  dayId: string;
  places: Place[];
  busy: boolean;
  save: SaveForm;
}) {
  const [title, setTitle] = useState(item?.title ?? initialPlace?.name ?? '');
  const [kind, setKind] = useState<Category>(item?.item_type ?? initialPlace?.category ?? 'custom');
  const [placeId, setPlaceId] = useState(item?.place_id ?? initialPlace?.id ?? '');
  const [day, setDay] = useState(dayId);
  const [zone, setZone] = useState(item?.timezone || '');
  const [start, setStart] = useState(item?.start_time ?? '');
  const [end, setEnd] = useState(item?.end_time ?? '');
  const [duration, setDuration] = useState(String(item?.duration ?? ''));
  const startMin = clockMinute(start);
  const endMin = end ? clockMinute(end) : startMin + (Number(duration) || 1);
  const overlapping =
    start &&
    days
      .find((d) => d.id === day)
      ?.items.some((other) => {
        if (!other.start_time || other.id === item?.id || (other.timezone || '') !== zone)
          return false;
        const otherStart = clockMinute(other.start_time);
        const otherEnd = other.end_time
          ? clockMinute(other.end_time)
          : otherStart + (other.duration || 1);
        return startMin < otherEnd && otherStart < endMin;
      });
  return (
    <form
      className="wp-form"
      onSubmit={(e) => {
        const v = valuesOf(e);
        void save({
          ...v,
          day_id: day,
          timezone: zone.trim() || null,
          place_id: placeId || null,
          start_time: start || null,
          end_time: end || null,
          duration: duration ? Number(duration) : null,
        });
      }}
    >
      {!item && (
        <label>
          日期
          <select value={day} onChange={(e) => setDay(e.target.value)}>
            {days.map((d) => (
              <option value={d.id} key={d.id}>
                Day {d.day_number}
                {d.date ? ` · ${d.date}` : ''}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        引用景點
        <select
          value={placeId}
          onChange={(e) => {
            setPlaceId(e.target.value);
            const place = places.find((p) => p.id === e.target.value);
            if (place) {
              setTitle(place.name);
              setKind(place.category);
            }
          }}
        >
          <option value="">自行填寫</option>
          {item?.archived_place && item.place_id === placeId && (
            <option value={placeId || ''}>{item.archived_place.name}（已移除）</option>
          )}
          {places
            .filter((p) => p.candidate || p.id === placeId)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
        </select>
      </label>
      <label>
        活動名稱
        <input
          name="title"
          required
          maxLength={150}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>
      <label>
        活動類型
        <select name="item_type" value={kind} onChange={(e) => setKind(e.target.value as Category)}>
          {options(categories)}
        </select>
      </label>
      <label>
        活動時區
        <input
          maxLength={64}
          value={zone}
          onChange={(e) => setZone(e.target.value)}
          placeholder={days.find((d) => d.id === day)?.timezone || 'Asia/Taipei'}
        />
        <small>遇到時鐘回撥時，重複的小時採第一次出現的時間。</small>
      </label>
      <div className="wp-form-pair">
        <label>
          開始時間
          <input
            type="time"
            required={!!end || !!duration}
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          結束時間
          <input
            type="time"
            disabled={!!duration}
            min={start || undefined}
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
      </div>
      <label>
        停留分鐘
        <input
          type="number"
          min="1"
          max="1440"
          disabled={!!end}
          value={duration}
          onChange={(e) => setDuration(e.target.value)}
        />
      </label>
      {overlapping && (
        <p className="wp-notice" role="status">
          與當日其他活動時間重疊，仍可儲存。
        </p>
      )}
      <label>
        備註
        <textarea name="notes" rows={3} maxLength={4000} defaultValue={item?.notes} />
      </label>
      <button className="btn btn-primary wp-save" disabled={busy || !day}>
        {busy ? '儲存中…' : '儲存活動'}
      </button>
    </form>
  );
}
