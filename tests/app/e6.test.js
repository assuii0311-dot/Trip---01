import { test } from "node:test";
import assert from "node:assert/strict";
import { mealPlan, mealRange, lodgingRange, entryFee, transitCost, estimateCost, NATIONAL } from "../../app/src/engines/e6.js";

const city = { id: "Q2807", n: { ko: "마드리드" }, price_profile: { eat: { n: 67, median: 11, q: [8, 15] }, sleep: { n: 37, median: 30, q: [17, 55] } }, taxi_fare: null };
test("식사 계획: 가볍게는 한 등급 아래, 간식·반주 표시", () => {
  assert.deepEqual(mealPlan(["light"], "mid"), { count: 2, tier: "low", snack: false, drink: false });
  assert.equal(mealPlan(["snack", "drink"], "high").tier, "high");
});
test("끼니·숙박 범위: 도시 분포 우선, 2인 1실", () => {
  assert.deepEqual([mealRange(city, "mid").min, mealRange(city, "mid").max], [8, 15]);
  assert.equal(mealRange(null, "mid").basis.startsWith("전국"), true);
  const l = lodgingRange(city, "mid", 3, 3); assert.deepEqual([l.min, l.max], [17 * 3 * 2, 55 * 3 * 2]);
});
test("입장료: 장소 값, 무료 범주, 전국 분포, 식당은 없음", () => {
  assert.equal(entryFee({ cat: ["museum"], price: { eur: 15, free: false, src: "wikivoyage" } }, 2).min, 30);
  assert.equal(entryFee({ cat: ["square"], price: null }, 2).max, 0);
  const e = entryFee({ cat: ["heritage"], price: null }, 1); assert.deepEqual([e.min, e.max], [Math.round(NATIONAL.see.q[0]), NATIONAL.see.q[1]]);
  assert.equal(entryFee({ cat: ["restaurant"], price: null }, 1), null);
});
test("교통비: 요금표 있으면 계산, 없으면 입력 전", () => {
  const a = transitCost(city, 3, 0, 0, 2, [{ price: 1.5, feed: "Metro" }]); assert.equal(a.transit.min, 9);
  const b = transitCost(city, 3, 1, 4, 2, []); assert.equal(b.transit.confidence, "none"); assert.equal(b.taxi.confidence, "none");
  const bcn = { taxi_fare: { base_eur: 2.8, per_km_eur: 1.35, per_km_eur_night: 1.66, min_eur: 8 } };
  assert.equal(transitCost(bcn, 0, 2, 10, 2, []).taxi.min, Math.round(2 * Math.max(8, 2.8 + 5 * 1.35)));
});
test("일정 전체 비용 합산", () => {
  const itinerary = { days: [{ date: "d1", cityId: "Q2807", items: [{ kind: "place", id: "a", travel: { mode: "walk" } }, { kind: "place", id: "b", travel: { mode: "transit" } }, { kind: "meal" }] }] };
  const places = { a: { cat: ["museum"], price: { eur: 10, free: false, src: "wikivoyage" } }, b: { cat: ["square"], price: null } };
  const r = estimateCost({ itinerary, getPlace: (id) => places[id], cityOf: () => city, trip: { people: 2, meals: ["normal"], budget: "mid" }, lodging: { Q2807: { nights: 2 } }, faresByCity: {} });
  assert.equal(r.total.entry.min, 20); assert.equal(r.total.meals.min, 8 * 2 * 2); assert.equal(r.total.lodging.min, 17 * 2); assert.equal(r.total.transit, null); assert.ok(r.notes[0].includes("입력 전")); assert.ok(r.grand.max > r.grand.min);
});
