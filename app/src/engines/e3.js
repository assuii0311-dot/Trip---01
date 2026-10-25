// E3 이동 시간 엔진(앱 쪽, docs/engines/E3-travel-time.md 설계 동의 D-025). 사전 계산 조회와 추정만 한다. 순수 함수.
import { hav } from "../data/places.js";

export const PARAMS = {
  walkSpeedKmh: 4.5, walkDetour: 1.24, carDetour: 1.27, cityCarKmh: 22, // 도시 안 차량 속도는 사전 계산 표본 중앙값으로 바꾼다(미측정. 추정 22km/h)
  walkCorrection: 1.12, carCorrection: 1.23, walkPreferM: 1500, // D-025 (c)(e)
  stopRadiusM: 400, waitMin: { 1: 5, 0: 6, 3: 8, 2: 8, 7: 6 }, speedKmh: { 1: 30, 0: 18, 3: 14, 2: 40, 7: 12 }, transferMin: 6, // D-025 (d)
  taxiWaitMin: 2, flightKmh: 700, flightProcMin: 120, ferryKmh: 35, ferryProcMin: 60, // D-025 (f)
};
const MODE_KO = { walk: "도보", transit: "대중교통", taxi: "택시", car: "차량", train: "기차", flight: "비행기", ferry: "배" };

export function straightWalk(a, b) {
  const d = hav(a.lat, a.lon, b.lat, b.lon) * PARAMS.walkDetour;
  return { min: Math.round(d / 1000 / PARAMS.walkSpeedKmh * 60), m: Math.round(d), confidence: "estimate" };
}
export function straightCar(a, b) {
  const d = hav(a.lat, a.lon, b.lat, b.lon) * PARAMS.carDetour;
  return { min: Math.round(d / 1000 / PARAMS.cityCarKmh * 60), m: Math.round(d), confidence: "estimate" };
}

/** 도시 안 사전 계산 색인(travel/<city>.json.gz) */
export function makeIntraIndex(file) {
  const idx = new Map(file.ids.map((id, i) => [id, i]));
  const pairs = new Map();
  for (const [i, j, t, d] of file.pairs) pairs.set(`${i}|${j}`, { min: t, m: d });
  return { lookup(aId, bId) { const i = idx.get(aId), j = idx.get(bId); if (i == null || j == null) return null; const p = pairs.get(`${Math.min(i, j)}|${Math.max(i, j)}`); return p ? { min: Math.round(p.min), m: p.m, confidence: "computed" } : null; } };
}

/** 도보 시간: 사전 계산 → 직선 추정 */
export function walkTime(a, b, intra) {
  return (intra && intra.lookup(a.id, b.id)) || straightWalk(a, b);
}

/** 대중교통 B 추정(E3 4절 3항): 두 지점 400m 안 정류장을 지나는 공통 노선(직통) 또는 1회 환승 */
export function makeTransitIndex(file) {
  if (!file) return null;
  const stops = file.stops; // [lat, lon, name]
  const routesByStop = new Map();
  file.routes.forEach((r, ri) => { for (const seq of r.seq) seq.forEach((s, pos) => { if (!routesByStop.has(s)) routesByStop.set(s, []); routesByStop.get(s).push([ri, pos, seq]); }); });
  const near = (p) => { const out = []; for (let i = 0; i < stops.length; i++) { const d = hav(p.lat, p.lon, stops[i][0], stops[i][1]); if (d <= PARAMS.stopRadiusM) out.push([i, d]); } return out; };
  return { stops, routes: file.routes, fares: file.fares || [], near, routesByStop };
}

export function transitEstimate(a, b, tidx) {
  if (!tidx) return null;
  const na = tidx.near(a), nb = tidx.near(b);
  if (!na.length || !nb.length) return null;
  const walk = (m) => Math.round(m / 1000 / PARAMS.walkSpeedKmh * 60);
  let best = null;
  // 직통
  for (const [sa, da] of na) for (const [ra, pa, seqA] of tidx.routesByStop.get(sa) || []) for (const [sb, db] of nb) {
    const pb = seqA.indexOf(sb); if (pb < 0 || pb === pa) continue;
    const r = tidx.routes[ra]; let dist = 0;
    const lo = Math.min(pa, pb), hi = Math.max(pa, pb);
    for (let k = lo; k < hi; k++) dist += hav(tidx.stops[seqA[k]][0], tidx.stops[seqA[k]][1], tidx.stops[seqA[k + 1]][0], tidx.stops[seqA[k + 1]][1]);
    const ride = dist / 1000 / (PARAMS.speedKmh[r.type] ?? 14) * 60;
    const total = walk(da) + (PARAMS.waitMin[r.type] ?? 8) + ride + walk(db);
    if (!best || total < best.min) best = { min: Math.round(total), legs: [{ route: r.name, type: r.type, stops: hi - lo, from: tidx.stops[sa][2], to: tidx.stops[sb][2] }], transfers: 0, confidence: "estimate" };
  }
  if (best) return best;
  // 1회 환승: A 근처 노선의 정류장 중 B 근처 노선과 겹치는 정류장
  const routesB = new Map();
  for (const [sb, db] of nb) for (const [rb, pb, seqB] of tidx.routesByStop.get(sb) || []) seqB.forEach((s, pos) => { if (!routesB.has(s)) routesB.set(s, []); routesB.get(s).push([rb, pos, pb, seqB, db, sb]); });
  for (const [sa, da] of na) for (const [ra, pa, seqA] of tidx.routesByStop.get(sa) || []) seqA.forEach((s, pos) => {
    if (pos === pa || !routesB.has(s)) return;
    for (const [rb, pos2, pb, seqB, db, sb] of routesB.get(s)) {
      if (rb === ra || pos2 === pb) continue;
      const r1 = tidx.routes[ra], r2 = tidx.routes[rb];
      const seg = (seq, i, j) => { let d = 0; for (let k = Math.min(i, j); k < Math.max(i, j); k++) d += hav(tidx.stops[seq[k]][0], tidx.stops[seq[k]][1], tidx.stops[seq[k + 1]][0], tidx.stops[seq[k + 1]][1]); return d; };
      const total = walk(da) + (PARAMS.waitMin[r1.type] ?? 8) + seg(seqA, pa, pos) / 1000 / (PARAMS.speedKmh[r1.type] ?? 14) * 60 + PARAMS.transferMin + (PARAMS.waitMin[r2.type] ?? 8) + seg(seqB, pos2, pb) / 1000 / (PARAMS.speedKmh[r2.type] ?? 14) * 60 + walk(db);
      if (!best || total < best.min) best = { min: Math.round(total), legs: [{ route: r1.name, type: r1.type, stops: Math.abs(pos - pa), from: tidx.stops[sa][2], to: tidx.stops[s][2] }, { route: r2.name, type: r2.type, stops: Math.abs(pb - pos2), from: tidx.stops[s][2], to: tidx.stops[sb][2] }], transfers: 1, confidence: "estimate" };
    }
  });
  return best;
}

export function gmapsTransit(a, b) { return `https://www.google.com/maps/dir/?api=1&origin=${a.lat.toFixed(6)},${a.lon.toFixed(6)}&destination=${b.lat.toFixed(6)},${b.lon.toFixed(6)}&travelmode=transit`; }

/** 도시 안 구간의 수단별 선택지와 최적안(E3 4절 7항) */
export function cityLeg(a, b, { intra, tidx, taxi } = {}) {
  const w = walkTime(a, b, intra);
  const options = [{ mode: "walk", min: w.min, m: w.m, confidence: w.confidence }];
  const t = transitEstimate(a, b, tidx);
  if (t) options.push({ mode: "transit", min: t.min, legs: t.legs, transfers: t.transfers, confidence: "estimate", link: gmapsTransit(a, b) });
  const c = straightCar(a, b);
  options.push({ mode: "taxi", min: c.min + PARAMS.taxiWaitMin, m: c.m, confidence: "estimate", fare: taxi ? Math.max(taxi.min_eur, taxi.base_eur + c.m / 1000 * taxi.per_km_eur) : null });
  let best;
  if (w.m <= PARAMS.walkPreferM) best = options[0]; else best = [...options].sort((x, y) => x.min - y.min)[0];
  const alternatives = options.filter((o) => o !== best).sort((x, y) => x.min - y.min).slice(0, 2);
  return { best, alternatives, options };
}

/** 도시 간 구간(사전 계산 행렬 + 기차 + 비행기·배 추정) */
export function intercityLeg(fromCity, toCity, inter, { airports = [] } = {}) {
  const ia = inter.cities.findIndex((c) => c.id === fromCity.id), ib = inter.cities.findIndex((c) => c.id === toCity.id);
  const options = [];
  const car = ia >= 0 && ib >= 0 ? inter.car_min[ia][ib] : null;
  const dist = hav(fromCity.lat, fromCity.lon, toCity.lat, toCity.lon);
  if (car != null) options.push({ mode: "car", min: car, km: inter.car_km[ia][ib], confidence: "computed" });
  else options.push({ mode: "car", min: Math.round(dist * PARAMS.carDetour / 1000 / 80 * 60), km: Math.round(dist * PARAMS.carDetour / 1000), confidence: "estimate", note: "행렬 밖 도시. 직선 추정" });
  const tr = ia >= 0 && ib >= 0 ? inter.train_min[ia][ib] : null;
  if (tr != null) options.push({ mode: "train", min: tr, perDay: inter.trains_per_day[ia][ib], confidence: "computed", note: "Renfe 직통 최단 운행(역 접근 제외)" });
  if (dist > 250000 || car == null) options.push({ mode: "flight", min: Math.round(dist / 1000 / PARAMS.flightKmh * 60 + PARAMS.flightProcMin), confidence: "estimate", link: gmapsTransit(fromCity, toCity), note: "거리 기반 추정(D-021 ②)" });
  if (car == null) options.push({ mode: "ferry", min: Math.round(dist / 1000 / PARAMS.ferryKmh * 60 + PARAMS.ferryProcMin), confidence: "estimate", link: gmapsTransit(fromCity, toCity), note: "항로 존재 여부 미확인. 거리 기반 추정" });
  const best = [...options].sort((x, y) => x.min - y.min)[0];
  return { best, alternatives: options.filter((o) => o !== best).sort((x, y) => x.min - y.min).slice(0, 2), options };
}

export function modeKo(m) { return MODE_KO[m] || m; }
