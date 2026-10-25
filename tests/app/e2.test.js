import { test } from "node:test";
import assert from "node:assert/strict";
import { profile, percentiles, scorePlace, recommend, cityAlternatives, placeAlternatives, cityNights, lodgingZones, reservationHint, WEIGHTS } from "../../app/src/engines/e2.js";

const CATS = [{ id: "museum", ko: "박물관·미술관" }, { id: "heritage", ko: "유적·기념물" }, { id: "cafe", ko: "카페·바" }, { id: "park", ko: "공원·정원" }];
const mk = (id, cat, sl, en, es, her = [], extra = {}) => ({ id, cat: [cat], her, lat: 40.41 + Math.random() * 0, lon: -3.7, pop: { sl, pv: { en, es }, en_share: en + es ? en / (en + es) : null }, ...extra });
const P = [
  mk("prado", "museum", 80, 14000, 8700, ["Q23712"], { lat: 40.4139, lon: -3.6922, price: { eur: 15, free: false } }),
  mk("reina", "museum", 60, 9000, 6000, ["Q23712"], { lat: 40.4080, lon: -3.6945, price: { eur: 12, free: false } }),
  mk("thyssen", "museum", 50, 7000, 5000, [], { lat: 40.4160, lon: -3.6949 }),
  mk("palacio", "heritage", 70, 12000, 9000, ["Q23712"], { lat: 40.4180, lon: -3.7143 }),
  mk("retiro", "park", 40, 6000, 7000, [], { lat: 40.4150, lon: -3.6840 }),
  mk("cafe1", "cafe", 0, 0, 0, [], { lat: 40.4200, lon: -3.7000, ver: false }),
  mk("ermita", "heritage", 0, 5, 300, [], { lat: 40.4300, lon: -3.7100 }),
];

test("profile: 선택 범주 1.0, 비선택 0.3, 미선택이면 전부 1.0", () => {
  const pr = profile({ tastes: ["museum"], budget: "mid" }, CATS);
  assert.equal(pr.weights.museum, 1.0); assert.equal(pr.weights.cafe, 0.3); assert.ok(pr.sentence.includes("박물관·미술관 중심"));
  assert.equal(profile({ tastes: [], budget: "low" }, CATS).weights.cafe, 1.0);
});
test("percentiles: 결정적, 0~1", () => { const f = percentiles([0, 10, 20, 30]); assert.equal(f(0), 0); assert.equal(f(30), 1); assert.equal(f(20), 2 / 3); });
test("scorePlace: 가중치 합 1, 근거 두 개", () => {
  assert.equal(WEIGHTS.match + WEIGHTS.rep + WEIGHTS.heritage, 1);
  const s = scorePlace(P[0], { museum: 1 }, 1, "landmark");
  assert.equal(s.score, 1); assert.deepEqual(s.reasons, ["취향 일치", "대표성"]);
  assert.equal(scorePlace(P[5], { cafe: 0.3 }, 0, "landmark").score, 0.15);
});
test("recommend: 점수순, 같은 범주 연속 3개 제한, 결정적", () => {
  const w = profile({ tastes: ["museum"] }, CATS).weights;
  const r1 = recommend(P, { weights: w, dayCapacity: 4, nights: 1, limit: 5 });
  const r2 = recommend(P, { weights: w, dayCapacity: 4, nights: 1, limit: 5 });
  assert.deepEqual(r1.map((x) => x.p.id), r2.map((x) => x.p.id));
  assert.equal(r1[0].p.id, "prado"); assert.ok(r1[0].landmark);
  const cats = r1.map((x) => x.p.cat[0]); assert.ok(!(cats[0] === cats[1] && cats[1] === cats[2] && cats[2] === cats[3]));
  assert.equal(recommend(P, { weights: w, dayCapacity: 4, nights: 2 }).length, Math.min(P.length, 12));
});
test("cityAlternatives: 그 밖 중심 세트는 대표성 낮은 곳이 앞", () => {
  const w = profile({ tastes: [] }, CATS).weights;
  const alt = cityAlternatives(P, { weights: w, limit: 3 });
  assert.equal(alt.landmark[0].p.id, "prado"); assert.notEqual(alt.other[0].p.id, "prado");
});
test("placeAlternatives: 같은 범주 2km 안 상위 2", () => {
  const alts = placeAlternatives(P[0], P, { museum: 1 });
  assert.deepEqual(alts.map((a) => a.p.id), ["reina", "thyssen"]);
});
test("cityNights: 비례 배분과 남는 밤", () => {
  assert.deepEqual(cityNights({ Q2807: 12, Q1492: 8 }, 7, 4), { Q2807: 4, Q1492: 3 });
  assert.deepEqual(cityNights({ Q2807: 2 }, 3, 4), { Q2807: 3 });
  assert.deepEqual(cityNights({ a: 20, b: 20, c: 20 }, 3, 4), { a: 1, b: 1, c: 1 });
});
test("lodgingZones: 1.5km 안 숙박 수 상위 3, 없으면 도시 중심", () => {
  const city = { lat: 40.4168, lon: -3.7038, districts: [{ id: "d1", n: "Sol", kind: "quarter", lat: 40.417, lon: -3.703, lodging: 104 }, { id: "d2", n: "Letras", kind: "neighbourhood", lat: 40.414, lon: -3.698, lodging: 90 }, { id: "d3", n: "Far", kind: "suburb", lat: 40.47, lon: -3.60, lodging: 300 }] };
  const z = lodgingZones(city, [P[0], P[1], P[2]]);
  assert.deepEqual(z.zones.map((x) => x.id), ["d1", "d2"]); assert.equal(z.fallback, null);
  assert.ok(lodgingZones({ lat: 1, lon: 1, districts: [] }, []).fallback);
});
test("reservationHint: 유료 박물관+유산 → 권장, 고가 식당 → 권장, 그 외 불필요", () => {
  assert.equal(reservationHint(P[0]).level, "recommended");
  assert.equal(reservationHint({ cat: ["restaurant"], price: { tier: "고가", eur: 40 }, pop: {} }).level, "recommended");
  assert.equal(reservationHint(P[4]).level, "none");
  assert.equal(reservationHint({ cat: ["cafe"], pop: {}, osm_tags: { reservation: "required" } }).level, "required");
});
