export type Status = 'planning' | 'confirmed' | 'traveling' | 'completed';
export type User = {
  id: string;
  nickname: string;
  email?: string | null;
  account_type: 'google' | 'guest' | 'local_test';
};
export type Member = User & { role: 'owner' | 'member' };
export const accountLabels: Record<User['account_type'], string> = {
  google: 'Google 帳號',
  guest: '訪客帳號',
  local_test: '本機測試帳號',
};
export function canCreateTrip(user: User | null) {
  return user?.account_type === 'google' || user?.account_type === 'local_test';
}
export type Trip = {
  id: string;
  title: string;
  destinations: string[];
  description: string;
  start_date: string | null;
  end_date: string | null;
  currency: string;
  status: Status;
  cover: string | null;
  archived: boolean;
  deleted_at: string | null;
  version: number;
  owner_id: string;
  created_by?: string;
  creator_name?: string;
  member_count: number;
  day_count: number;
  place_count: number;
  created_at: string;
};
export const statusLabels: Record<Status, string> = {
  planning: '規劃中',
  confirmed: '已確認',
  traveling: '旅遊中',
  completed: '已完成',
};
export const covers = [
  { id: 'kyoto', name: '京都夕照', path: '/art/kyoto.webp' },
  { id: 'alps', name: '山間湖畔', path: '/art/alps.webp' },
  { id: 'tainan', name: '南國街景', path: '/art/tainan.webp' },
  { id: 'valley', name: '山谷小徑', path: '/art/valley.webp' },
];
export function coverFor(trip: Trip) {
  const custom = covers.find((c) => c.id === trip.cover || c.path === trip.cover);
  if (custom) return custom.path;
  if (trip.cover?.startsWith('https://')) return trip.cover;
  return covers[trip.id.charCodeAt(0) % covers.length].path;
}
export function formatDates(start: string | null, end: string | null) {
  if (!start) return '日期待定';
  const label = start.replaceAll('-', '.');
  if (!end || end === start) return label;
  return (
    label +
    ' – ' +
    (end.slice(0, 4) === start.slice(0, 4) ? end.slice(5) : end).replaceAll('-', '.')
  );
}
export function matchingTrips(trips: Trip[], area: string, filter: string, query: string) {
  const needle = query.trim().toLocaleLowerCase();
  return trips.filter(
    (t) =>
      (area === 'trash' ? !!t.deleted_at : !t.deleted_at && t.archived === (area === 'archive')) &&
      (filter === 'all' || t.status === filter) &&
      [t.title, ...t.destinations].join(' ').toLocaleLowerCase().includes(needle),
  );
}
export const errorText = (error: unknown) =>
  error instanceof Error ? error.message : '操作失敗，請再試一次。';
