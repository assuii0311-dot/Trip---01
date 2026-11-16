import { test } from "node:test";
import assert from "node:assert/strict";
import { profile, popularity, diversify, recommend, cityAlternatives, placeAlternatives, cityNights, lodgingZones, reservationHint, BUNDLE_SHARE } from "../../app/src/engines/e2.js";

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
test("popularity: 실제 크기의 로그 비율, 0~1, 큰 도시에서도 상위권이 동점이 아니다 (D-049)", () => {
  const pop = popularity(P);
  assert.equal(pop(P[0]), 1); assert.equal(pop(P[5]), 0); // 사이트링크와 조회수가 모두 가장 큰 곳이 1, 둘 다 0이면 0
  assert.ok(pop(P[3]) > pop(P[1]) && pop(P[1]) > pop(P[2]) && pop(P[2]) > pop(P[4]) && pop(P[4]) > pop(P[6]));
  // 예전 백분위 방식은 장소가 수천 곳이면 상위권이 같은 값이 됐다. 지금은 5,000곳 가운데 위 20곳의 점수가 모두 다르다
  const many = Array.from({ length: 5000 }, (_, i) => mk("m" + i, "heritage", 1 + (i % 200), 10 * (i + 1), 5 * (i + 1)));
  const top = many.map(popularity(many)).sort((a, b) => b - a).slice(0, 20);
  assert.equal(new Set(top).size, 20);
  assert.equal(popularity([])({ pop: {} }), 0);
});
test("diversify: 같은 첫 범주 3곳 뒤에는 다른 범주가 나올 때까지 미뤘다가 다시 끼운다", () => {
  const s = (id, cat) => ({ p: { id, cat: [cat] } });
  const L = [s("a1", "A"), s("a2", "A"), s("a3", "A"), s("a4", "A"), s("a5", "A"), s("b1", "B"), s("a6", "A"), s("c1", "C")];
  assert.deepEqual(diversify(L, 8).map((x) => x.p.id), ["a1", "a2", "a3", "b1", "a4", "a5", "a6", "c1"]);
  assert.deepEqual(diversify(L, 5).map((x) => x.p.id), ["a1", "a2", "a3", "b1", "a4"]);
  assert.deepEqual(diversify(L.slice(0, 5), 5).map((x) => x.p.id), ["a1", "a2", "a3", "a4", "a5"]); // 한 범주뿐이면 그대로 잇는다
});
test("recommend: 대표 명소와 취향 추천의 두 묶음, 수는 하루 수용 × 일수, 결정적 (D-049)", () => {
  const r1 = recommend(P, { tastes: ["museum"], dayCapacity: 4, days: 1 });
  assert.deepEqual(r1.map((x) => [x.p.id, x.bundle]), [["prado", "top"], ["palacio", "top"], ["reina", "taste"], ["thyssen", "taste"]]);
  assert.deepEqual(r1.map((x) => x.p.id), recommend(P, { tastes: ["museum"], dayCapacity: 4, days: 1 }).map((x) => x.p.id));
  assert.equal(r1[0].score, 1); assert.deepEqual(r1[0].reasons, ["대표 명소", "취향 일치"]); assert.deepEqual(r1[1].reasons, ["대표 명소", "유산 지정"]); assert.deepEqual(r1[2].reasons, ["취향 일치", "유산 지정"]);
  assert.ok(r1[0].landmark);
  assert.equal(recommend(P, { tastes: ["museum"], dayCapacity: 4, days: 2 }).length, P.length); // 후보보다 많이 추천하지 않는다(8곳 요청, 후보 7곳)
  assert.equal(recommend(P, { tastes: ["museum"], dayCapacity: 2, days: 3 }).length, 6); // 1.5배를 곱하지 않는다
  // 취향을 고르지 않으면 전부 대표 명소이고 인기 점수순이다
  const none = recommend(P, { tastes: [], dayCapacity: 4, days: 1 });
  assert.deepEqual(none.map((x) => [x.p.id, x.bundle]), [["prado", "top"], ["palacio", "top"], ["reina", "top"], ["thyssen", "top"]]);
});
test("recommend: 묶음의 몫은 추천 기준으로 정하고, 취향에 맞는 곳이 모자라면 인기순으로 채운다", () => {
  assert.deepEqual(BUNDLE_SHARE, { landmark: 0.75, balance: 0.5, other: 0.25 });
  const count = (balance) => recommend(P, { tastes: ["museum", "heritage"], balance, limit: 4 }).filter((x) => x.bundle === "top").length;
  assert.equal(count("landmark"), 3); assert.equal(count("balance"), 2); assert.equal(count("other"), 1);
  const r = recommend(P, { tastes: ["park"], balance: "other", limit: 4 }); // 공원은 한 곳뿐이라 나머지 두 자리는 대표 명소로 채운다
  assert.deepEqual(r.map((x) => [x.p.id, x.bundle]), [["prado", "top"], ["palacio", "top"], ["reina", "top"], ["retiro", "taste"]]);
  // 취향을 하나만 골라도 취향 묶음은 그 범주로 찬다(예전에는 연속 3곳 제한 때문에 3곳뿐이었다)
  const mus = Array.from({ length: 12 }, (_, i) => mk("mu" + i, "museum", 30 - i, 3000 - i * 100, 1000));
  const her = Array.from({ length: 12 }, (_, i) => mk("he" + i, "heritage", 90 - i, 9000 - i * 100, 3000));
  const rr = recommend([...mus, ...her], { tastes: ["museum"], limit: 12 });
  assert.equal(rr.filter((x) => x.bundle === "taste").length, 6); assert.ok(rr.filter((x) => x.bundle === "taste").every((x) => x.p.cat[0] === "museum"));
  assert.ok(rr.filter((x) => x.bundle === "top").every((x) => x.p.cat[0] === "heritage"));
});
test("cityAlternatives: 대표 명소 중심 세트와 취향 중심 세트는 묶음의 몫이 다르다", () => {
  const alt = cityAlternatives(P, { tastes: ["park", "cafe"], limit: 4 });
  assert.equal(alt.landmark[0].p.id, "prado"); assert.equal(alt.other[0].p.id, "prado");
  assert.equal(alt.landmark.filter((x) => x.bundle === "taste").length, 1); assert.equal(alt.other.filter((x) => x.bundle === "taste").length, 2); // 공원·카페는 두 곳뿐
});
test("placeAlternatives: 같은 범주 2km 안 인기 점수 상위 2", () => {
  const alts = placeAlternatives(P[0], P);
  assert.deepEqual(alts.map((a) => a.p.id), ["reina", "thyssen"]); assert.ok(alts[0].score > alts[1].score);
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
test("lodgingZones: 섬 여행지는 거리 제한 없이 숙박 많은 구역(D-030)", () => {
  const isl = { kind: "island", lat: 39.57, lon: 2.65, districts: [{ id: "d1", n: "Palma Centre", lat: 39.57, lon: 2.65, kind: "suburb", lodging: 40 }, { id: "d2", n: "Alcúdia", lat: 39.85, lon: 3.12, kind: "suburb", lodging: 90 }, { id: "d3", n: "Empty", lat: 39.6, lon: 2.7, kind: "suburb", lodging: 0 }] };
  const z = lodgingZones(isl, [{ lat: 39.57, lon: 2.65 }]);
  assert.deepEqual(z.zones.map((x) => x.id), ["d2", "d1"]); assert.ok(z.zones[0].reason.includes("km")); assert.equal(z.fallback, null);
  assert.deepEqual(lodgingZones({ ...isl, kind: undefined }, [{ lat: 39.57, lon: 2.65 }]).zones.map((x) => x.id), ["d1"]);
});

import { recommendForDestination, RECOMMEND_TIER2_CATS } from "../../app/src/engines/e2.js";
test("recommendForDestination: 1등급 전부와 2등급의 식당·카페·시장만 후보 (D-039)", () => {
  const mk = (id, tier, cat, sl) => ({ id, tier, cat: [cat], pop: { sl, pv: null, en_share: null }, lat: 40, lon: -3, her: [] });
  const places = [mk("a", 1, "museum", 30), mk("b", 2, "restaurant", 0), mk("c", 2, "shop", 0), mk("d", 2, "cafe", 0)];
  const ids = recommendForDestination(places, { tastes: ["museum", "restaurant", "cafe", "shop"], limit: 10 }).map((r) => r.p.id).sort();
  assert.deepEqual(ids, ["a", "b", "d"]); assert.ok(RECOMMEND_TIER2_CATS.includes("market"));
});
