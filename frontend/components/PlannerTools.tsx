'use client';
import { useEffect, useState } from 'react';
import { CloudSun, History, Printer } from 'lucide-react';
import { api } from '../lib/api';
import { PlanningDialog } from './PlannerForms';
import { categories, type Lease, type Place, type TripDay } from './plannerTypes';

type Weather = {
  available: boolean;
  min?: number;
  max?: number;
  rain?: number;
  code?: number;
  place?: string;
};
function condition(code: number) {
  if (code === 0) return '晴朗';
  if (code <= 3) return '多雲';
  if (code <= 48) return '有霧';
  if (code <= 57) return '毛毛雨';
  if (code <= 67) return '有雨';
  if (code <= 77) return '降雪';
  if (code <= 82) return '陣雨';
  if (code <= 86) return '陣雪';
  return '雷雨';
}
export function DayWeather({ day, places }: { day: TripDay; places: Place[] }) {
  const [weather, setWeather] = useState<Weather | null>(null);
  const location = day.items
    .map((i) => places.find((p) => p.id === i.place_id))
    .find((p) => p?.latitude != null);
  const dependency = [
    day.id,
    day.date,
    day.timezone,
    location?.id,
    location?.latitude,
    location?.longitude,
  ].join('|');
  useEffect(() => {
    let live = true;
    setWeather(null);
    if (!location || !day.date) {
      setWeather({ available: false });
      return;
    }
    api<Weather>(`/days/${day.id}/weather`)
      .then((value) => {
        if (live) setWeather(value);
      })
      .catch(() => {
        if (live) setWeather({ available: false });
      });
    return () => {
      live = false;
    };
  }, [day.id, day.date, dependency, !!location]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="wp-weather">
      <CloudSun size={18} />
      {weather?.available ? (
        <>
          <span>
            {weather.place} · {condition(weather.code!)} · {weather.min}–{weather.max} °C · 降雨{' '}
            {weather.rain}%
          </span>
          <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">
            Open-Meteo
          </a>
        </>
      ) : (
        <span>{weather ? '尚無可用天氣預報' : '讀取天氣中…'}</span>
      )}
    </div>
  );
}

type Revision = {
  id: string;
  resource_id: string;
  kind: 'item' | 'place';
  title: string;
  version: number;
  current_version: number;
  editable: boolean;
  actor: string;
  at: string;
};
function RevisionList({
  tripId,
  refresh,
  changed,
}: {
  tripId: string;
  refresh: number;
  changed(): void;
}) {
  const [rows, setRows] = useState<Revision[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const [restored, setRestored] = useState('');
  useEffect(() => {
    let live = true;
    api<Revision[]>(`/trips/${tripId}/planner-history`)
      .then((value) => {
        if (live) {
          setRows(value);
          setLoaded(true);
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [tripId, refresh]);
  async function restore(row: Revision) {
    if (!window.confirm(`將「${row.title}」復原至版本 ${row.version}？這次復原也會寫入歷史。`))
      return;
    let token: Lease | undefined;
    setPending(true);
    setError('');
    setRestored('');
    try {
      token = await api<Lease>('/edit-leases', 'POST', {
        resource_type: row.kind,
        resource_id: row.resource_id,
      });
      await api(`/planner-history/${row.kind}/${row.resource_id}/restore`, 'POST', {
        lease_id: token.id,
        version: row.current_version,
        restore_version: row.version,
      });
      token = undefined;
      setRestored(`已復原「${row.title}」`);
      changed();
    } catch (e) {
      setError(e instanceof Error ? e.message : '復原失敗。');
    } finally {
      if (token) await api(`/edit-leases/${token.id}`, 'DELETE').catch(() => {});
      setPending(false);
    }
  }
  return (
    <>
      <p className="wp-hint">選擇變更前的版本，復原該筆景點或活動。</p>
      {error && (
        <p role="alert" className="wp-notice">
          {error}
        </p>
      )}
      {restored && <p role="status">{restored}</p>}
      {!loaded && !error && <p>讀取中…</p>}
      {loaded && !rows.length && <p>目前沒有可復原的修改。</p>}
      <ul className="wp-history">
        {rows.map((row) => (
          <li key={row.id}>
            <strong>
              {row.title} · 版本 {row.version}
            </strong>
            <small>
              {row.actor} 於 {new Date(row.at).toLocaleString('zh-TW')} 變更
            </small>
            {row.editable && (
              <button disabled={pending} className="wp-text" onClick={() => void restore(row)}>
                復原這個版本
              </button>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

export function printableDays(days: TripDay[], places: Place[], detailed: boolean) {
  return days.map((day) => ({
    heading: `Day ${day.day_number}${day.date ? ' · ' + day.date : ''}${day.title ? ' · ' + day.title : ''}`,
    timezone: day.timezone,
    rows: day.items.map((item) => {
      const place = places.find((p) => p.id === item.place_id);
      const clock =
        item.start_time || (item.suggested_time ? '建議 ' + item.suggested_time : '時間未定');
      return {
        heading: `${clock}${item.end_time ? '–' + item.end_time : ''}　${item.title}`,
        detail: detailed
          ? [
              categories[item.item_type],
              item.local_timezone || day.timezone,
              item.duration && item.duration + ' 分鐘',
              place?.address || item.archived_place?.address,
              item.clock_note,
            ]
              .filter(Boolean)
              .join(' · ')
          : '',
      };
    }),
  }));
}
function PrintForm({ days, places }: { days: TripDay[]; places: Place[] }) {
  const [selected, setSelected] = useState(() => new Set(days.map((d) => d.id)));
  const [detail, setDetail] = useState(true);
  const [error, setError] = useState('');
  function print() {
    const preview = window.open('', '_blank');
    if (!preview) {
      setError('請允許開啟列印視窗。');
      return;
    }
    // Only public itinerary fields are written, always as text nodes.
    preview.opener = null;
    const doc = preview.document;
    doc.documentElement.lang = 'zh-Hant';
    doc.title = '每日行程';
    const style = doc.createElement('style');
    style.textContent =
      '@page{size:A4;margin:18mm}body{font:14px/1.6 system-ui,sans-serif;color:#243a30;max-width:700px;margin:auto}section+section{break-before:page}h2{border-bottom:1px solid #a4b9aa}article{break-inside:avoid;margin:12px 0}small{display:block;color:#475b50}@media print{button{display:none}}';
    doc.head.append(style);
    const button = doc.createElement('button');
    button.textContent = '列印或儲存 PDF';
    button.onclick = () => preview.print();
    doc.body.append(button);
    for (const day of printableDays(
      days.filter((d) => selected.has(d.id)),
      places,
      detail,
    )) {
      const section = doc.createElement('section');
      const title = doc.createElement('h2');
      title.textContent = day.heading;
      section.append(title);
      const time = doc.createElement('p');
      time.textContent = day.timezone;
      section.append(time);
      for (const row of day.rows) {
        const entry = doc.createElement('article');
        entry.textContent = row.heading;
        if (row.detail) {
          const text = doc.createElement('small');
          text.textContent = row.detail;
          entry.append(text);
        }
        section.append(entry);
      }
      if (!day.rows.length) {
        const empty = doc.createElement('p');
        empty.textContent = '尚無安排';
        section.append(empty);
      }
      doc.body.append(section);
    }
    preview.focus();
    preview.print();
  }
  return (
    <div className="wp-form">
      <fieldset>
        <legend>匯出日期</legend>
        {days.map((d) => (
          <label key={d.id} className="wp-choice">
            <input
              type="checkbox"
              checked={selected.has(d.id)}
              onChange={(e) => {
                const next = new Set(selected);
                if (e.target.checked) next.add(d.id);
                else next.delete(d.id);
                setSelected(next);
              }}
            />
            Day {d.day_number}
            {d.date ? ' · ' + d.date : ''}
          </label>
        ))}
      </fieldset>
      <label>
        詳細程度
        <select
          value={detail ? 'details' : 'brief'}
          onChange={(e) => setDetail(e.target.value === 'details')}
        >
          <option value="brief">簡表（時間與活動）</option>
          <option value="details">詳細（含地址、時區與停留時間）</option>
        </select>
      </label>
      {error && <p role="alert">{error}</p>}
      <button className="btn btn-primary" disabled={!selected.size} onClick={print}>
        列印或儲存 PDF
      </button>
    </div>
  );
}

export function PlannerTools({
  tripId,
  days,
  places,
  refresh,
  onChange,
}: {
  tripId: string;
  days: TripDay[];
  places: Place[];
  refresh: number;
  onChange(): void;
}) {
  const [mode, setMode] = useState<'history' | 'print' | null>(null);
  return (
    <div className="wp-tools">
      <button className="wp-text" onClick={() => setMode('history')}>
        <History size={15} />
        版本復原
      </button>
      <button className="wp-text" onClick={() => setMode('print')}>
        <Printer size={15} />
        匯出行程 PDF
      </button>
      {mode && (
        <PlanningDialog
          title={mode === 'history' ? '版本復原' : '匯出每日行程'}
          close={() => setMode(null)}
        >
          {mode === 'history' ? (
            <RevisionList tripId={tripId} refresh={refresh} changed={onChange} />
          ) : (
            <PrintForm days={days} places={places} />
          )}
        </PlanningDialog>
      )}
    </div>
  );
}
