// E2 추천 엔진(docs/engines/E2-recommendation.md, 설계 동의 D-025. 인기 점수와 추천의 두 묶음은 D-049).
// 순수 함수만 둔다. 입력은 E1 기준 데이터와 여행 입력, 출력은 설계 문서 3절의 구조.
import { hav, isForeignLandmark } from "../data/places.js";

export const W_SELECTED = 1.0, W_UNSELECTED = 0.3; // D-025 (f). 화면의 선호 표시에만 쓴다(D-049)
export const LANDMARK_TH = { share: 0.5, sitelinks: 10 }; // D-025 (d)
export const BUNDLE_SHARE = { landmark: 0.75, balance: 0.5, other: 0.25 }; // D-049: 추천 가운데 대표 명소 묶음의 몫(제안값)
export const RUN_MAX = 3; // 같은 첫 범주가 이어질 수 있는 수

/** 선호 분석(R-05): 범주 가중치와 프로필 문장. budget·dayCapacity는 E6·E4 값과 맞춘다. */
export function profile(trip, categories, dayCapacity = 4) {
  const sel = new Set(trip.tastes || []);
  const weights = Object.fromEntries(categories.map((c) => [c.id, sel.size === 0 ? W_SELECTED : sel.has(c.id) ? W_SELECTED : W_UNSELECTED]));
  const names = categories.filter((c) => sel.has(c.id)).map((c) => c.ko);
  const budget = { low: "저가", mid: "중가", high: "고가" }[trip.budget] || "중가";
  const sentence = `${names.length ? names.slice(0, 3).join("·") + " 중심" : "모든 범주 고르게"}, ${budget}, 하루 ${dayCapacity}곳 안팎`;
  return { weights, sentence, budget, dayCapacity, tastes: [...sel] };
}

const views = (p) => (p.pop?.pv?.en ?? 0) + (p.pop?.pv?.es ?? 0);

/**
 * 인기 점수(E2 4절 3항, D-049): 사이트링크 수와 월 조회수(en+es)의 ln(1+x)를 후보 안 최댓값으로 나눠 평균(0~1).
 * 백분위가 아니라 실제 크기를 쓰므로 장소가 많은 도시에서도 상위권이 동점이 되지 않는다.
 */
export function popularity(places) {
  let maxSl = 0, maxPv = 0; // 후보가 수만 곳일 수 있어 펼침 인자 대신 돌면서 센다
  for (const p of places) { maxSl = Math.max(maxSl, p.pop?.sl ?? 0); maxPv = Math.max(maxPv, views(p)); }
  const mSl = Math.log1p(maxSl), mPv = Math.log1p(maxPv);
  return (p) => ((mSl ? Math.log1p(p.pop?.sl ?? 0) / mSl : 0) + (mPv ? Math.log1p(views(p)) / mPv : 0)) / 2;
}

/** 다양성 제한(E2 4절 4항): 같은 첫 범주가 RUN_MAX곳 이어지면 다음 곳을 미뤘다가 다른 범주가 나온 뒤 다시 끼운다. 앞에서 n곳 */
export function diversify(sorted, n, runMax = RUN_MAX) {
  const out = [], wait = [];
  let last = null, run = 0;
  const push = (s) => { const c = s.p.cat[0]; run = c === last ? run + 1 : 1; last = c; out.push(s); };
  const blocked = (s) => s.p.cat[0] === last && run >= runMax;
  for (const s of sorted) {
    if (out.length >= n) break;
    if (blocked(s)) { wait.push(s); continue; }
    push(s);
    while (wait.length && out.length < n && !blocked(wait[0])) push(wait.shift());
  }
  for (const s of wait) { if (out.length >= n) break; out.push(s); } // 한 범주뿐이면 그대로 잇는다
  return out;
}

/**
 * 추천 목록(R-06, E2 4절 4항, D-049): 대표 명소 묶음(취향과 무관, 인기 점수순)과 취향 추천 묶음(고른 취향 범주, 인기 점수순).
 * 수는 dayCapacity×days. 대표 명소의 몫은 BUNDLE_SHARE[balance](올림), 취향을 고르지 않았으면 전부 대표 명소.
 * 묶음에 드는 곳은 점수로 정하고, 같은 범주가 이어지지 않게 하는 제한(diversify)은 묶음 안의 순서에만 쓴다.
 * 돌려주는 배열은 대표 명소가 앞, 취향 추천이 뒤다. 각 항목: { p, score, bundle: "top"|"taste", reasons, match, her, landmark }
 */
export function recommend(places, { tastes = [], balance = "balance", dayCapacity = 4, days = 1, limit } = {}) {
  const pop = popularity(places), sel = new Set(tastes);
  const scored = places.map((p) => ({ p, raw: pop(p), match: p.cat.some((c) => sel.has(c)), her: p.her && p.her.length ? 1 : 0, landmark: isForeignLandmark(p, LANDMARK_TH) }))
    .sort((a, b) => b.raw - a.raw || String(a.p.id).localeCompare(String(b.p.id)));
  const n = Math.min(scored.length, limit ?? dayCapacity * Math.max(1, days));
  const nTop = sel.size ? Math.ceil(n * (BUNDLE_SHARE[balance] ?? BUNDLE_SHARE.balance)) : n;
  // 묶음에 드는 곳은 인기 점수로 정하고, 다양성 제한은 묶음 안의 순서에만 쓴다(덜 알려진 곳이 범주가 다르다는 이유로 끼어들지 않게)
  const top = diversify(scored.slice(0, nTop), nTop);
  const used = new Set(top.map((s) => s.p.id));
  const taste = diversify(scored.filter((s) => s.match && !used.has(s.p.id)).slice(0, n - top.length), n - top.length);
  for (const s of taste) used.add(s.p.id);
  const fill = top.length + taste.length < n ? scored.filter((s) => !used.has(s.p.id)).slice(0, n - top.length - taste.length) : []; // 취향에 맞는 곳이 모자라면 인기순으로 채운다
  const item = (bundle) => ({ p, raw, match, her, landmark }) => ({ p, score: Math.round(raw * 1000) / 1000, bundle, match, her, landmark,
    reasons: [bundle === "top" ? "대표 명소" : "취향 일치", ...(bundle === "top" && match && sel.size ? ["취향 일치"] : []), ...(her ? ["유산 지정"] : [])].slice(0, 2) });
  return [...top.map(item("top")), ...fill.map(item("top")), ...taste.map(item("taste"))];
}

/** 추천에 넣는 2등급 범주(식당·카페·시장). 1등급은 모두 후보다 */
export const RECOMMEND_TIER2_CATS = ["restaurant", "cafe", "market"];

/** 여행지 하나의 추천 목록. 탐색 화면과 요약 화면이 같은 목록을 쓰도록 후보 고르기를 한곳에 둔다(D-039) */
export function recommendForDestination(places, opts) {
  return recommend(places.filter((p) => p.tier === 1 || p.cat.some((c) => RECOMMEND_TIER2_CATS.includes(c))), opts);
}

/** 도시 수준 대안(R-06): 대표 명소 중심 세트와 취향 중심 세트 */
export function cityAlternatives(places, opts) {
  return { landmark: recommend(places, { ...opts, balance: "landmark" }), other: recommend(places, { ...opts, balance: "other" }) };
}

/** 장소 수준 대안: 같은 상위 범주, 2km 안, 인기 점수 상위 2개 */
export function placeAlternatives(p, places) {
  const pop = popularity(places);
  return places.filter((q) => q.id !== p.id && q.cat.some((c) => p.cat.includes(c)) && hav(p.lat, p.lon, q.lat, q.lon) <= 2000)
    .map((q) => ({ p: q, score: Math.round(pop(q) * 1000) / 1000, raw: pop(q), dist: hav(p.lat, p.lon, q.lat, q.lon) }))
    .sort((a, b) => b.raw - a.raw || a.dist - b.dist || String(a.p.id).localeCompare(String(b.p.id))).slice(0, 2);
}

export const KNOWN_TH = 0.5;     // 알려진 곳: 인기 점수가 이 값 이상(D-051, 제안값)
export const LONG_LEG_MIN = 240; // 이보다 긴 도시 간 구간에 경고와 "들를 만한 곳"(E2 4절 5항)
export const STOPOVER = { detour: 1.15, minM: 30000, max: 3 }; // 들를 만한 곳: 에움 비율, 양쪽에서 떨어진 거리, 보이는 수(제안값)
export const PERMUTE_MAX = 8;    // 여행지가 이 수까지면 모든 순서를 견준다

/** 알려진 곳의 수(E2 4절 6항). places는 여행지 하나의 1등급 장소. tastes를 주면 그 범주에 드는 곳만 센다 */
export function knownCount(places, tastes = null) {
  const pop = popularity(places), sel = tastes ? new Set(tastes) : null;
  let n = 0;
  for (const p of places) if (pop(p) >= KNOWN_TH && (!sel || p.cat.some((c) => sel.has(c)))) n++;
  return n;
}

/** amount를 무게에 비례한 정수로 나눈다(가장 큰 나머지 방식, 동률은 앞 순서). 무게 합이 0이면 고르게 */
export function shareOut(ids, weights, amount) {
  const n = ids.length; if (!n || amount <= 0) return Object.fromEntries(ids.map((id) => [id, 0]));
  const w = ids.map((id) => Math.max(0, Number(weights[id]) || 0)), sum = w.reduce((a, b) => a + b, 0);
  const raw = w.map((v) => (sum > 0 ? (v / sum) * amount : amount / n)), out = raw.map(Math.floor);
  let left = amount - out.reduce((a, b) => a + b, 0);
  raw.map((v, i) => [v - Math.floor(v), i]).sort((a, b) => b[0] - a[0] || a[1] - b[1]).forEach(([, i]) => { if (left > 0) { out[i]++; left--; } });
  return Object.fromEntries(ids.map((id, i) => [id, out[i]]));
}

/** 날을 나눈다: 여행지마다 1일을 먼저 주고 남은 날을 무게에 비례해 나눈다. 날이 여행지 수보다 적으면 앞에서부터 1일씩 */
export function splitDays(ids, weights, total) {
  const n = ids.length; if (!n) return {};
  if (total <= n) return Object.fromEntries(ids.map((id, i) => [id, i < total ? 1 : 0]));
  const extra = shareOut(ids, weights, total - n);
  return Object.fromEntries(ids.map((id) => [id, 1 + extra[id]]));
}

/**
 * 여행지별 기본 일수(E2 4절 6항, D-051). 고른 장소를 먼저 반영한다.
 * order: 여행지 순서, picked: {여행지: 고른 장소 수}, known: {여행지: 알려진 곳 수}, fixed: {여행지: 사용자가 정한 일수}.
 * 돌려주는 값: { days: {여행지: 일수}(합은 totalDays), need: {여행지: 고른 장소에 필요한 일수}, over: 고른 장소가 일정보다 많은가 }
 */
export function defaultDays({ order, totalDays, picked = {}, known = {}, fixed = {}, dayCapacity = 4 }) {
  const days = {}, free = [];
  let remain = totalDays;
  for (const id of order) { if (fixed[id] != null) { days[id] = Math.max(0, Number(fixed[id]) || 0); remain -= days[id]; } else free.push(id); }
  remain = Math.max(0, remain);
  const need = Object.fromEntries(order.map((id) => [id, (picked[id] || 0) > 0 ? Math.ceil(picked[id] / dayCapacity) : 0]));
  const pk = free.filter((id) => need[id] > 0), un = free.filter((id) => need[id] === 0);
  const sumNeed = pk.reduce((s, id) => s + need[id], 0);
  if (sumNeed + un.length > remain) Object.assign(days, splitDays(free, Object.fromEntries(free.map((id) => [id, need[id] || 1])), remain)); // 날이 모자라면 필요 일수에 비례해 줄인다
  else if (un.length) { for (const id of pk) days[id] = need[id]; Object.assign(days, splitDays(un, known, remain - sumNeed)); } // 남는 날은 아직 고르지 않은 여행지에
  else { const extra = shareOut(pk, picked, remain - sumNeed); for (const id of pk) days[id] = need[id] + extra[id]; }   // 모두 골랐으면 고른 수에 비례해 더
  return { days, need, over: order.some((id) => need[id] > (days[id] || 0)) };
}

/** 일수를 숙박 일수로: 일정은 여행지마다 숙박 일수만큼 날짜를 쓰고 마지막 여행지가 남은 날을 쓰므로, 마지막만 하루 적다 */
export function daysToNights(order, days) {
  return Object.fromEntries(order.map((id, i) => [id, Math.max(0, (days[id] || 0) - (i === order.length - 1 ? 1 : 0))]));
}

/** 이동 시간 합이 가장 작은 여행지 순서. 첫 여행지는 그대로 둔다. legMin(a, b): 두 여행지 사이의 분. 같으면 원래 순서를 지킨다 */
export function shortestOrder(order, legMin) {
  const n = order.length; if (n <= 2) return [...order];
  const cost = (o) => { let s = 0; for (let i = 1; i < o.length; i++) s += legMin(o[i - 1], o[i]); return s; };
  let best = [...order], bc = cost(best);
  const first = order[0], rest = order.slice(1);
  if (n <= PERMUTE_MAX) {
    const walk = (left, acc) => {
      if (!left.length) { const o = [first, ...acc], c = cost(o); if (c < bc - 1e-9) { bc = c; best = o; } return; }
      for (let i = 0; i < left.length; i++) walk([...left.slice(0, i), ...left.slice(i + 1)], [...acc, left[i]]);
    };
    walk(rest, []);
    return best;
  }
  // 여행지가 많으면 가까운 곳부터 잇고(nearest neighbour) 두 구간 바꾸기(2-opt)로 다듬는다
  const o = [first], left = [...rest];
  while (left.length) { let bi = 0; for (let i = 1; i < left.length; i++) if (legMin(o[o.length - 1], left[i]) < legMin(o[o.length - 1], left[bi]) - 1e-9) bi = i; o.push(left.splice(bi, 1)[0]); }
  let cur = o, cc = cost(cur);
  for (let pass = 0, improved = true; improved && pass < 50; pass++) {
    improved = false;
    for (let i = 1; i < n - 1; i++) for (let j = i + 1; j < n; j++) {
      const cand = [...cur.slice(0, i), ...cur.slice(i, j + 1).reverse(), ...cur.slice(j + 1)], c = cost(cand);
      if (c < cc - 1e-9) { cur = cand; cc = c; improved = true; }
    }
  }
  return cc < bc - 1e-9 ? cur : best;
}

/** 들를 만한 곳(E2 4절 5항): 두 여행지를 잇는 길 가까이 있는 다른 여행지. 섬이 끼면 없다. 참고 순위순 */
export function stopovers(a, b, destinations, exclude = []) {
  if (!a || !b || a.kind === "island" || b.kind === "island") return [];
  const ex = new Set(exclude), d = hav(a.lat, a.lon, b.lat, b.lon);
  return destinations.filter((c) => c.dest && c.kind !== "island" && !ex.has(c.id) && c.id !== a.id && c.id !== b.id)
    .map((c) => ({ c, da: hav(a.lat, a.lon, c.lat, c.lon), db: hav(c.lat, c.lon, b.lat, b.lon) }))
    .filter((x) => x.da > STOPOVER.minM && x.db > STOPOVER.minM && x.da + x.db <= d * STOPOVER.detour)
    .sort((x, y) => (x.c.dest.rank ?? 9999) - (y.c.dest.rank ?? 9999) || x.c.id.localeCompare(y.c.id)).slice(0, STOPOVER.max).map((x) => x.c);
}

/**
 * 전체 일정 대안(R-06, E2 4절 5항, D-051). 안 하나는 기준 하나와 그 기준에 맞춘 순서·일수·추천 기준의 조합이다.
 * leg(a, b): 두 여행지 사이의 가장 빠른 이동 { mode, min, estimate }. cityOf(id): 여행지 레코드(들를 만한 곳에 쓴다).
 * 돌려주는 값: [{ key, title, basis, order, days, nights, balance, legs, travelMin, estimateLegs, longLegs, overPicked, same }]. 여행지가 한 곳이면 빈 배열
 */
export function tripAlternatives({ order, totalDays, picked = {}, known = {}, tasteKnown = {}, fixed = {}, tastes = [], leg, dayCapacity = 4, destinations = [], cityOf = () => null }) {
  if (order.length < 2) return [];
  const memo = new Map();
  const legC = (a, b) => { const k = a + ">" + b; if (!memo.has(k)) memo.set(k, leg(a, b) || { mode: null, min: 0, estimate: true }); return memo.get(k); };
  const make = (key, title, basis, o, days, balance) => {
    const legs = o.slice(1).map((id, i) => { const l = legC(o[i], id); return { from: o[i], to: id, mode: l.mode, min: l.min, estimate: !!l.estimate }; });
    const longLegs = legs.filter((l) => l.min > LONG_LEG_MIN).map((l) => ({ ...l, stopovers: stopovers(cityOf(l.from), cityOf(l.to), destinations, o).map((c) => c.id) }));
    const overPicked = Object.fromEntries(o.map((id) => [id, Math.max(0, (picked[id] || 0) - (days[id] || 0) * dayCapacity)]).filter(([, v]) => v > 0));
    return { key, title, basis, order: o, days, nights: daysToNights(o, days), balance, legs, travelMin: legs.reduce((s, l) => s + l.min, 0), estimateLegs: legs.filter((l) => l.estimate).length, longLegs, overPicked };
  };
  const baseDays = defaultDays({ order, totalDays, picked, known, fixed, dayCapacity }).days;
  const short = shortestOrder(order, (a, b) => legC(a, b).min);
  const out = [
    make("base", "기본안", "고른 순서와 기본 일수", order, baseDays, "balance"),
    make("move", "이동 최소안", "도시 간 이동 시간을 줄인다", short, baseDays, "balance"),
    make("landmark", "대표 명소안", "알려진 곳이 많은 여행지에 더 머문다", short, splitDays(short, known, totalDays), "landmark"),
  ];
  if (tastes.length) out.push(make("taste", "취향안", "고른 취향에 맞는 곳이 많은 여행지에 더 머문다", short, splitDays(short, tasteKnown, totalDays), "other"));
  const sig = (a) => a.order.join(",") + "|" + a.order.map((id) => a.days[id]).join(",");
  return out.map((a, i) => ({ ...a, same: i > 0 && sig(a) === sig(out[0]) }));
}

/** 숙박 구역(R-10): 선택·추천 장소의 중앙값 좌표에서 1.5km 안 구역 중 숙박 수 상위 3 */
export function lodgingZones(city, focusPlaces) {
  const pts = focusPlaces.length ? focusPlaces : [{ lat: city.lat, lon: city.lon }];
  const med = (xs) => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
  const lat = med(pts.map((p) => p.lat)), lon = med(pts.map((p) => p.lon));
  // 섬 여행지(D-030)는 장소가 섬 전체에 흩어져 있으므로 거리 제한 없이 숙박이 많은 구역을 제안한다
  const island = city.kind === "island";
  const zones = (city.districts || []).map((d) => ({ ...d, dist: hav(lat, lon, d.lat, d.lon) })).filter((d) => island ? d.lodging > 0 : d.dist <= 1500)
    .sort((a, b) => b.lodging - a.lodging || a.dist - b.dist).slice(0, 3)
    .map((d) => ({ id: d.id, name: d.n, kind: d.kind, lodging: d.lodging, dist: Math.round(d.dist), reason: `숙박 ${d.lodging}곳 · 추천 장소 중심에서 ${d.dist >= 1000 ? (d.dist / 1000).toFixed(1) + "km" : Math.round(d.dist) + "m"}` }));
  return { center: { lat, lon }, zones, fallback: zones.length === 0 ? { lat: city.lat, lon: city.lon, radius: 1000, reason: "구역 데이터 없음. 도시 중심 반경 1km" } : null };
}

/** 예약 필요 여부(R-18, E2 4절 7항): 클로드 제안 규칙. 사용자가 확정한다. */
export function reservationHint(p, { pvTop10 = 0 } = {}) {
  const paid = p.price && !p.price.free && (p.price.eur ?? 0) > 0;
  const kind = (c) => p.cat.includes(c);
  const views = (p.pop?.pv?.en ?? 0) + (p.pop?.pv?.es ?? 0);
  if (p.osm_tags?.reservation === "required") return { level: "required", label: "예약 필요", reason: "OSM reservation=required" };
  if (paid && (kind("museum") || kind("heritage")) && ((p.her && p.her.length) || (pvTop10 && views >= pvTop10))) return { level: "recommended", label: "예약 권장", reason: "유료 입장이고 박물관·유적이며 유산 지정 또는 조회수 상위" };
  if (kind("restaurant") && p.price?.tier === "고가") return { level: "recommended", label: "예약 권장", reason: "고가 식당" };
  return { level: "none", label: "불필요(추정)", reason: "규칙에 해당 없음" };
}
