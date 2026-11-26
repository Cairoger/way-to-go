'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import * as Drawer from '@radix-ui/react-dialog';
import {
  Archive,
  BookOpen,
  CalendarDays,
  Check,
  ChevronRight,
  Compass,
  FolderOpen,
  Globe2,
  Grid2X2,
  HelpCircle,
  House,
  Layers3,
  Link2,
  List,
  LogIn,
  LogOut,
  Map,
  MapPin,
  Menu,
  MountainSnow,
  Plus,
  RotateCcw,
  Search,
  Ticket,
  Trash2,
  UserRound,
  Users,
  X,
} from 'lucide-react';
import { api, ApiError } from '../lib/api';
import { syncOfflineAccount } from '../lib/offlineTrips';
import {
  accountLabels,
  canCreateTrip,
  coverFor,
  errorText,
  formatDates,
  matchingTrips,
  statusLabels,
  type Trip,
  type User,
} from '../lib/trips';
import { samples } from '../lib/samples';
import TripForm from './TripForm';
import TripDetail from './TripDetail';
import NoticeCenter from './NoticeCenter';
import ProfileForm from './ProfileForm';
import AccessDialog from './AccessDialog';
import { Button } from './ui/button';
import { Modal } from './ui/dialog';

type Area = 'home' | 'archive' | 'trash' | 'examples';
type Route = { area: Area; trip: string; sample: boolean; section?: 'comments'; comment?: string };
type Dialog = 'login' | 'login-create' | 'join' | 'create' | 'settings' | 'help' | 'account' | null;
const mobileSidebarQuery = '(max-width: 880px)';
const initialRoute: Route = { area: 'home', trip: '', sample: false };
const areas = { home: '旅程總覽', archive: '已封存', trash: '回收區', examples: '示範旅程' };
const readRoute = (): Route => {
  const p = new URLSearchParams(location.search);
  const view = p.get('view') || 'home';
  return {
    area: Object.hasOwn(areas, view) ? (view as Area) : 'home',
    trip: p.get('example') || p.get('trip') || '',
    sample: p.has('example'),
    section: p.get('section') === 'comments' ? 'comments' : undefined,
    comment: location.hash.match(/^#comment-([a-f0-9-]{36})$/i)?.[1],
  };
};
const exampleTrips = samples.map((s) => s.trip);
function StatusBadge({ trip }: { trip: Trip }) {
  return (
    <span className={'badge badge-' + trip.status}>
      <i />
      {statusLabels[trip.status]}
    </span>
  );
}
function TripCard({
  trip,
  sample,
  restore,
  open,
  list,
}: {
  trip: Trip;
  sample: boolean;
  restore: () => void;
  open: () => void;
  list: boolean;
}) {
  const people = sample ? samples.find((s) => s.trip.id === trip.id)?.travellers : undefined;
  return (
    <article className={'trip-card' + (list ? ' list-card' : '')}>
      <button className="card-open" onClick={trip.deleted_at ? restore : open}>
        <div className="card-art">
          <img src={coverFor(trip)} alt="" loading="lazy" />
          <StatusBadge trip={trip} />
        </div>
        <div className="card-info">
          <div className="card-location">
            <MapPin size={14} />
            {trip.destinations.join(' · ') || '目的地待定'}
          </div>
          <h3>
            <span className="sr-only">{trip.deleted_at ? '復原' : '開啟'}</span>
            {trip.title}
          </h3>
          <div className="card-date">
            <CalendarDays size={15} />
            {formatDates(trip.start_date, trip.end_date)}
          </div>
        </div>
        <div className="card-foot">
          <div className="people">
            {people ? (
              <div className="avatars">
                {people.slice(0, 3).map((p, i) => (
                  <span key={p} className={'person p' + i}>
                    {p}
                  </span>
                ))}
              </div>
            ) : (
              <Users size={16} />
            )}
            <span>{trip.member_count} 位旅伴</span>
          </div>
          <span className="days">
            {trip.deleted_at ? (
              <>
                <RotateCcw size={14} />
                復原
              </>
            ) : (
              <>
                <Layers3 size={14} />
                {trip.day_count} 天
              </>
            )}
          </span>
        </div>
      </button>
    </article>
  );
}
export default function Workspace() {
  const [user, setUser] = useState<User | null>(),
    [trips, setTrips] = useState<Trip[]>([]),
    [route, setRoute] = useState<Route>(initialRoute),
    [dialog, setDialog] = useState<Dialog>(null),
    [invite, setInvite] = useState('');
  const [loading, setLoading] = useState(true),
    [loadError, setLoadError] = useState(''),
    [error, setError] = useState(''),
    [notice, setNotice] = useState(''),
    [sidebar, setSidebar] = useState(false),
    [filter, setFilter] = useState('all'),
    [query, setQuery] = useState(''),
    [view, setView] = useState<'grid' | 'list'>('grid'),
    [searchOpen, setSearchOpen] = useState(false);
  const [date, setDate] = useState('');
  const reloadId = useRef(0);
  const tripsOwner = useRef<string | null>(null);
  const menuTrigger = useRef<HTMLButtonElement>(null);
  const desktopSidebar = useRef<HTMLElement>(null);
  const dialogFromSidebar = useRef<Dialog>(null);
  const focusNavigation = useCallback(() => {
    const target = window.matchMedia(mobileSidebarQuery).matches
      ? menuTrigger.current
      : desktopSidebar.current?.querySelector('button');
    target?.focus();
  }, []);
  const reload = useCallback(async (onAccount?: (account: User) => void) => {
    const request = ++reloadId.current;
    let me: User | null = null;
    setLoadError('');
    setLoading(true);
    try {
      const account = await api<User>('/auth/me');
      me = account;
      if (request !== reloadId.current) return null;
      syncOfflineAccount(account.id);
      if (tripsOwner.current !== account.id) {
        setTrips([]);
        tripsOwner.current = account.id;
      }
      setUser((previous) =>
        previous?.id === account.id &&
        previous.account_type === account.account_type &&
        previous.nickname === account.nickname &&
        previous.version === account.version &&
        previous.email === account.email
          ? previous
          : account,
      );
      onAccount?.(account);
      const all = await api<Trip[]>('/trips');
      if (request !== reloadId.current) return null;
      syncOfflineAccount(account.id, all);
      setTrips(all);
      return me;
    } catch (e) {
      if (request !== reloadId.current) return null;
      if (e instanceof ApiError && e.status === 401) {
        syncOfflineAccount(null);
        tripsOwner.current = null;
        setUser(null);
        setTrips([]);
        return null;
      }
      if (!me) {
        tripsOwner.current = null;
        setUser(undefined);
        setTrips([]);
      }
      setLoadError((me ? '無法載入旅程清單。' : '無法確認登入狀態。') + errorText(e));
      return me;
    } finally {
      if (request === reloadId.current) setLoading(false);
    }
  }, []);
  const navigate = useCallback((r: Route) => {
    const p = new URLSearchParams();
    if (r.area !== 'home') p.set('view', r.area);
    if (r.trip) p.set(r.sample ? 'example' : 'trip', r.trip);
    if (r.trip && r.section) p.set('section', r.section);
    history.pushState(
      null,
      '',
      location.pathname + (p.size ? '?' + p : '') + (r.comment ? '#comment-' + r.comment : ''),
    );
    setRoute(r);
    setQuery('');
    setFilter('all');
    setSidebar(false);
    setSearchOpen(false);
    window.scrollTo({ top: 0 });
  }, []);
  const home = useCallback(() => navigate(initialRoute), [navigate]);
  const exitTrip = useCallback(() => {
    home();
    void reload();
  }, [home, reload]);
  const update = useCallback(
    (t: Trip) =>
      setTrips((list) =>
        list.some((x) => x.id === t.id) ? list.map((x) => (x.id === t.id ? t : x)) : [...list, t],
      ),
    [],
  );
  useEffect(() => {
    setDate(
      new Intl.DateTimeFormat('zh-TW', { month: 'long', day: 'numeric', weekday: 'long' }).format(
        new Date(),
      ),
    );
    setRoute(readRoute());
    const params = new URLSearchParams(location.search);
    const code = params.get('invite');
    if (code) {
      setInvite(code);
      setDialog('join');
    }
    if (params.has('error')) setError('登入未完成，請重新嘗試。');
    const pop = () => {
      setRoute(readRoute());
      setDialog(null);
      setSidebar(false);
    };
    window.addEventListener('popstate', pop);
    void reload();
    if (process.env.NODE_ENV === 'production' && 'serviceWorker' in navigator)
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    return () => window.removeEventListener('popstate', pop);
  }, [reload]);
  useEffect(() => {
    if (!canCreateTrip(user ?? null)) return;
    const params = new URLSearchParams(location.search);
    if (params.has('invite') || params.get('action') !== 'create') return;
    params.delete('action');
    history.replaceState(null, '', location.pathname + (params.size ? '?' + params : ''));
    setDialog('create');
  }, [user]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(''), 3500);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    if (!sidebar) return;
    const mobile = window.matchMedia(mobileSidebarQuery);
    const closeOnDesktop = () => {
      if (!mobile.matches) setSidebar(false);
    };
    closeOnDesktop();
    mobile.addEventListener('change', closeOnDesktop);
    return () => mobile.removeEventListener('change', closeOnDesktop);
  }, [sidebar]);
  useEffect(() => {
    if (!dialog && dialogFromSidebar.current) {
      dialogFromSidebar.current = null;
      focusNavigation();
    }
  }, [dialog, focusNavigation]);
  function openFromSidebar(next: Dialog) {
    if (sidebar) {
      // Restore focus to the mobile trigger before the next dialog records its opener.
      dialogFromSidebar.current = next;
      setSidebar(false);
    } else {
      setDialog(next);
    }
  }
  const showSamples = route.area === 'examples' || (!user && route.area === 'home');
  const records = showSamples ? exampleTrips : trips;
  const trip = (route.sample ? exampleTrips : trips).find((t) => t.id === route.trip);
  const goTrip = (t: Trip, isSample: boolean) =>
    navigate({ area: route.area, trip: t.id, sample: isSample });
  const switchArea = (area: Area) => navigate({ area, trip: '', sample: false });
  const featured =
    (!showSamples && trips.find((t) => !t.deleted_at && !t.archived && t.status !== 'completed')) ||
    samples[1].trip;
  const featuredSample = exampleTrips.includes(featured);
  const shape = matchingTrips(records, route.area, filter, query);
  const total = matchingTrips(records, route.area, 'all', '').length;
  const create = () => setDialog(canCreateTrip(user ?? null) ? 'create' : 'login-create');
  const openSavedTrip = (t: Trip) => {
    update(t);
    // A list request started before this save can still return its old snapshot.
    if (loading) void reload();
    navigate({ area: 'home', trip: t.id, sample: false });
  };
  const joined = (trip: Trip, joinedUserId: string) => {
    setDialog(null);
    setInvite('');
    void reload((account) => {
      if (account.id !== joinedUserId) return;
      update(trip);
      navigate({ area: 'home', trip: trip.id, sample: false });
      setNotice('已加入旅程。');
    });
  };
  const closeDialog = () => {
    setDialog(null);
    if (new URLSearchParams(location.search).has('invite'))
      history.replaceState(null, '', location.pathname);
  };
  const quickTrips = (
    user ? trips.filter((t) => !t.archived && !t.deleted_at) : exampleTrips
  ).slice(0, 3);
  async function restore(t: Trip) {
    try {
      const result = await api<Trip>('/trips/' + t.id + '/restore', 'POST', { version: t.version });
      update(result);
      setNotice('旅程已復原。');
    } catch (e) {
      setError(errorText(e));
    }
  }
  const navigation = (
    <>
      <button className="brand" onClick={home}>
        <img src="/compass.svg" width="42" height="42" alt="" />
        <span>
          <strong>
            WayToGo<span className="brand-dot">.</span>
          </strong>
          <small>旅伴手札</small>
        </span>
      </button>
      <nav aria-label="工作空間" className="side-nav">
        <div className="nav-heading">工作空間</div>
        {(
          [
            ['home', '旅程總覽', Map],
            ['archive', '已封存', Archive],
            ['trash', '回收區', Trash2],
          ] as const
        ).map(([id, label, Icon]) => (
          <button
            key={id}
            aria-current={route.area === id && !route.trip ? 'page' : undefined}
            onClick={() => switchArea(id)}
          >
            <Icon />
            {label}
          </button>
        ))}
        <div className="side-divider" />
        <div className="nav-heading">
          {user ? '快速前往' : '示範旅程'}
          <Compass size={13} />
        </div>
        {quickTrips.map((t, i) => (
          <button
            key={t.id}
            className={'quick-trip' + (route.trip === t.id ? ' selected' : '')}
            onClick={() => goTrip(t, !user)}
          >
            <span className={'destination-dot d' + i} />
            {t.title}
          </button>
        ))}
        {user && (
          <button onClick={() => switchArea('examples')}>
            <BookOpen />
            瀏覽示範
          </button>
        )}
      </nav>
      <div className="side-bottom">
        <div className="invite-slip">
          <Ticket className="slip-icon" size={26} />
          <b>收到旅伴邀請？</b>
          <button disabled={user === undefined} onClick={() => openFromSidebar('join')}>
            <Link2 size={15} />
            輸入邀請碼
          </button>
        </div>
        <button
          className="profile"
          disabled={user === undefined}
          onClick={() => openFromSidebar(user ? 'account' : 'login')}
        >
          <span className="profile-icon">
            <UserRound size={19} />
          </span>
          <span>
            <b>
              {user === undefined
                ? loading
                  ? '讀取帳號中…'
                  : '無法確認帳號'
                : (user?.nickname ?? '訪客模式')}
            </b>
            {user !== undefined && (
              <small>{user ? accountLabels[user.account_type] : '登入你的帳號'}</small>
            )}
          </span>
          <ChevronRight size={15} />
        </button>
      </div>
    </>
  );
  return (
    <div className="shell">
      <a className="skip-link" href="#main" tabIndex={0}>
        跳到主要內容
      </a>
      {!sidebar && (
        <aside ref={desktopSidebar} id="workspace-navigation" className="sidebar">
          {navigation}
        </aside>
      )}
      <div className="main-column">
        <header className="top-bar">
          <div className="breadcrumbs">
            <Drawer.Root open={sidebar} onOpenChange={setSidebar}>
              <Drawer.Trigger
                ref={menuTrigger}
                className="icon-button mobile-menu"
                aria-label="開啟選單"
                aria-controls="workspace-navigation"
              >
                <Menu />
              </Drawer.Trigger>
              <Drawer.Portal>
                <Drawer.Overlay className="mobile-shade" />
                <Drawer.Content
                  id="workspace-navigation"
                  className="sidebar opened"
                  aria-describedby={undefined}
                  onCloseAutoFocus={(event) => {
                    event.preventDefault();
                    focusNavigation();
                    if (dialogFromSidebar.current) setDialog(dialogFromSidebar.current);
                  }}
                >
                  <Drawer.Title className="sr-only">工作空間選單</Drawer.Title>
                  <Drawer.Close className="icon-button sidebar-close" aria-label="收合選單">
                    <X size={18} />
                  </Drawer.Close>
                  {navigation}
                </Drawer.Content>
              </Drawer.Portal>
            </Drawer.Root>
            <House size={16} />
            <span>工作空間</span>
            <ChevronRight size={13} />
            <b>{trip ? '旅程手札' : areas[route.area]}</b>
          </div>
          <div className="top-tools">
            {user && (
              <NoticeCenter
                key={user.id}
                openTrip={(id, comment) =>
                  navigate({ area: 'home', trip: id, sample: false, section: 'comments', comment })
                }
              />
            )}
            <span className="today">
              <CalendarDays size={15} />
              {date}
            </span>
            <button className="icon-button" onClick={() => setDialog('help')} aria-label="使用說明">
              <HelpCircle size={19} />
            </button>
          </div>
        </header>
        <main id="main" className="main-content">
          {loadError && (
            <div className="error-banner" role="alert">
              <span>{loadError}</span>
              <button onClick={() => void reload()}>重新載入</button>
            </div>
          )}
          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              <button onClick={() => setError('')} aria-label="關閉錯誤訊息">
                <X size={16} />
              </button>
            </div>
          )}
          {route.trip && trip ? (
            <TripDetail
              key={trip.id + (route.section ?? '') + (route.comment ?? '')}
              initialSection={route.section}
              onCopy={(t) => {
                openSavedTrip(t);
                setNotice('已複製旅程與每日行程。');
              }}
              trip={trip}
              user={user ?? null}
              sample={route.sample}
              back={home}
              onExit={exitTrip}
              settings={() => setDialog('settings')}
              update={update}
              setError={setError}
            />
          ) : route.trip ? (
            <div className="empty">
              <Compass />
              <h2>{loading ? '讀取旅程中…' : '無法開啟此旅程'}</h2>
              {!loading && (
                <>
                  <p>請確認帳號或使用有效邀請加入。</p>
                  <Button onClick={home}>返回總覽</Button>
                </>
              )}
            </div>
          ) : (
            <>
              <div className="page-intro">
                <div>
                  <h1>{areas[route.area]}</h1>
                  <p>
                    {route.area === 'archive'
                      ? '已收起的旅程手札，可隨時移回總覽。'
                      : route.area === 'trash'
                        ? '刪除後 30 天內，旅程擁有者可在此復原。'
                        : route.area === 'examples'
                          ? '打開示範手札，看看多日行程如何安排。'
                          : '和旅伴一起，規劃每一趟值得期待的旅行。'}
                  </p>
                </div>
                <Button disabled={user === undefined} onClick={create}>
                  <Plus size={18} />
                  建立旅程
                </Button>
              </div>
              {route.area === 'home' && (
                <section className="hero">
                  <div className="hero-art" aria-hidden="true" />
                  <div className="hero-copy">
                    <div className="hero-tag">
                      <Compass size={14} />
                      {featuredSample ? '精選示範旅程' : '旅程焦點'}
                    </div>
                    <h2>{featured.title}</h2>
                    <div className="hero-meta">
                      <span>
                        <MapPin />
                        {featured.destinations.join(' · ') || '目的地待定'}
                      </span>
                      <i />
                      <span>
                        <CalendarDays />
                        {featured.day_count} 天行程
                      </span>
                    </div>
                    <button onClick={() => goTrip(featured, featuredSample)}>
                      <BookOpen size={15} />
                      翻開旅程手札
                    </button>
                  </div>
                  <div className="hero-caption">
                    <MountainSnow size={14} />
                    {featuredSample ? 'DOLOMITI, ITALIA' : 'WAYTOGO'}
                  </div>
                </section>
              )}
              <section className="trips-section">
                <div className="section-heading">
                  <h2>
                    {showSamples
                      ? '示範旅程'
                      : route.area === 'home'
                        ? '我的旅程'
                        : areas[route.area]}
                    <span className="count">{total}</span>
                  </h2>
                  <div className="view-tools">
                    <button
                      className={'icon-button' + (searchOpen ? ' on' : '')}
                      aria-label="搜尋旅程"
                      aria-expanded={searchOpen}
                      onClick={() => {
                        setSearchOpen(!searchOpen);
                        setQuery('');
                      }}
                    >
                      <Search size={18} />
                    </button>
                    <div className="view-toggle">
                      <button
                        aria-label="卡片檢視"
                        aria-pressed={view === 'grid'}
                        onClick={() => setView('grid')}
                      >
                        <Grid2X2 size={16} />
                      </button>
                      <button
                        aria-label="清單檢視"
                        aria-pressed={view === 'list'}
                        onClick={() => setView('list')}
                      >
                        <List size={18} />
                      </button>
                    </div>
                  </div>
                </div>
                {searchOpen && (
                  <label className="search-field">
                    <Search size={17} />
                    <input
                      autoFocus
                      type="search"
                      placeholder="搜尋旅程或目的地"
                      aria-label="搜尋旅程或目的地"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                )}
                <div className="filters" role="group" aria-label="篩選旅程">
                  {[['all', '全部'], ...Object.entries(statusLabels)].map(([id, label]) => (
                    <button aria-pressed={filter === id} key={id} onClick={() => setFilter(id)}>
                      {label}
                    </button>
                  ))}
                </div>
                {shape.length ? (
                  <div className={'trip-grid' + (view === 'list' ? ' as-list' : '')}>
                    {shape.map((t) => (
                      <TripCard
                        key={t.id}
                        trip={t}
                        sample={showSamples}
                        list={view === 'list'}
                        open={() => goTrip(t, showSamples)}
                        restore={() => restore(t)}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="empty">
                    <FolderOpen size={31} />
                    <h3>
                      {query || filter !== 'all'
                        ? '沒有符合條件的旅程'
                        : route.area === 'home'
                          ? '開始你的第一趟旅程'
                          : '這裡還沒有旅程'}
                    </h3>
                    {route.area === 'home' && !query && filter === 'all' && (
                      <Button
                        variant="outline"
                        disabled={user === undefined}
                        onClick={() => setDialog('join')}
                      >
                        用邀請碼加入
                      </Button>
                    )}
                    {(query || filter !== 'all') && (
                      <button
                        className="text-btn"
                        onClick={() => {
                          setQuery('');
                          setFilter('all');
                        }}
                      >
                        清除篩選
                      </button>
                    )}
                  </div>
                )}
              </section>
            </>
          )}
        </main>
        <footer className="main-footer">
          <span>
            <Compass size={14} />
            WayToGo 旅伴手札
          </span>
          <span>
            <Globe2 size={13} />
            繁體中文
          </span>
        </footer>
      </div>
      {notice && (
        <div role="status" className="toast">
          <Check size={16} />
          {notice}
        </div>
      )}
      {user !== undefined &&
        (dialog === 'login' || dialog === 'login-create' || dialog === 'join') && (
          <AccessDialog
            key={dialog}
            mode={dialog === 'join' ? 'join' : 'login'}
            user={user}
            invite={invite}
            onClose={closeDialog}
            onJoined={joined}
            onJoin={() => setDialog('join')}
            createAfterLogin={dialog === 'login-create'}
            onSignedIn={async (account) => {
              setUser(account);
              setTrips([]);
              setError('');
              setDialog(null);
              home();
              if (await reload()) {
                setNotice('已登入測試帳號。');
                if (dialog === 'login-create') setDialog('create');
              }
            }}
          />
        )}
      {(dialog === 'create' || dialog === 'settings') && (
        <TripForm
          trip={dialog === 'settings' ? trip : undefined}
          onClose={closeDialog}
          onSaved={(t) => {
            openSavedTrip(t);
            setDialog(null);
            setNotice('旅程已儲存。');
          }}
        />
      )}
      {dialog === 'help' && (
        <Modal title="旅伴手札使用說明" onClose={closeDialog}>
          <div className="help-list">
            <p>
              <b>建立旅程</b>登入帳號後，輸入旅程名稱就能開始。日期可以稍後決定。
            </p>
            <p>
              <b>邀請旅伴</b>擁有者可在旅程的「旅伴」分頁產生邀請碼、連結和 QR
              Code。訪客輸入暱稱即可加入。
            </p>
            <p>
              <b>一起規劃</b>收集景點、安排每日行程，或發起投票。其他在線旅伴會同步看到最新進度。
            </p>
          </div>
        </Modal>
      )}
      {dialog === 'account' && user && (
        <Modal title="帳號" onClose={closeDialog}>
          <div className="stack">
            <p>{user.email || accountLabels[user.account_type]}</p>
            <ProfileForm key={user.id} user={user} onSaved={setUser} />
            {user.account_type === 'guest' && (
              <Button onClick={() => setDialog('login')}>
                <LogIn size={16} />
                使用 Google 登入
              </Button>
            )}
            <Button
              variant="outline"
              onClick={async () => {
                if (
                  user.account_type === 'guest' &&
                  !window.confirm('登出後可能無法恢復這個訪客身分，確定登出？')
                )
                  return;
                try {
                  await api('/auth/logout', 'POST', {});
                  syncOfflineAccount(null);
                  ++reloadId.current;
                  tripsOwner.current = null;
                  setLoading(false);
                  setLoadError('');
                  setTrips([]);
                  setUser(null);
                  setDialog(null);
                  home();
                } catch (e) {
                  setError(errorText(e));
                }
              }}
            >
              <LogOut size={16} />
              登出
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
