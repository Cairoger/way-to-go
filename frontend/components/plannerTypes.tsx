import { BedDouble, Camera, MapPin, Plane, Shapes, TrainFront, Utensils } from 'lucide-react';

export const categories = {
  place: '景點',
  food: '餐飲',
  transit: '交通',
  stay: '住宿',
  flight: '航班',
  custom: '自訂活動',
};
export const statusNames = { must: '必去', want: '想去', maybe: '備選', skip: '不考慮' };
export type Category = keyof typeof categories;
export type PlaceStatus = keyof typeof statusNames;
export const categoryIcons = {
  place: Camera,
  food: Utensils,
  transit: TrainFront,
  stay: BedDouble,
  flight: Plane,
  custom: Shapes,
};

export type Editable = {
  id: string;
  created_by: string;
  editable_by: string;
  editing_by: string | null;
  version: number;
};
export type Place = Editable & {
  name: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
  country: string;
  city: string;
  category: Category;
  status: PlaceStatus;
  tags: string[];
  duration: number | null;
  cost: string | number | null;
  opening_hours: string;
  website: string;
  photo_url: string;
  notes: string;
  candidate: boolean;
  candidate_id: string;
};
export type PlanItem = Editable & {
  archived_place?: { name: string; address: string };
  clock_note?: string;
  timezone: string | null;
  local_timezone: string;
  start_instant: string | null;
  suggested_time: string | null;
  title: string;
  item_type: Category;
  day_id: string;
  place_id: string | null;
  position: number;
  start_time: string | null;
  end_time: string | null;
  duration: number | null;
  notes: string;
  overlap: boolean;
};

export function parseGooglePlaceLink(raw: string) {
  try {
    const url = new URL(raw);
    if (
      url.protocol !== 'https:' ||
      url.username ||
      url.password ||
      !/^(?:(?:www|maps)\.)?google\.(?:com|com\.tw|co\.jp|co\.uk|com\.hk|fr|de)$/.test(url.hostname)
    )
      return null;
    if (!url.pathname.startsWith('/maps') && !url.hostname.startsWith('maps.')) return null;
    const path = decodeURIComponent(url.pathname);
    const query = url.searchParams.get('query') || url.searchParams.get('q') || '';
    const point =
      /^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/.exec(query) ||
      /!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/.exec(path);
    // @lat,lng is the camera center. A place link can center its map well away from the pin.
    const label =
      /\/maps\/place\/([^/]+)/.exec(path)?.[1]?.replace(/\+/g, ' ') ||
      (query && !/^\s*-?\d+[\d.]*\s*,\s*-?\d/.test(query) ? query : '');
    const latitude =
      point && Math.abs(Number(point[1])) <= 90 && Math.abs(Number(point[2])) <= 180
        ? Number(point[1])
        : null;
    const longitude = latitude !== null && point ? Number(point[2]) : null;
    return label || latitude !== null ? { name: label.slice(0, 150), latitude, longitude } : null;
  } catch {
    return null;
  }
}
export type TripDay = {
  id: string;
  day_number: number;
  title: string;
  date: string | null;
  timezone: string;
  items: PlanItem[];
};
export type Lease = { id: string; expires_at: string; version: number };
export function mapLink(place: Place, direction = false) {
  const target =
    place.latitude !== null && place.longitude !== null
      ? `${place.latitude},${place.longitude}`
      : [place.name, place.address, place.city, place.country].filter(Boolean).join(' ');
  return direction
    ? `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(target)}`
    : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(target)}`;
}
export function CategoryIcon({ type, size = 18 }: { type: Category; size?: number }) {
  const Icon = categoryIcons[type] || MapPin;
  return <Icon size={size} aria-hidden="true" />;
}
