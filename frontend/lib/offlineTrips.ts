import type { Place, TripDay } from '../components/plannerTypes';
import { api } from './api';
import { formatDates, type Trip } from './trips';

// Only the explicitly selected fields below are available to the offline reader.
// Keep these keys in sync with public/offline-reader.js.
const identity = 'waytogo.offline.account';
const prefix = 'waytogo.offline.trip.';

export function syncOfflineAccount(userId: string | null, trips?: Trip[]) {
  try {
    const allowed = trips && new Set(trips.filter((t) => !t.deleted_at).map((t) => t.id));
    const changed = localStorage.getItem(identity) !== userId;
    // Another tab can log out or switch identities while the trip list is in flight.
    if (trips && changed) return;
    if (!userId || changed) localStorage.removeItem(identity);
    for (const key of Object.keys(localStorage)) {
      if (
        key.startsWith(prefix) &&
        (!userId || changed || (allowed && !allowed.has(key.slice(prefix.length))))
      )
        localStorage.removeItem(key);
    }
    if (userId && changed) localStorage.setItem(identity, userId);
  } catch {
    // Browsers that deny local storage still support the online workspace.
  }
}

export function forgetOfflineTrip(tripId: string) {
  try {
    localStorage.removeItem(prefix + tripId);
  } catch {}
}

export function offlineSavedAt(userId: string, tripId: string): string | null {
  try {
    if (localStorage.getItem(identity) !== userId) return null;
    const record = JSON.parse(localStorage.getItem(prefix + tripId) || 'null');
    return record?.owner === userId ? record.savedAt : null;
  } catch {
    return null;
  }
}

export async function saveOfflineTrip(userId: string, tripId: string) {
  if (!('serviceWorker' in navigator)) throw new Error('此瀏覽器無法儲存離線旅程。');
  const registration = await navigator.serviceWorker.register('/sw.js');
  // On upgrade the old worker can already be active. Wait for the new reader shell.
  const installing = registration.installing || registration.waiting;
  if (installing && installing.state !== 'activated') {
    await new Promise<void>((resolve, reject) => {
      const check = () => {
        if (installing.state === 'activated' || installing.state === 'redundant') {
          installing.removeEventListener('statechange', check);
          if (installing.state === 'activated') resolve();
          else reject(new Error('離線閱讀器未能安裝，請重新儲存。'));
        }
      };
      installing.addEventListener('statechange', check);
      check();
    });
  }
  if (!registration.active) throw new Error('離線閱讀器尚未啟用，請重新儲存。');
  const base = '/trips/' + tripId;
  const [account, trip, days, places] = await Promise.all([
    api<{ id: string }>('/auth/me'),
    api<Trip>(base),
    api<TripDay[]>(base + '/days'),
    api<Place[]>(base + '/places'),
  ]);
  if (account.id !== userId || localStorage.getItem(identity) !== userId)
    throw new Error('帳號已切換，請重新開啟旅程。');
  const locations = new Map(places.map((p) => [p.id, p]));
  const record = {
    owner: userId,
    savedAt: new Date().toISOString(),
    title: trip.title,
    destinations: trip.destinations.join('、'),
    dates: formatDates(trip.start_date, trip.end_date),
    days: days.map((d) => ({
      heading: ['第 ' + d.day_number + ' 天', d.title, d.date, d.timezone]
        .filter(Boolean)
        .join(' · '),
      items: d.items.map((i) => {
        const place = locations.get(i.place_id || '') || i.archived_place;
        return {
          title: i.title,
          time: [
            i.start_time || (i.suggested_time && '建議 ' + i.suggested_time) || '時間未定',
            i.end_time,
          ]
            .filter(Boolean)
            .join('–'),
          zone: i.local_timezone || d.timezone,
          clockNote: i.clock_note,
          place: place?.name,
          address: place?.address,
        };
      }),
    })),
    places: places.filter((p) => p.candidate).map((p) => ({ name: p.name, address: p.address })),
  };
  localStorage.setItem(prefix + tripId, JSON.stringify(record));
  return record.savedAt;
}
