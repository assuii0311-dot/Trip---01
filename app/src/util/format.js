// 표기 규칙(04-design-rules 6절)과 구글맵 링크(poc/gmaps_links.py와 같은 형식)
export function fmtDistance(m) { return m < 1000 ? `${Math.round(m)}m` : `${(m / 1000).toFixed(1)}km`; }
export function fmtMinutes(min) { const h = Math.floor(min / 60), m = Math.round(min % 60); return h ? (m ? `${h}시간 ${m}분` : `${h}시간`) : `${m}분`; }
export function fmtEur(v) { return v == null ? "—" : `€${Math.round(v)}`; }
export function fmtEurRange(a, b) { return a == null && b == null ? "—" : a === b ? fmtEur(a) : `€${Math.round(a)}~${Math.round(b)}`; }
export function gmapsCoord(lat, lon) { return `https://www.google.com/maps/search/?api=1&query=${lat.toFixed(6)},${lon.toFixed(6)}`; }
export function gmapsName(name) { return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(name)}`; }
/** 경유지 한도(모바일 3, 그 외 9)에 맞춰 나눈 경로 링크 목록 */
export function gmapsDirLinks(points, mode = "walking", limit = 3) {
  const ll = (p) => `${p.lat.toFixed(6)},${p.lon.toFixed(6)}`;
  const out = [];
  for (let i = 0; i < points.length - 1; i += limit + 1) {
    const seg = points.slice(i, i + limit + 2);
    const wps = seg.slice(1, -1);
    const wp = wps.length ? `&waypoints=${wps.map(ll).join("%7C")}` : "";
    out.push({ from: seg[0], to: seg[seg.length - 1], via: wps, url: `https://www.google.com/maps/dir/?api=1&origin=${ll(seg[0])}&destination=${ll(seg[seg.length - 1])}${wp}&travelmode=${mode}` });
  }
  return out;
}
export const CAT_ICON = { heritage: "🏛", religious: "⛪", museum: "🖼", nature: "⛰", park: "🌳", beach: "🏖", square: "⛲", market: "🛍", restaurant: "🍽", cafe: "☕", lodging: "🛏", activity: "🎭" };
