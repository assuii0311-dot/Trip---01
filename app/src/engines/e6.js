// E6 비용 추정 엔진(docs/engines/E6-cost.md, 설계 동의 D-025, 범위 D-021 ③·D-024). 순수 함수.
// 전국 기본 분포(사실: docs/02-poc-results.md 26절, Wikivoyage 가격 필드 집계)
export const NATIONAL = { see: { median: 5, q: [2.5, 8] }, eat: { median: 19, q: [10, 30] }, drink: { median: 10, q: [6, 10] }, sleep: { median: 90, q: [50, 135] } };
export const TIER_NAME = { low: "저가", mid: "중가", high: "고가" };
export const FREE_CATS = new Set(["square", "beach", "nature", "park"]); // D-025 (c)
const MEAL_TIER_SHIFT = { low: "low", mid: "mid", high: "high" };

/** 끼니 수와 조정(E6 4절 2항): 기본 2끼, 가볍게는 한 등급 아래, 간식 +1(저가 반값), 반주는 끼니마다 drink 중앙값 */
export function mealPlan(meals = [], budget = "mid") {
  const order = ["low", "mid", "high"];
  let tier = budget;
  if (meals.includes("light")) tier = order[Math.max(0, order.indexOf(budget) - 1)];
  return { count: 2, tier, snack: meals.includes("snack"), drink: meals.includes("drink") };
}

/** 도시 가격 분포에서 등급별 끼니 금액 범위. 도시 값이 없으면 전국 */
export function mealRange(city, tier) {
  const prof = city?.price_profile?.eat;
  const base = prof && prof.median ? { median: prof.median, q: prof.q || [prof.median * 0.6, prof.median * 1.5] } : NATIONAL.eat;
  const f = { low: 0.65, mid: 1.0, high: 1.7 }[tier] ?? 1.0; // 추정: 등급별 배율
  return { min: Math.round(base.q[0] * f), max: Math.round(base.q[1] * f), basis: prof && prof.median ? `도시 식당 ${prof.n}건 Wikivoyage 가격` : "전국 Wikivoyage 식당 가격 1,819건", confidence: "estimate" };
}

export function lodgingRange(city, tier, nights, people) {
  const prof = city?.price_profile?.sleep;
  const base = prof && prof.median ? { median: prof.median, q: prof.q || [prof.median * 0.6, prof.median * 1.5] } : NATIONAL.sleep;
  const f = { low: 0.65, mid: 1.0, high: 1.7 }[tier] ?? 1.0;
  const rooms = Math.max(1, Math.ceil(people / 2)); // D-025 (b) 2인 1실
  return { min: Math.round(base.q[0] * f * nights * rooms), max: Math.round(base.q[1] * f * nights * rooms), basis: `${prof && prof.median ? `도시 숙박 ${prof.n}건` : "전국 숙박 2,029건"} Wikivoyage 가격 · ${nights}박 × 객실 ${rooms}`, confidence: "estimate" };
}

/** 입장료(E6 4절 1항): 장소 값 → 무료 범주 0 → 범주 분포(전국) */
export function entryFee(p, people) {
  if (p.price && p.price.free) return { min: 0, max: 0, basis: `${p.price.src === "wikivoyage" ? "Wikivoyage" : "OSM"} 무료 표기`, confidence: "computed" };
  if (p.price && p.price.eur != null && p.price.eur > 0) return { min: Math.round(p.price.eur * people), max: Math.round(p.price.eur * people), basis: `${p.price.src === "wikivoyage" ? "Wikivoyage 참고값" : "OSM"} €${p.price.eur} × ${people}명`, confidence: "computed" };
  if (p.cat.some((c) => FREE_CATS.has(c)) && !p.cat.some((c) => ["museum", "activity"].includes(c))) return { min: 0, max: 0, basis: "광장·해변·자연·공원은 무료로 가정(D-025)", confidence: "estimate" };
  if (p.cat.some((c) => ["restaurant", "cafe", "market", "lodging"].includes(c))) return null;
  return { min: Math.round(NATIONAL.see.q[0] * people), max: Math.round(NATIONAL.see.q[1] * people), basis: `전국 볼거리 입장료 사분위 €${NATIONAL.see.q[0]}~${NATIONAL.see.q[1]} × ${people}명`, confidence: "estimate" };
}

/** 교통비(E6 4절 4항): 1회권 요금이 있는 도시만. 택시는 요금표가 있으면 */
export function transitCost(city, transitRides, taxiRides, taxiKmTotal, people, fares) {
  const fare = (fares || []).find((f) => f.price > 0);
  const out = { transit: null, taxi: null };
  if (fare) out.transit = { min: Math.round(fare.price * transitRides * people), max: Math.round(fare.price * transitRides * people), basis: `1회권 €${fare.price} × ${transitRides}회 × ${people}명 (${fare.feed})`, confidence: "computed" };
  else if (transitRides > 0) out.transit = { min: null, max: null, basis: "요금표 입력 전", confidence: "none" };
  const t = city?.taxi_fare;
  if (t && taxiRides > 0) { const v = taxiRides * Math.max(t.min_eur, t.base_eur + (taxiKmTotal / Math.max(1, taxiRides)) * t.per_km_eur); out.taxi = { min: Math.round(v), max: Math.round(v * t.per_km_eur_night / t.per_km_eur), basis: `기본 €${t.base_eur} + km당 €${t.per_km_eur}(야간 ${t.per_km_eur_night}) × ${taxiRides}회`, confidence: "computed" }; }
  else if (taxiRides > 0) out.taxi = { min: null, max: null, basis: "요금표 입력 전", confidence: "none" };
  return out;
}

/**
 * 일정 전체 비용(E6 3절). itinerary: E4 결과, getPlace, cities(map), trip, faresByCity
 * 반환 {days:[{date, entry, meals, transit, taxi}], total:{entry, meals, lodging, transit, taxi}, notes}
 */
export function estimateCost({ itinerary, getPlace, cityOf, trip, lodging = {}, faresByCity = {} }) {
  const people = Math.max(1, Number(trip.people) || 1);
  const mp = mealPlan(trip.meals, trip.budget);
  const sum = (a, b) => (!a ? b : !b ? a : { min: (a.min ?? 0) + (b.min ?? 0), max: (a.max ?? 0) + (b.max ?? 0) });
  const days = []; const total = { entry: null, meals: null, lodging: null, transit: null, taxi: null }; const notes = new Set();
  for (const d of itinerary.days) {
    const city = cityOf(d.cityId);
    let entry = null; let transitRides = 0, taxiRides = 0, taxiKm = 0;
    for (const it of d.items) {
      if (it.kind !== "place") continue;
      const p = getPlace(it.id); if (!p) continue;
      const fee = entryFee(p, people); if (fee) entry = sum(entry, fee);
      if (it.travel?.mode === "transit") transitRides++;
      if (it.travel?.mode === "taxi") { taxiRides++; taxiKm += (it.travel.m || 0) / 1000; }
    }
    const mr = mealRange(city, mp.tier);
    let meals = { min: mr.min * mp.count * people, max: mr.max * mp.count * people, basis: `${TIER_NAME[mp.tier]} ${mp.count}끼 × ${people}명 · ${mr.basis}`, confidence: "estimate" };
    if (mp.snack) meals = sum(meals, { min: Math.round(mr.min * 0.5 * people), max: Math.round(mr.min * 0.5 * people) });
    if (mp.drink) meals = sum(meals, { min: NATIONAL.drink.median * mp.count * people, max: NATIONAL.drink.median * mp.count * people });
    const tc = transitCost(city, transitRides, taxiRides, taxiKm, people, faresByCity[d.cityId]);
    if (tc.transit?.confidence === "none") notes.add(`${city?.n?.ko || d.cityId}: 대중교통 요금표 입력 전`);
    days.push({ date: d.date, cityId: d.cityId, entry, meals, transit: tc.transit, taxi: tc.taxi });
    total.entry = sum(total.entry, entry); total.meals = sum(total.meals, meals);
    if (tc.transit && tc.transit.min != null) total.transit = sum(total.transit, tc.transit);
    if (tc.taxi && tc.taxi.min != null) total.taxi = sum(total.taxi, tc.taxi);
  }
  for (const [cid, l] of Object.entries(lodging)) { const n = Number(l.nights) || 0; if (n > 0) total.lodging = sum(total.lodging, lodgingRange(cityOf(cid), trip.budget || "mid", n, people)); }
  const grand = ["entry", "meals", "lodging", "transit", "taxi"].reduce((s, k) => sum(s, total[k]), null);
  return { days, total, grand, people, tier: mp.tier, notes: [...notes] };
}
