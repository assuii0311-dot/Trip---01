// 여행 데이터(docs/02-data-model.md 3절)의 순수 변환 함수. plan = {trip, selection, custom, days, lodging, reservations}
import { emptyTrip, tripDays } from "./store.js";

export const PLAN_KEY = "trip01.plan.v1";

export function emptyPlan() {
  return { trip: emptyTrip(), selection: [], custom: {}, days: {}, lodging: {}, reservations: {}, version: 1 };
}

/** 이전 키(trip01.draft.v1 등)에서 옮겨 온다 */
export function migrate(raw, legacy = {}) {
  const base = emptyPlan();
  if (raw && typeof raw === "object") {
    return { ...base, ...raw, trip: { ...base.trip, ...(raw.trip || {}) } };
  }
  return { ...base, trip: { ...base.trip, ...(legacy.trip || {}) }, selection: legacy.selection || [], reservations: legacy.reservations || {} };
}

export function loadPlan(storage) {
  try {
    const raw = storage.getItem(PLAN_KEY);
    if (raw) return migrate(JSON.parse(raw));
    const legacy = { trip: JSON.parse(storage.getItem("trip01.draft.v1") || "null") || undefined, selection: JSON.parse(storage.getItem("trip01.selection.v1") || "[]"), reservations: JSON.parse(storage.getItem("trip01.reservations.v1") || "{}") };
    return migrate(null, legacy);
  } catch { return emptyPlan(); }
}
export function savePlan(storage, plan) { try { storage.setItem(PLAN_KEY, JSON.stringify(plan)); return true; } catch { return false; } }

/** 날짜 목록(YYYY-MM-DD) */
export function dateList(trip) {
  const n = tripDays(trip); if (!n) return [];
  const out = []; const d = new Date(trip.start + "T00:00:00Z");
  for (let i = 0; i < n; i++) { out.push(new Date(d.getTime() + i * 86400000).toISOString().slice(0, 10)); }
  return out;
}

export function toggleSelect(plan, id) {
  const has = plan.selection.includes(id);
  const selection = has ? plan.selection.filter((x) => x !== id) : [...plan.selection, id];
  const days = has ? Object.fromEntries(Object.entries(plan.days).map(([d, ids]) => [d, ids.filter((x) => x !== id)])) : plan.days;
  return { ...plan, selection, days };
}

/** 여러 장소를 한 번에 선택에 넣는다(이미 있는 곳은 그대로, 순서 유지). 요약 화면의 "추천 모두 담기"(D-039) */
export function addSelections(plan, ids) {
  const have = new Set(plan.selection);
  const add = ids.filter((id) => !have.has(id) && have.add(id));
  return add.length ? { ...plan, selection: [...plan.selection, ...add] } : plan;
}

/** 장소를 날짜에 배치(null이면 미배치). 다른 날에서 제거하고 끝에 붙인다 */
export function assignDay(plan, id, date) {
  const days = Object.fromEntries(Object.entries(plan.days).map(([d, ids]) => [d, ids.filter((x) => x !== id)]));
  if (date) days[date] = [...(days[date] || []), id];
  return { ...plan, days };
}

export function moveInDay(plan, date, from, to) {
  const ids = [...(plan.days[date] || [])]; if (from < 0 || from >= ids.length || to < 0 || to >= ids.length) return plan;
  const [x] = ids.splice(from, 1); ids.splice(to, 0, x);
  return { ...plan, days: { ...plan.days, [date]: ids } };
}

/** 고른 장소 여러 곳을 한 번에 뺀다. 날짜 배치에서도 빼고, 직접 추가한 장소는 정의까지 지운다(다시 고를 길이 없다). 예약·체류 시간 메모는 남긴다(묶음 13) */
export function removeSelections(plan, ids) {
  const drop = new Set(ids); if (!drop.size) return plan;
  return { ...plan, selection: plan.selection.filter((id) => !drop.has(id)),
    days: Object.fromEntries(Object.entries(plan.days).map(([d, a]) => [d, a.filter((id) => !drop.has(id))])),
    custom: Object.fromEntries(Object.entries(plan.custom || {}).filter(([k]) => !drop.has(k))) };
}

/** 여행지를 빼면서 그 여행지에서 고른 장소도 함께 뺀다. placeIds는 그 여행지에 속한 고른 장소다(묶음 13) */
export function removeDestination(plan, destId, placeIds = []) {
  const p = removeSelections(plan, placeIds);
  return { ...p, trip: { ...p.trip, cities: p.trip.cities.filter((x) => x !== destId) }, lodging: Object.fromEntries(Object.entries(p.lodging || {}).filter(([k]) => k !== destId)) };
}

/** 여러 장소의 날짜 배치를 한 번에 바꾼다. byDate {날짜: [장소]}의 장소는 다른 날에서 빼고 그 날 끝에 순서대로 넣는다. clear의 장소는 미배치로 돌린다(묶음 13) */
export function assignMany(plan, byDate = {}, clear = []) {
  const moved = new Set([...Object.values(byDate).flat(), ...clear]);
  const days = Object.fromEntries(Object.entries(plan.days).map(([d, a]) => [d, a.filter((id) => !moved.has(id))]));
  for (const [d, ids] of Object.entries(byDate)) days[d] = [...(days[d] || []), ...ids];
  return { ...plan, days };
}

/** 여행지 순서를 한 칸 옮긴다(dir: -1 앞으로, +1 뒤로). 끝에서는 그대로(D-051) */
export function moveCity(plan, cityId, dir) {
  const cs = [...plan.trip.cities], i = cs.indexOf(cityId), j = i + (dir < 0 ? -1 : 1);
  if (i < 0 || j < 0 || j >= cs.length) return plan;
  [cs[i], cs[j]] = [cs[j], cs[i]];
  return { ...plan, trip: { ...plan.trip, cities: cs } };
}

/**
 * 전체 일정 대안을 계획에 쓴다(E2 4절 5항, D-051): 여행지 순서, 여행지별 숙박 일수, 추천 기준.
 * order가 지금 여행지와 같은 집합이 아니면 아무것도 바꾸지 않는다. keepAssign이 false면 날짜 배치를 모두 푼다(고른 장소는 남는다).
 */
export function applyTripPlan(plan, { order, nights = {}, balance = null }, { keepAssign = true } = {}) {
  const cur = plan.trip.cities;
  if (!Array.isArray(order) || order.length !== cur.length || new Set(order).size !== order.length || order.some((id) => !cur.includes(id))) return plan;
  const lodging = { ...plan.lodging };
  for (const id of order) if (nights[id] != null) lodging[id] = { ...(lodging[id] || {}), nights: Number(nights[id]) };
  const trip = { ...plan.trip, cities: [...order], ...(balance ? { foreignBalance: balance } : {}) };
  const days = keepAssign ? plan.days : Object.fromEntries(Object.keys(plan.days).map((d) => [d, []]));
  return { ...plan, trip, lodging, days };
}

export function unassigned(plan) { const placed = new Set(Object.values(plan.days).flat()); return plan.selection.filter((id) => !placed.has(id)); }

/** 직접 추가 장소(R-07): 교차검증 "사용자 추가" */
export function addCustomPlace(plan, { name, lat, lon, cityId, cat = "heritage" }) {
  const id = `user:${Date.now().toString(36)}:${Math.random().toString(36).slice(2, 6)}`;
  const p = { id, n: { local: name }, lat, lon, city: cityId || null, cat: [cat], cv: "user", ver: true, tier: 1, her: [], desc: [], pop: { sl: 0, pv: null, en_share: null }, links: {}, src: { wd: null, osm: [], wv: [] }, hrs: null, price: null };
  return { ...plan, custom: { ...plan.custom, [id]: p }, selection: [...plan.selection, id] };
}

/**
 * 일정표를 만든 뒤 선택이 달라졌는지(D-036). missing: 골랐지만 일정표(날짜별 항목과 초과분)에 없는 장소, removed: 일정표에 있지만 선택에서 뺀 장소.
 * 일정표가 없으면 둘 다 빈 목록이다.
 */
export function itineraryDrift(plan) {
  const it = plan.itinerary;
  if (!it) return { missing: [], removed: [] };
  const inIt = new Set();
  for (const d of it.days || []) for (const i of d.items || []) if (i.kind === "place") inIt.add(i.id);
  for (const o of it.overflow || []) inIt.add(o.id);
  const sel = new Set(plan.selection);
  return { missing: plan.selection.filter((id) => !inIt.has(id)), removed: [...inIt].filter((id) => !sel.has(id)) };
}

export function setLodging(plan, cityId, patch) { return { ...plan, lodging: { ...plan.lodging, [cityId]: { ...(plan.lodging[cityId] || {}), ...patch } } }; }

/** 도시별 숙박 일수 합이 기간-1과 같은지 */
export function lodgingCheck(plan) {
  const nights = Object.values(plan.lodging).reduce((s, l) => s + (Number(l.nights) || 0), 0);
  const total = Math.max(0, tripDays(plan.trip) - 1);
  return { nights, total, ok: nights === total };
}
