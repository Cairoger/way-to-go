// Shared keys with frontend/lib/offlineTrips.ts. Use text nodes for all saved user data.
const accountKey = 'waytogo.offline.account';
const tripPrefix = 'waytogo.offline.trip.';
const container = document.getElementById('trip');
function line(tag, value, parent = container) {
  const element = document.createElement(tag);
  element.textContent = value;
  parent.append(element);
  return element;
}
function showSaved() {
  container.replaceChildren();
  let records = [];
  try {
    const owner = localStorage.getItem(accountKey);
    if (owner)
      records = Object.keys(localStorage)
        .filter((k) => k.startsWith(tripPrefix))
        .map((k) => ({ id: k.slice(tripPrefix.length), ...JSON.parse(localStorage.getItem(k)) }))
        .filter((t) => t.owner === owner);
  } catch {
    records = [];
  }
  const id = new URLSearchParams(location.search).get('trip');
  if (!id) {
    line('h1', '已儲存的旅程');
    if (!records.length) line('p', '此裝置沒有可離線閱讀的旅程。');
    for (const t of records) {
      const link = line('a', t.title, line('p', ''));
      link.href = '/?trip=' + encodeURIComponent(t.id);
    }
    return;
  }
  const trip = records.find((t) => t.id === id);
  if (!trip) {
    line('h1', '此旅程尚未儲存在裝置上');
    line('p', '請連線後開啟旅程並選擇「儲存離線旅程」。');
    return;
  }
  line('h1', trip.title);
  line('p', [trip.destinations, trip.dates].filter(Boolean).join(' · '));
  line('small', '儲存於 ' + new Date(trip.savedAt).toLocaleString('zh-TW'));
  for (const day of trip.days) {
    line('h2', day.heading);
    if (!day.items.length) line('p', '當天尚無活動。');
    for (const item of day.items) {
      const card = line('section', '');
      line('h3', item.title, card);
      line('p', [item.time, item.zone, item.clockNote].filter(Boolean).join(' · '), card);
      if (item.place || item.address)
        line('p', [item.place, item.address].filter(Boolean).join(' · '), card);
    }
  }
  if (trip.places.length) {
    line('h2', '候選景點');
    for (const place of trip.places)
      line('p', [place.name, place.address].filter(Boolean).join(' · '));
  }
}
window.addEventListener('storage', showSaved);
window.addEventListener('pageshow', showSaved);
showSaved();
