// E4 일정 생성 엔진(docs/engines/E4-itinerary.md, 설계 동의 D-025, 체류·마감 규칙 D-024). 순수 함수.
import { hav } from "../data/places.js";

export const DWELL_MIN = { museum: 180, heritage: 135, religious: 70, square: 45, nature: 70, park: 90, beach: 180, market: 90, restaurant: 135, cafe: 70, activity: 180, lodging: 0 }; // D-024
export const MEAL = { lunch: { min: 75, from: "12:30", to: "14:30" }, dinner: { min: 90, from: "19:30" } }; // D-025 (b)
export const TRAVEL_SHARE_MAX = 0.4; // D-025 (d)
export const EDGE_BUFFER_MIN = { flight: 180, train: 60 }; // D-025 (c)

export const toMin = (hhmm) => { const [h, m] = hhmm.split(":").map(Number); return h * 60 + m; };
export const toHHMM = (min) => `${String(Math.floor(min / 60) % 24).padStart(2, "0")}:${String(Math.round(min % 60)).padStart(2, "0")}`;

export function dwellOf(p, overrides = {}) { if (overrides[p.id] != null) return overrides[p.id]; return Math.max(...p.cat.map((c) => DWELL_MIN[c] ?? 60)); }

/** 식사 슬롯 길이(분). 식사 형태 가안: 가볍게 -15, 간식 포함 +30(16시 전후) */
export function mealSlots(meals = []) {
  const light = meals.includes("light") ? -15 : 0;
  const slots = [{ kind: "lunch", min: MEAL.lunch.min + light, from: toMin(MEAL.lunch.from), to: toMin(MEAL.lunch.to) }, { kind: "dinner", min: MEAL.dinner.min + light, from: toMin(MEAL.dinner.from), to: toMin("22:30") }];
  if (meals.includes("snack")) slots.push({ kind: "snack", min: 30, from: toMin("15:30"), to: toMin("17:00") });
  return slots;
}

/** 결정적 k-means(씨앗 고정: 경도 순 초기 중심). 반환: 묶음별 인덱스 배열 */
export function clusterPlaces(places, k) {
  if (k <= 1 || places.length <= 1) return [places.map((_, i) => i)];
  k = Math.min(k, places.length);
  const sorted = [...places.keys()].sort((a, b) => places[a].lon - places[b].lon || places[a].lat - places[b].lat);
  let centers = Array.from({ length: k }, (_, c) => { const p = places[sorted[Math.floor(c * (sorted.length - 1) / (k - 1 || 1))]]; return [p.lat, p.lon]; });
  let assign = new Array(places.length).fill(0);
  for (let iter = 0; iter < 20; iter++) {
    const next = places.map((p) => { let bi = 0, bd = Infinity; centers.forEach(([la, lo], ci) => { const d = hav(p.lat, p.lon, la, lo); if (d < bd - 1e-9) { bd = d; bi = ci; } }); return bi; });
    if (next.every((v, i) => v === assign[i])) break;
    assign = next;
    centers = centers.map(([la, lo], ci) => { const m = places.filter((_, i) => assign[i] === ci); return m.length ? [m.reduce((s, p) => s + p.lat, 0) / m.length, m.reduce((s, p) => s + p.lon, 0) / m.length] : [la, lo]; });
  }
  const groups = Array.from({ length: k }, () => []);
  assign.forEach((c, i) => groups[c].push(i));
  return groups.filter((g) => g.length);
}

/**
 * 한 여행지의 장소를 그 여행지의 날짜들에 나눈다(배치 화면의 "자동 배정", 묶음 13).
 * 좌표로 묶고(clusterPlaces) 서쪽 묶음부터 날짜 순으로 놓는다(generate와 같은 규칙). 하루 capacity곳을 넘는 묶음은
 * 중심에서 먼 장소부터, 자리가 남은 가장 가까운 묶음으로 옮긴다. 어디에도 자리가 없으면 rest(미배치)로 돌려준다.
 * 하루 안의 순서는 묶음 중심에서 가까운 곳부터 이어 가는 최근접 순서다.
 */
export function spreadOverDays(places, dates, capacity = 4) {
  if (!dates.length || !places.length) return { byDate: {}, rest: places.map((p) => p.id) };
  const cen = (g) => [g.reduce((s, p) => s + p.lat, 0) / g.length, g.reduce((s, p) => s + p.lon, 0) / g.length];
  const groups = clusterPlaces(places, dates.length).map((g) => g.map((i) => places[i]));
  groups.sort((a, b) => cen(a)[1] - cen(b)[1] || cen(a)[0] - cen(b)[0] || (a[0].id < b[0].id ? -1 : 1));
  while (groups.length < dates.length) groups.push([]);
  const rest = [];
  for (let guard = places.length * 2; guard > 0; guard--) {
    const gi = groups.findIndex((g) => g.length > capacity); if (gi < 0) break;
    const g = groups[gi]; const [la, lo] = cen(g);
    let fi = 0, fd = -1; g.forEach((p, i) => { const d = hav(p.lat, p.lon, la, lo); if (d > fd || (d === fd && p.id < g[fi].id)) { fd = d; fi = i; } });
    const [p] = g.splice(fi, 1);
    let ti = -1, td = Infinity;
    groups.forEach((h, i) => { if (i === gi || h.length >= capacity) return; const d = h.length ? hav(p.lat, p.lon, ...cen(h)) : 1e12; if (d < td) { td = d; ti = i; } });
    if (ti < 0) rest.push(p.id); else groups[ti].push(p);
  }
  const byDate = {};
  groups.forEach((g, i) => {
    if (!g.length) return;
    const [la, lo] = cen(g);
    byDate[dates[i]] = orderRoute(g, { lat: la, lon: lo }, (a, b) => hav(a.lat, a.lon, b.lat, b.lon)).map((k) => g[k].id);
  });
  return { byDate, rest };
}

export const TWO_OPT_MAX_PASSES = 50; // 순서 다듬기(2-opt)의 반복 상한(T-052). 추정: 보통 10번 안에 멈춘다

/** 같은 구간의 이동 계산을 한 번만 하게 감싼다(T-052). 열쇠는 장소 id, 없으면 좌표 */
export function memoTravel(travel) {
  const cache = new Map(); const k = (x) => x.id ?? `${x.lat},${x.lon}`;
  return (a, b) => { const key = `${k(a)}>${k(b)}`; let v = cache.get(key); if (v === undefined) { v = travel(a, b); cache.set(key, v); } return v; };
}

/** 최근접 이웃 + 2-opt. start는 {lat, lon}. travel(a,b)는 분. 같은 구간은 한 번만 계산하고 2-opt는 TWO_OPT_MAX_PASSES번까지 돈다 */
export function orderRoute(places, start, travel) {
  if (places.length <= 1) return [...places.keys()];
  const n = places.length; const seen = new Map(); // 구간(출발 -1 = start, 도착) → 분
  const tv = (i, j) => { const key = (i + 1) * (n + 1) + j; let v = seen.get(key); if (v === undefined) { v = travel(i < 0 ? start : places[i], places[j]); seen.set(key, v); } return v; };
  let order = []; const left = new Set(places.keys()); let cur = start;
  while (left.size) { let bi = null, bd = Infinity; for (const i of left) { const d = hav(cur.lat, cur.lon, places[i].lat, places[i].lon); if (d < bd) { bd = d; bi = i; } } order.push(bi); left.delete(bi); cur = places[bi]; }
  const cost = (o) => o.reduce((s, i, k) => s + tv(k === 0 ? -1 : o[k - 1], i), 0);
  let improved = true, c0 = cost(order);
  for (let pass = 0; improved && pass < TWO_OPT_MAX_PASSES; pass++) { improved = false; for (let i = 0; i < order.length - 1; i++) for (let j = i + 1; j < order.length; j++) { const o2 = order.slice(0, i).concat(order.slice(i, j + 1).reverse(), order.slice(j + 1)); const c2 = cost(o2); if (c2 < c0 - 0.5) { order = o2; c0 = c2; improved = true; } } }
  return order;
}

/** 영업시간 참고값 문자열에서 요일 무시하고 첫 시간대를 뽑는다(추정). 못 읽으면 null */
export function parseHours(h) {
  if (!h) return null;
  const m = String(h).match(/(\d{1,2}):(\d{2})\s*[-–~]\s*(\d{1,2}):(\d{2})/);
  if (!m) return null;
  return { open: Number(m[1]) * 60 + Number(m[2]), close: Number(m[3]) * 60 + Number(m[4]) };
}

/**
 * 하루 일정 배치(E4 4절 2·6·7항). 마감은 항목 시작 시각 기준(D-024).
 * @param {object} opt {date, start, end(HHMM), places:[{p, dwell, fixedAt?}], origin:{lat,lon,name}, travel(a,b)→{min, mode...}, meals:[], locked:[]}
 * 반환 {items:[...], overflow:[placeIds], summary}
 */
export function placeDay({ start, end, places, origin, travel, meals = [], hoursOf = (p) => parseHours(p.hrs), order }) {
  const s0 = toMin(start), e0 = toMin(end);
  const slots = mealSlots(meals); const usedSlot = new Set();
  const items = []; const overflow = [];
  let t = s0; let cur = origin; let travelTotal = 0, walkM = 0;
  const seq = order || orderRoute(places.map((x) => x.p), origin, (a, b) => travel(a, b).min);
  for (const idx of seq) {
    const { p, dwell, fixedAt } = places[idx];
    // 식사 슬롯: 다음 항목 전에 슬롯 시각이 지나면 삽입
    for (const sl of slots) { if (!usedSlot.has(sl.kind) && t >= sl.from && t <= sl.to + 60 && t + sl.min <= e0 && !p.cat.includes("restaurant")) { items.push({ kind: "meal", meal: sl.kind, start: t, end: t + sl.min }); t += sl.min; usedSlot.add(sl.kind); } }
    const tr = travel(cur, p);
    let st = t + tr.min;
    if (fixedAt != null) st = Math.max(st, fixedAt);
    const hrs = hoursOf(p); let flag = null;
    if (hrs) { if (st < hrs.open) { st = hrs.open; } if (st + dwell > hrs.close) flag = "closed_or_short"; } else flag = "no_hours";
    if (st > e0) { overflow.push(p.id); continue; } // 마감은 시작 시각 기준
    if (p.cat.includes("restaurant")) { for (const sl of slots) if (!usedSlot.has(sl.kind) && st >= sl.from - 30 && st <= sl.to + 60) usedSlot.add(sl.kind); }
    items.push({ kind: "place", id: p.id, start: st, end: st + dwell, dwell, travel: tr, flag, fixed: fixedAt != null });
    travelTotal += tr.min; walkM += tr.mode === "walk" ? (tr.m || 0) : 0; t = st + dwell; cur = p;
  }
  const dayLen = Math.max(1, e0 - s0);
  return { items, overflow, summary: { places: items.filter((i) => i.kind === "place").length, travelMin: travelTotal, walkM, start: s0, end: t, travelShare: Math.round(travelTotal / dayLen * 100) / 100, warn: travelTotal / dayLen > TRAVEL_SHARE_MAX } };
}

/**
 * 전체 일정 생성(E4 4절). dayPlan: [{date, cityId, origin, places:[p...], fixed:{id:HHMM}, locked:bool}]
 * assigned: 날짜별로 사용자가 배치한 장소 id 목록(배치된 것은 그 날에 둔다). 나머지 도시 장소는 k-means로 나눈다.
 */
export function generate({ days, placesByCity, assigned = {}, dwellOverrides = {}, fixed = {}, travelFor, meals, dayStart, dayEnd, edges = {} }) {
  const out = []; const overflow = [];
  const memo = {}; const tf = (cid) => (memo[cid] ||= memoTravel(travelFor(cid))); // 넘친 장소가 다음 날로 넘어가며 같은 구간을 다시 묻는다(T-052)
  const byCityDays = {}; days.forEach((d, i) => { (byCityDays[d.cityId] ||= []).push(i); });
  const planned = new Set(Object.values(assigned).flat());
  const auto = {}; // dayIndex → place objects
  for (const [cityId, idxs] of Object.entries(byCityDays)) {
    const free = (placesByCity[cityId] || []).filter((p) => !planned.has(p.id));
    const groups = clusterPlaces(free, idxs.length);
    // 묶음을 날짜에 배정: 묶음 중심 경도 순 ↔ 날짜 순(결정적)
    groups.sort((a, b) => (a.reduce((s, i) => s + free[i].lon, 0) / a.length) - (b.reduce((s, i) => s + free[i].lon, 0) / b.length));
    groups.forEach((g, gi) => { auto[idxs[gi % idxs.length]] = (auto[idxs[gi % idxs.length]] || []).concat(g.map((i) => free[i])); });
  }
  days.forEach((d, di) => {
    const fixedList = (assigned[d.date] || []).map((id) => placesByCity.__all.get(id)).filter(Boolean);
    const list = fixedList.concat(auto[di] || []);
    let start = dayStart, end = dayEnd;
    if (d.edge === "arrive" && d.arriveAt) start = toHHMM(Math.max(toMin(dayStart), toMin(d.arriveAt)));
    if (d.edge === "depart" && d.departAt) end = toHHMM(Math.max(toMin(dayStart), toMin(d.departAt) - (EDGE_BUFFER_MIN[d.departMode] ?? 60)));
    const day = placeDay({ start, end, places: list.map((p) => ({ p, dwell: dwellOf(p, dwellOverrides), fixedAt: fixed[p.id] ? toMin(fixed[p.id]) : null })), origin: d.origin, travel: tf(d.cityId), meals, order: d.lockedOrder ? d.lockedOrder.map((id) => list.findIndex((p) => p.id === id)).filter((i) => i >= 0) : undefined });
    out.push({ date: d.date, cityId: d.cityId, origin: d.origin, ...day });
    // 넘친 장소는 같은 도시의 다음 날로 넘긴다(한 번만)
    if (day.overflow.length && di + 1 < days.length && days[di + 1].cityId === d.cityId) auto[di + 1] = (auto[di + 1] || []).concat(day.overflow.map((id) => placesByCity.__all.get(id)));
    else overflow.push(...day.overflow.map((id) => ({ id, reason: "시간 부족" })));
  });
  return { days: out, overflow };
}
