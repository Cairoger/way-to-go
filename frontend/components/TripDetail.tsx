'use client';
import { useState, useEffect, useCallback } from 'react';
import {
  CalendarDays,
  MapPinned,
  MapPin,
  Users,
  Settings2,
  Vote,
  MessageCircle,
  Archive,
  Trash2,
  ChevronLeft,
  ListChecks,
  Wifi,
  Navigation,
} from 'lucide-react';
import dynamic from 'next/dynamic';
import { api, ApiError } from '../lib/api';
import {
  type Trip,
  type User,
  type Member,
  coverFor,
  statusLabels,
  formatDates,
  errorText,
} from '../lib/trips';
import { samples } from '../lib/samples';
import { Button } from './ui/button';
import Members from './Members';
const Planner = dynamic(() => import('./Planner'), {
  ssr: false,
  loading: () => <p role="status">讀取行程中…</p>,
});
const Decisions = dynamic(() => import('./Decisions'), {
  ssr: false,
  loading: () => <p role="status">讀取討論中…</p>,
});
const tabs = [
  ['plan', '每日行程', CalendarDays],
  ['places', '候選景點', MapPin],
  ['map', '旅程地圖', MapPinned],
  ['polls', '投票', Vote],
  ['comments', '討論', MessageCircle],
  ['members', '旅伴', Users],
] as const;
type Section = (typeof tabs)[number][0];
type Props = {
  trip: Trip;
  user: User | null;
  sample: boolean;
  back: () => void;
  settings: () => void;
  update: (t: Trip) => void;
  setError: (s: string) => void;
  onExit: () => void;
};
export default function TripDetail({
  trip,
  user,
  sample,
  back,
  settings,
  update,
  setError,
  onExit,
}: Props) {
  const [section, setSection] = useState<Section>('plan'),
    [refresh, setRefresh] = useState(0),
    [members, setMembers] = useState<Member[]>([]),
    [online, setOnline] = useState<string[]>([]),
    [net, setNet] = useState('連線中'),
    [sampleDay, setSampleDay] = useState(0);
  const demo = sample ? samples.find((s) => s.trip.id === trip.id) : undefined;
  const changed = useCallback(() => setRefresh((n) => n + 1), []);
  const owner = user?.id === trip.owner_id;
  useEffect(() => {
    if (sample || !user) return;
    let live = true;
    Promise.all([api<Trip>('/trips/' + trip.id), api<Member[]>('/trips/' + trip.id + '/members')])
      .then(([t, m]) => {
        if (live) {
          update(t);
          setMembers(m);
        }
      })
      .catch((e) => {
        if (!live) return;
        setError(errorText(e));
        if (e instanceof ApiError && [401, 403, 404, 410].includes(e.status)) onExit();
      });
    return () => {
      live = false;
    };
  }, [trip.id, refresh, sample, user, update, setError, onExit]);
  useEffect(() => {
    if (sample || !user) return;
    let active = true,
      socket: WebSocket | undefined,
      timer: ReturnType<typeof setTimeout>,
      delay = 700;
    const connect = () => {
      if (!active) return;
      socket = new WebSocket(
        (location.protocol === 'https:' ? 'wss://' : 'ws://') +
          location.host +
          '/ws/trips/' +
          trip.id,
      );
      socket.onopen = () => {
        if (active) {
          delay = 700;
          setNet('即時同步');
          changed();
        }
      };
      socket.onmessage = (e) => {
        if (!active) return;
        try {
          const data = JSON.parse(e.data);
          if (data.type === 'presence') setOnline(data.members);
          else if (data.type !== 'heartbeat' && data.type !== 'pong') changed();
        } catch {}
      };
      socket.onclose = (e) => {
        if (!active) return;
        setOnline([]);
        if ([4401, 4403, 4404, 1008].includes(e.code)) {
          setError('此旅程的存取權已結束。');
          onExit();
          return;
        }
        setNet('重新連線中');
        timer = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 10000);
      };
    };
    connect();
    return () => {
      active = false;
      clearTimeout(timer);
      if (socket) {
        socket.onclose = null;
        socket.close();
      }
    };
  }, [trip.id, sample, user, changed, onExit, setError]);
  async function lifecycle(action: 'archive' | 'delete') {
    if (
      !window.confirm(
        action === 'archive'
          ? trip.archived
            ? '將旅程移回總覽？'
            : '將旅程移到已封存？'
          : '將旅程移到回收區？可於 30 天內復原。',
      )
    )
      return;
    try {
      if (action === 'archive')
        await api('/trips/' + trip.id + '/archive', 'POST', {
          archived: !trip.archived,
          version: trip.version,
        });
      else await api('/trips/' + trip.id + '?version=' + trip.version, 'DELETE');
      onExit();
    } catch (e) {
      setError(errorText(e));
    }
  }
  return (
    <>
      <div className="detail-top">
        <button className="text-btn" onClick={back}>
          <ChevronLeft size={17} />
          旅程總覽
        </button>
        {!sample && (
          <span className="sync">
            <Wifi size={14} />
            {net} · {online.length} 人在線
          </span>
        )}
      </div>
      <div
        className="detail-cover"
        style={{
          backgroundImage:
            'linear-gradient(90deg,rgba(16,41,33,.87),rgba(16,41,33,.35)),url(' +
            JSON.stringify(coverFor(trip)) +
            ')',
        }}
      >
        <div className="detail-label">
          {sample ? '示範旅程' : '我的旅程'}　/　{statusLabels[trip.status]}
        </div>
        <h1>{trip.title}</h1>
        <p>{trip.description}</p>
        <div className="detail-meta">
          <span>
            <MapPin />
            {trip.destinations.join(' · ') || '目的地待定'}
          </span>
          <span>
            <CalendarDays />
            {formatDates(trip.start_date, trip.end_date)}
          </span>
          <span>
            <Users />
            {trip.member_count} 位旅伴
          </span>
        </div>
      </div>
      {demo ? (
        <>
          <div className="detail-bar">
            <h2 className="section-title">
              <ListChecks />
              每日行程
            </h2>
            <span className="badge neutral">唯讀示範</span>
          </div>
          <div className="day-tabs">
            {demo.days.map((_, i) => (
              <button
                className={i === sampleDay ? 'on' : ''}
                key={i}
                onClick={() => setSampleDay(i)}
              >
                Day {i + 1}
              </button>
            ))}
          </div>
          <div className="card padded">
            <h3>{demo.days[sampleDay].title}</h3>
            {demo.days[sampleDay].stops.map(([time, title, note]) => (
              <article className="sample-stop" key={title}>
                <time>{time}</time>
                <div>
                  <b>{title}</b>
                  <p>{note}</p>
                </div>
                <a
                  aria-label={'在 Google 地圖查看' + title}
                  target="_blank"
                  rel="noreferrer"
                  href={
                    'https://www.google.com/maps/search/?api=1&query=' +
                    encodeURIComponent(title + ' ' + trip.destinations[0])
                  }
                >
                  <Navigation size={18} />
                </a>
              </article>
            ))}
          </div>
        </>
      ) : (
        user && (
          <>
            <nav aria-label="旅程功能" className="trip-tabs">
              {tabs.map(([id, label, Icon]) => (
                <button
                  key={id}
                  onClick={() => setSection(id)}
                  aria-current={section === id ? 'page' : undefined}
                >
                  <Icon size={16} />
                  {label}
                </button>
              ))}
            </nav>
            {(section === 'plan' || section === 'places' || section === 'map') && (
              <Planner
                tripId={trip.id}
                userId={user.id}
                section={section}
                refresh={refresh}
                onChange={changed}
                setError={setError}
                startDate={trip.start_date}
                currency={trip.currency}
              />
            )}
            {(section === 'polls' || section === 'comments') && (
              <Decisions
                tripId={trip.id}
                userId={user.id}
                isOwner={owner}
                section={section}
                refresh={refresh}
                onChange={changed}
                setError={setError}
              />
            )}
            {section === 'members' && (
              <Members
                trip={trip}
                userId={user.id}
                members={members}
                online={online}
                onChange={changed}
                onExit={onExit}
                setError={setError}
              />
            )}
            {owner && (
              <div className="lifecycle">
                <Button variant="ghost" onClick={settings}>
                  <Settings2 size={16} />
                  旅程設定
                </Button>
                <Button variant="ghost" onClick={() => lifecycle('archive')}>
                  <Archive size={16} />
                  {trip.archived ? '取消封存' : '封存旅程'}
                </Button>
                <Button variant="ghost" onClick={() => lifecycle('delete')}>
                  <Trash2 size={16} />
                  移到回收區
                </Button>
              </div>
            )}
          </>
        )
      )}
    </>
  );
}
