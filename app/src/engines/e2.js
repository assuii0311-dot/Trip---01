// E2 추천 엔진(docs/engines/E2-recommendation.md, 설계 동의 D-025. 점수 가중치는 D-024).
// 순수 함수만 둔다. 입력은 E1 기준 데이터와 여행 입력, 출력은 설계 문서 3절의 구조.
import { hav, isForeignLandmark } from "../data/places.js";

export const WEIGHTS = { match: 0.5, rep: 0.4, heritage: 0.1 }; // D-024
export const W_SELECTED = 1.0, W_UNSELECTED = 0.3; // D-025 (f)
export const LANDMARK_TH = { share: 0.5, sitelinks: 10 }; // D-025 (d)

/** 선호 분석(R-05): 범주 가중치와 프로필 문장. budget·dayCapacity는 E6·E4 값과 맞춘다. */
export function profile(trip, categories, dayCapacity = 4) {
  const sel = new Set(trip.tastes || []);
  const weights = Object.fromEntries(categories.map((c) => [c.id, sel.size === 0 ? W_SELECTED : sel.has(c.id) ? W_SELECTED : W_UNSELECTED]));
  const names = categories.filter((c) => sel.has(c.id)).map((c) => c.ko);
  const budget = { low: "저가", mid: "중가", high: "고가" }[trip.budget] || "중가";
  const sentence = `${names.length ? names.slice(0, 3).join("·") + " 중심" : "모든 범주 고르게"}, ${budget}, 하루 ${dayCapacity}곳 안팎`;
  return { weights, sentence, budget, dayCapacity, tastes: [...sel] };
}

/** 도시 안 백분위(0~1). 값이 같으면 같은 백분위. 결정적. */
export function percentiles(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  return (v) => (n <= 1 ? 1 : sorted.findIndex((x) => x >= v) / (n - 1));
}

/** 대표성: 사이트링크와 조회수(en+es)를 각각 도시 안 백분위로 바꿔 평균 */
export function representativeness(places) {
  const sl = percentiles(places.map((p) => p.pop?.sl ?? 0));
  const pv = percentiles(places.map((p) => (p.pop?.pv?.en ?? 0) + (p.pop?.pv?.es ?? 0)));
  return (p) => (sl(p.pop?.sl ?? 0) + pv((p.pop?.pv?.en ?? 0) + (p.pop?.pv?.es ?? 0))) / 2;
}

/** "그 밖의 장소" 비중(D-025 (b)): landmark 그대로, balance 0.6배, other 반전(1-rep). E2 4절 3항의 "부호와 크기" */
export function balancedRep(rep, balance) {
  if (balance === "other") return 1 - rep;
  if (balance === "balance") return 0.6 * rep;
  return rep;
}

/** 장소 점수(D-024): 0.50×취향 일치 + 0.40×대표성 + 0.10×유산 지정. 근거 항목 두 개를 함께 돌려준다. */
export function scorePlace(p, weights, rep, balance = "balance") {
  const match = Math.max(0, ...p.cat.map((c) => weights[c] ?? W_UNSELECTED));
  const r = balancedRep(rep, balance);
  const her = p.her && p.her.length ? 1 : 0;
  const terms = [["취향 일치", WEIGHTS.match * match], ["대표성", WEIGHTS.rep * r], ["유산 지정", WEIGHTS.heritage * her]];
  const score = terms.reduce((s, [, v]) => s + v, 0);
  const reasons = terms.filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 2).map(([k]) => k);
  return { score: Math.round(score * 1000) / 1000, reasons, match, rep: r, her };
}

/** 추천 목록(R-06): 도시의 장소를 점수순으로, 같은 범주 연속 3개 제한. 수는 cap×nights×1.5 */
export function recommend(places, { weights, balance = "balance", dayCapacity = 4, nights = 1, limit } = {}) {
  const rep = representativeness(places);
  const scored = places.map((p) => ({ p, ...scorePlace(p, weights, rep(p), balance), landmark: isForeignLandmark(p, LANDMARK_TH) }))
    .sort((a, b) => b.score - a.score || String(a.p.id).localeCompare(String(b.p.id)));
  const n = limit ?? Math.ceil(dayCapacity * Math.max(1, nights) * 1.5);
  const out = [], deferred = [];
  let lastCat = null, run = 0;
  for (const s of scored) {
    if (out.length >= n) break;
    const c = s.p.cat[0];
    if (c === lastCat && run >= 3) { deferred.push(s); continue; }
    out.push(s); run = c === lastCat ? run + 1 : 1; lastCat = c;
  }
  for (const s of deferred) { if (out.length >= n) break; out.push(s); }
  return out;
}

/** 도시 수준 대안(R-06): 대표 명소 중심 세트와 그 밖 중심 세트 */
export function cityAlternatives(places, opts) {
  return { landmark: recommend(places, { ...opts, balance: "landmark" }), other: recommend(places, { ...opts, balance: "other" }) };
}

/** 장소 수준 대안: 같은 상위 범주, 2km 안, 점수 상위 2개 */
export function placeAlternatives(p, places, weights, balance = "balance") {
  const rep = representativeness(places);
  return places.filter((q) => q.id !== p.id && q.cat.some((c) => p.cat.includes(c)) && hav(p.lat, p.lon, q.lat, q.lon) <= 2000)
    .map((q) => ({ p: q, ...scorePlace(q, weights, rep(q), balance), dist: hav(p.lat, p.lon, q.lat, q.lon) }))
    .sort((a, b) => b.score - a.score || a.dist - b.dist).slice(0, 2);
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
  const zones = (city.districts || []).map((d) => ({ ...d, dist: hav(lat, lon, d.lat, d.lon) })).filter((d) => d.dist <= 1500)
    .sort((a, b) => b.lodging - a.lodging || a.dist - b.dist).slice(0, 3)
    .map((d) => ({ id: d.id, name: d.n, kind: d.kind, lodging: d.lodging, dist: Math.round(d.dist), reason: `숙박 ${d.lodging}곳 · 추천 장소 중심에서 ${Math.round(d.dist)}m` }));
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
