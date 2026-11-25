'use client';
import { useState, type FormEvent } from 'react';
import { BedDouble, ExternalLink, LockKeyhole, MapPin, Plane, Plus } from 'lucide-react';
import { api } from '../lib/api';
import { errorText, type Member } from '../lib/trips';
import { Button } from './ui/button';
import { AttachmentButton } from './Attachments';
import { Modal } from './ui/dialog';
import { ItemOptions, type DayRef, type PrepProps } from './preparationTypes';
type Passenger = { user_id: string; seat?: string; baggage?: string };
type Leg = {
  airline: string;
  number: string;
  origin: string;
  destination: string;
  departure: string;
  arrival: string;
  departure_terminal: string;
  arrival_terminal: string;
  passengers: Passenger[];
};
type Stay = {
  address: string;
  room: string;
  check_in: string;
  check_out: string;
  guests: string[];
};
export type Booking = {
  id: string;
  kind: 'flight' | 'stay';
  title: string;
  status: 'planned' | 'booked' | 'cancelled';
  price: string | null;
  currency: string;
  website: string;
  reference?: string;
  segments: Leg[];
  stay: Stay | null;
  item_id: string | null;
  created_by: string;
  can_edit_public?: boolean;
  version: number;
};
const statuses = { planned: '規劃中', booked: '已預訂', cancelled: '已取消' };
function offset() {
  const minutes = -new Date().getTimezoneOffset();
  return (
    (minutes < 0 ? '-' : '+') +
    String(Math.floor(Math.abs(minutes) / 60)).padStart(2, '0') +
    ':' +
    String(Math.abs(minutes) % 60).padStart(2, '0')
  );
}
function emptyLeg(): Leg {
  return {
    airline: '',
    number: '',
    origin: '',
    destination: '',
    departure: '',
    arrival: '',
    departure_terminal: '',
    arrival_terminal: '',
    passengers: [],
  };
}
function Timestamp({
  title,
  value,
  change,
}: {
  title: string;
  value: string;
  change: (value: string) => void;
}) {
  const suffix = value.match(/(Z|[+-]\d\d:\d\d)$/)?.[1] || offset();
  const zone = suffix === 'Z' ? '+00:00' : suffix;
  const [tz, setTz] = useState(zone);
  return (
    <div className="form-row">
      <label className="field">
        {title}（當地時間）
        <input
          type="datetime-local"
          required
          value={value.slice(0, 16)}
          onChange={(e) => change(e.target.value ? e.target.value + tz : '')}
        />
      </label>
      <label className="field">
        UTC 時差
        <input
          value={tz}
          required
          pattern={'(\\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00)'}
          placeholder="+08:00"
          onChange={(e) => {
            setTz(e.target.value);
            if (value) change(value.slice(0, 16) + e.target.value);
          }}
        />
      </label>
    </div>
  );
}
function LegFields({
  leg,
  change,
  members,
  index,
  remove,
  publicOnly,
}: {
  leg: Leg;
  change: (leg: Leg) => void;
  members: Member[];
  index: number;
  remove?: () => void;
  publicOnly: boolean;
}) {
  function field(key: keyof Omit<Leg, 'passengers'>, label: string, required = false) {
    return (
      <label className="field">
        {label}
        <input
          required={required}
          value={leg[key]}
          maxLength={100}
          onChange={(e) => change({ ...leg, [key]: e.target.value })}
        />
      </label>
    );
  }
  return (
    <fieldset className="prep-segment">
      <legend>航段 {index + 1}</legend>
      <div className="stack">
        <div className="form-row">
          {field('airline', '航空公司')}
          {field('number', '航班編號', true)}
        </div>
        <div className="form-row">
          {field('origin', '出發機場', true)}
          {field('destination', '抵達機場', true)}
        </div>
        <div className="form-row">
          {field('departure_terminal', '出發航廈')}
          {field('arrival_terminal', '抵達航廈')}
        </div>
        <Timestamp
          title="起飛"
          value={leg.departure}
          change={(departure) => change({ ...leg, departure })}
        />
        <Timestamp
          title="抵達"
          value={leg.arrival}
          change={(arrival) => change({ ...leg, arrival })}
        />
        {!publicOnly && (
          <fieldset>
            <legend>此航段的旅客</legend>
            {members.map((m) => {
              const p = leg.passengers.find((p) => p.user_id === m.id);
              return (
                <div key={m.id} className="prep-passenger">
                  <label>
                    <input
                      type="checkbox"
                      checked={!!p}
                      onChange={(e) =>
                        change({
                          ...leg,
                          passengers: e.target.checked
                            ? [...leg.passengers, { user_id: m.id, seat: '', baggage: '' }]
                            : leg.passengers.filter((p) => p.user_id !== m.id),
                        })
                      }
                    />
                    {m.nickname}
                  </label>
                  {p && (
                    <div className="form-row">
                      {(['seat', 'baggage'] as const).map((k) => (
                        <label key={k} className="field">
                          {k === 'seat' ? '座位' : '行李'}
                          <input
                            value={p[k] ?? ''}
                            onChange={(e) =>
                              change({
                                ...leg,
                                passengers: leg.passengers.map((person) =>
                                  person.user_id === m.id
                                    ? { ...person, [k]: e.target.value }
                                    : person,
                                ),
                              })
                            }
                          />
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </fieldset>
        )}
        {remove && (
          <Button variant="ghost" onClick={remove}>
            移除此航段
          </Button>
        )}
      </div>
    </fieldset>
  );
}
function BookingEditor({
  initial,
  days,
  close,
  save,
  kind,
  members,
  currency,
}: {
  initial?: Booking;
  days: DayRef[];
  close: () => void;
  save: (payload: unknown) => Promise<void>;
  kind: Booking['kind'];
  members: Member[];
  currency: string;
}) {
  const [legs, setLegs] = useState(
      (initial?.segments.length ? initial.segments : [emptyLeg()]).map((leg, index) => ({
        leg,
        key: index,
      })),
    ),
    [seq, setSeq] = useState(legs.length);
  const [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const publicOnly = initial?.can_edit_public === true;
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const str = (key: string) => String(f.get(key) || '');
    setBusy(true);
    setError('');
    try {
      await save({
        kind,
        title: str('title'),
        status: str('status'),
        currency: str('currency').toUpperCase(),
        price: str('price') || null,
        ...(publicOnly ? {} : { reference: str('reference') }),
        website: str('website'),
        item_id: str('item_id') || null,
        segments:
          kind === 'flight'
            ? legs.map(({ leg }) =>
                publicOnly
                  ? Object.fromEntries(
                      Object.entries(leg).filter(([field]) => field !== 'passengers'),
                    )
                  : leg,
              )
            : [],
        stay:
          kind === 'stay'
            ? {
                address: str('address'),
                room: str('room'),
                check_in: str('check_in'),
                check_out: str('check_out'),
                ...(publicOnly ? {} : { guests: f.getAll('guests') }),
              }
            : null,
        ...(initial ? { version: initial.version } : {}),
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
      title={(initial ? '編輯' : '新增') + (kind === 'flight' ? '航班' : '住宿')}
      onClose={close}
    >
      <form className="stack" onSubmit={submit}>
        {publicOnly && (
          <p className="muted">預訂建立者已退出旅程，你可以維護這筆預訂的公開資料。</p>
        )}
        <label className="field">
          {kind === 'stay' ? '住宿名稱' : '航班預訂名稱'}
          <input name="title" required maxLength={160} defaultValue={initial?.title} autoFocus />
        </label>
        <label className="field">
          預訂狀態
          <select name="status" defaultValue={initial?.status ?? 'planned'}>
            {Object.entries(statuses).map(([k, v]) => (
              <option value={k} key={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        {kind === 'flight' ? (
          <>
            {legs.map(({ leg, key }, i) => (
              <LegFields
                key={key}
                index={i}
                leg={leg}
                members={members}
                publicOnly={publicOnly}
                change={(v) =>
                  setLegs((rows) => rows.map((r) => (r.key === key ? { key, leg: v } : r)))
                }
                remove={
                  !publicOnly && legs.length > 1
                    ? () => setLegs((rows) => rows.filter((r) => r.key !== key))
                    : undefined
                }
              />
            ))}
            {!publicOnly && (
              <Button
                variant="outline"
                onClick={() => {
                  setLegs((rows) => [...rows, { key: seq, leg: emptyLeg() }]);
                  setSeq((n) => n + 1);
                }}
              >
                新增航段
              </Button>
            )}
          </>
        ) : (
          <>
            <div className="form-row">
              <label className="field">
                入住日期
                <input
                  name="check_in"
                  type="date"
                  required
                  defaultValue={initial?.stay?.check_in}
                />
              </label>
              <label className="field">
                退房日期
                <input
                  name="check_out"
                  type="date"
                  required
                  defaultValue={initial?.stay?.check_out}
                />
              </label>
            </div>
            <label className="field">
              住宿地址
              <input name="address" defaultValue={initial?.stay?.address} />
            </label>
            <label className="field">
              房型
              <input name="room" defaultValue={initial?.stay?.room} />
            </label>
            {!publicOnly && (
              <fieldset>
                <legend>住客</legend>
                <div className="prep-choices">
                  {members.map((m) => (
                    <label key={m.id}>
                      <input
                        type="checkbox"
                        name="guests"
                        value={m.id}
                        defaultChecked={initial?.stay?.guests.includes(m.id)}
                      />
                      {m.nickname}
                    </label>
                  ))}
                  {initial?.stay?.guests
                    .filter((id) => !members.some((m) => m.id === id))
                    .map((id) => (
                      <label key={id}>
                        <input type="checkbox" name="guests" value={id} defaultChecked />
                        已退出的住客
                      </label>
                    ))}
                </div>
              </fieldset>
            )}
          </>
        )}
        <div className="form-row">
          <label className="field">
            價格
            <input
              name="price"
              min="0"
              step="0.0001"
              type="number"
              defaultValue={initial?.price ?? ''}
            />
          </label>
          <label className="field">
            幣別
            <input
              name="currency"
              required
              pattern="[a-zA-Z]{3}"
              maxLength={3}
              defaultValue={initial?.currency ?? currency}
            />
          </label>
        </div>
        {!publicOnly && (
          <label className="field">
            訂位代號
            <input
              name="reference"
              autoComplete="off"
              maxLength={100}
              defaultValue={initial?.reference}
            />
            <small>只有建立者與這筆預訂的旅客可查看。</small>
          </label>
        )}
        <label className="field">
          官方或航班資訊網址
          <input type="url" name="website" placeholder="https://" defaultValue={initial?.website} />
        </label>
        <label className="field">
          關聯行程活動
          <select name="item_id" defaultValue={initial?.item_id ?? ''}>
            <ItemOptions days={days} linkedId={initial?.item_id} />
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
            儲存預訂
          </Button>
        </div>
      </form>
    </Modal>
  );
}
export default function Bookings({
  trip,
  userId,
  members,
  rows,
  days,
  onChange,
  setError,
}: PrepProps & { rows: Booking[]; days: DayRef[] }) {
  const [kind, setKind] = useState<Booking['kind']>('flight'),
    [editing, setEditing] = useState<Booking | 'new' | null>(null);
  const base = '/trips/' + trip.id + '/bookings';
  const visible = rows.filter((r) => r.kind === kind);
  const name = (id: string) => members.find((m) => m.id === id)?.nickname || '已退出的旅伴';
  return (
    <section className="prep-root">
      <div className="prep-heading">
        <h2>{kind === 'flight' ? <Plane /> : <BedDouble />}交通與住宿</h2>
        <Button onClick={() => setEditing('new')}>
          <Plus size={16} />
          新增{kind === 'flight' ? '航班' : '住宿'}
        </Button>
      </div>
      <div className="day-tabs">
        <button className={kind === 'flight' ? 'on' : ''} onClick={() => setKind('flight')}>
          航班
        </button>
        <button className={kind === 'stay' ? 'on' : ''} onClick={() => setKind('stay')}>
          住宿
        </button>
      </div>
      {!visible.length && (
        <div className="empty">
          {kind === 'flight' ? <Plane /> : <BedDouble />}
          <h3>還沒有{kind === 'flight' ? '航班' : '住宿'}紀錄</h3>
        </div>
      )}
      <div className="prep-list">
        {visible.map((b) => (
          <article key={b.id} className="card prep-card">
            <div className="prep-line">
              <h3>{b.title}</h3>
              <span className="badge neutral">{statuses[b.status]}</span>
            </div>
            {b.segments.map((s, i) => (
              <div className="prep-leg" key={i}>
                <b>
                  {s.airline} {s.number} · {s.origin} 至 {s.destination}
                </b>
                <p>
                  起飛 {s.departure.replace('T', ' ')} {s.departure_terminal}
                </p>
                <p>
                  抵達 {s.arrival.replace('T', ' ')} {s.arrival_terminal}
                </p>
                {s.passengers.length > 0 && (
                  <small>
                    {s.passengers
                      .map((p) => [name(p.user_id), p.seat, p.baggage].filter(Boolean).join(' / '))
                      .join('、')}
                  </small>
                )}
              </div>
            ))}
            {b.stay && (
              <div className="prep-leg">
                <b>
                  {b.stay.check_in} 至 {b.stay.check_out}
                </b>
                <p>
                  {b.stay.room} {b.stay.guests.map(name).join('、')}
                </p>
                {b.stay.address && (
                  <a
                    href={
                      'https://www.google.com/maps/dir/?api=1&destination=' +
                      encodeURIComponent(b.stay.address)
                    }
                    target="_blank"
                    rel="noreferrer"
                  >
                    <MapPin size={14} />
                    {b.stay.address}
                  </a>
                )}
              </div>
            )}
            <div className="prep-meta">
              {b.reference !== undefined && (
                <AttachmentButton tripId={trip.id} kind="booking" targetId={b.id} />
              )}
              {b.price !== null && (
                <span>
                  {b.currency}{' '}
                  {b.price.includes('.') ? b.price.replace(/0+$/, '').replace(/\.$/, '') : b.price}
                </span>
              )}
              {b.reference && (
                <span>
                  <LockKeyhole size={14} />
                  訂位代號 {b.reference}
                </span>
              )}
              {b.website && (
                <a href={b.website} target="_blank" rel="noreferrer">
                  <ExternalLink size={14} />
                  外部預訂資訊
                </a>
              )}
              {days.flatMap((d) =>
                d.items
                  .filter((i) => i.id === b.item_id)
                  .map((i) => (
                    <span key={i.id}>
                      Day {d.day_number} · {i.title}
                    </span>
                  )),
              )}
            </div>
            {b.created_by === userId && (
              <div className="prep-buttons">
                <button onClick={() => setEditing(b)}>編輯</button>
                <button
                  onClick={async () => {
                    if (!confirm('確定刪除這筆預訂紀錄？')) return;
                    try {
                      await api(base + '/' + b.id, 'DELETE', { version: b.version });
                      onChange();
                    } catch (e) {
                      setError(errorText(e));
                    }
                  }}
                >
                  刪除
                </button>
              </div>
            )}
            {b.can_edit_public && (
              <div className="prep-buttons">
                <button onClick={() => setEditing(b)}>編輯公開資料</button>
              </div>
            )}
          </article>
        ))}
      </div>
      {editing && (
        <BookingEditor
          initial={editing === 'new' ? undefined : editing}
          kind={kind}
          days={days}
          currency={trip.currency}
          members={members}
          close={() => setEditing(null)}
          save={async (p) => {
            await api(
              editing === 'new'
                ? base
                : base + '/' + editing.id + (editing.can_edit_public ? '/public' : ''),
              editing === 'new' ? 'POST' : 'PUT',
              p,
            );
            onChange();
          }}
        />
      )}
    </section>
  );
}
