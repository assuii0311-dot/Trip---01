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

/** 숙박 일수(R-10, E2 4절 6항): ceil(추천 수 ÷ 하루 수용), 최소 1, 합이 기간을 넘으면 비례 축소 */
export function cityNights(recommendedCounts, totalNights, dayCapacity = 4) {
  const ids = Object.keys(recommendedCounts);
  if (!ids.length || totalNights <= 0) return {};
  let nights = Object.fromEntries(ids.map((id) => [id, Math.max(1, Math.ceil(recommendedCounts[id] / dayCapacity))]));
  let sum = Object.values(nights).reduce((a, b) => a + b, 0);
  if (sum > totalNights) {
    nights = Object.fromEntries(ids.map((id) => [id, Math.max(1, Math.floor((nights[id] / sum) * totalNights))]));
    sum = Object.values(nights).reduce((a, b) => a + b, 0);
  }
  // 남는 밤은 추천 수가 많은 도시부터 하나씩
  const order = [...ids].sort((a, b) => recommendedCounts[b] - recommendedCounts[a] || a.localeCompare(b));
  for (let i = 0; sum < totalNights && order.length; i = (i + 1) % order.length) { nights[order[i]]++; sum++; }
  return nights;
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
