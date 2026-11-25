'use client';

import { useEffect, useRef, useState } from 'react';
import type { Map as LeafletMap } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { ExternalLink, Navigation } from 'lucide-react';
import { CategoryIcon, categories, mapLink, type Place, type TripDay } from './plannerTypes';

const colors = {
  place: '#228264',
  food: '#b65524',
  transit: '#43649c',
  stay: '#86579a',
  flight: '#34778f',
  custom: '#74654b',
};

export default function PlannerMap({ places, days }: { places: Place[]; days: TripDay[] }) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const [tileError, setTileError] = useState(false);
  const [routeDay, setRouteDay] = useState('');
  const ordered =
    days
      .find((d) => d.id === routeDay)
      ?.items.flatMap((item) => {
        const place = places.find((p) => p.id === item.place_id);
        return place?.latitude != null && place.longitude != null
          ? [[place.latitude, place.longitude]]
          : [];
      }) || [];
  const line = JSON.stringify(ordered);
  const points = places.filter((p) => p.latitude !== null && p.longitude !== null);
  // Skip map recreation on unrelated collaboration events.
  const markers = JSON.stringify(
    points.map((p) => [p.id, p.name, p.category, p.latitude, p.longitude]),
  );
  useEffect(() => {
    let cancelled = false;
    setTileError(false);
    void import('leaflet')
      .then((L) => {
        if (cancelled || !host.current) return;
        const instance = L.map(host.current, { scrollWheelZoom: false }).setView([23.7, 120.96], 7);
        map.current = instance;
        const tiles =
          process.env.NEXT_PUBLIC_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
        L.tileLayer(tiles, {
          maxZoom: 19,
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        })
          .on('tileerror', () => !cancelled && setTileError(true))
          .addTo(instance);
        const coords: [number, number][] = [];
        const entries: [string, string, keyof typeof colors, number, number][] =
          JSON.parse(markers);
        for (const [, name, category, lat, lon] of entries) {
          coords.push([lat, lon]);
          const label = document.createElement('span');
          label.textContent = `${categories[category]} · ${name}`;
          const icon = L.divIcon({
            className: 'wp-pin-wrap',
            iconSize: [28, 28],
            iconAnchor: [14, 14],
            html: `<span class="wp-pin" style="background:${colors[category]}">${categories[category].slice(0, 1)}</span>`,
          });
          L.marker([lat, lon], { icon, alt: name }).addTo(instance).bindPopup(label);
        }
        const route: [number, number][] = JSON.parse(line);
        if (route.length > 1)
          L.polyline(route, { color: '#316b53', weight: 3, dashArray: '6 8' }).addTo(instance);
        if (route.length)
          instance.fitBounds(L.latLngBounds(route), { padding: [38, 38], maxZoom: 15 });
        else if (coords.length)
          instance.fitBounds(L.latLngBounds(coords), { padding: [38, 38], maxZoom: 15 });
      })
      .catch(() => !cancelled && setTileError(true));
    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
    };
  }, [markers, line]);

  return (
    <div className="wp-map-panel">
      <label className="wp-filter wp-map-route">
        行程序列連線
        <select value={routeDay} onChange={(e) => setRouteDay(e.target.value)}>
          <option value="">只顯示地點</option>
          {days.map((day) => (
            <option key={day.id} value={day.id}>
              Day {day.day_number} · 景點順序
            </option>
          ))}
        </select>
      </label>
      <p className="wp-hint">自動規劃道路路線：付費功能開發中。可使用景點旁的免費導航。</p>
      {routeDay && (
        <p className="wp-hint">
          {ordered.length >= 2
            ? '虛線依行程順序連接地點，實際道路請參考導航。'
            : '當天需要兩個以上有座標的地點才能連線。'}
        </p>
      )}
      <div ref={host} className="wp-map" aria-label="旅程景點地圖" />
      {tileError && (
        <p className="wp-notice" role="status">
          底圖暫時無法載入。可使用下方景點地址及導航連結。
        </p>
      )}
      {points.length < places.length && (
        <p className="wp-hint">{places.length - points.length} 個景點尚未填寫座標。</p>
      )}
      <div className="wp-map-list">
        {places.map((place) => (
          <div key={place.id} className="wp-map-line">
            <span className={`wp-symbol wp-${place.category}`}>
              <CategoryIcon type={place.category} />
            </span>
            <div>
              <strong>{place.name}</strong>
              <small>
                {place.address ||
                  [place.city, place.country].filter(Boolean).join(' · ') ||
                  categories[place.category]}
              </small>
            </div>
            {place.latitude !== null && place.longitude !== null && (
              <button
                type="button"
                className="wp-text"
                onClick={() => map.current?.setView([place.latitude!, place.longitude!], 15)}
              >
                定位
              </button>
            )}
            <a
              className="wp-text"
              href={mapLink(place)}
              target="_blank"
              rel="noreferrer"
              aria-label={`在 Google Maps 搜尋${place.name}`}
            >
              <ExternalLink size={16} />
            </a>
            <a
              className="wp-text"
              href={mapLink(place, true)}
              target="_blank"
              rel="noreferrer"
              aria-label={`導航至${place.name}`}
            >
              <Navigation size={16} />
            </a>
          </div>
        ))}
      </div>
      {!places.length && <p className="wp-hint">新增候選景點並填寫座標，即可在地圖上查看位置。</p>}
    </div>
  );
}
