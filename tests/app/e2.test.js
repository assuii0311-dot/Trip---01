import { test } from "node:test";
import assert from "node:assert/strict";
import { profile, popularity, diversify, recommend, cityAlternatives, placeAlternatives, lodgingZones, reservationHint, BUNDLE_SHARE } from "../../app/src/engines/e2.js";

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

// --- 전체 일정 대안과 기본 일수(E2 4절 5·6항, D-051). 고정 입력은 2026-11-16 시험 계산(마드리드·세비야·그라나다·바르셀로나)의 모양을 축약한 것.
import { knownCount, shareOut, splitDays, defaultDays, daysToNights, shortestOrder, stopovers, tripAlternatives, KNOWN_TH, LONG_LEG_MIN } from "../../app/src/engines/e2.js";
test("knownCount: 인기 점수 0.5 이상인 곳, 취향을 주면 그 범주만", () => {
  assert.equal(KNOWN_TH, 0.5);
  assert.equal(knownCount(P), 5); // 카페(0)와 에르미타(조회수 조금)는 빠진다
  assert.equal(knownCount(P, ["museum"]), 3); assert.equal(knownCount(P, ["park", "cafe"]), 1); assert.equal(knownCount([]), 0);
});
test("shareOut/splitDays: 가장 큰 나머지 방식, 여행지마다 1일 보장, 합은 그대로", () => {
  assert.deepEqual(shareOut(["a", "b", "c"], { a: 5, b: 3, c: 2 }, 7), { a: 4, b: 2, c: 1 }); // 3.5·2.1·1.4 → 내림 3·2·1, 남은 1은 나머지가 가장 큰 a
  assert.deepEqual(shareOut(["a", "b"], {}, 3), { a: 2, b: 1 }); assert.deepEqual(shareOut(["a"], { a: 1 }, 0), { a: 0 });
  // 알려진 곳 수(마드리드 119, 세비야 42, 그라나다 21, 바르셀로나 99)로 9일을 나누면 3·2·1·3
  const ids = ["mad", "sev", "gra", "bcn"], known = { mad: 119, sev: 42, gra: 21, bcn: 99 };
  assert.deepEqual(splitDays(ids, known, 9), { mad: 3, sev: 2, gra: 1, bcn: 3 });
  assert.deepEqual(splitDays(ids, {}, 9), { mad: 3, sev: 2, gra: 2, bcn: 2 }); // 무게가 없으면 고르게
  assert.deepEqual(splitDays(ids, known, 4), { mad: 1, sev: 1, gra: 1, bcn: 1 }); assert.deepEqual(splitDays(ids, known, 2), { mad: 1, sev: 1, gra: 0, bcn: 0 });
  assert.deepEqual(splitDays([], known, 5), {});
});
test("defaultDays: 알려진 곳 수로 나누고, 고른 장소는 일수를 늘리기만 한다 (D-051, D-053)", () => {
  const order = ["mad", "sev", "gra", "bcn"], known = { mad: 119, sev: 42, gra: 21, bcn: 99 };
  const d = (picked, extra = {}) => defaultDays({ order, totalDays: 10, known, picked, ...extra });
  // 아무것도 고르지 않았으면 알려진 곳 수에 비례
  assert.deepEqual(d({}).days, { mad: 4, sev: 2, gra: 1, bcn: 3 });
  // 고른 장소가 받은 일수에 들어가면 일수는 그대로다. 장소를 하나만 골라도 그 여행지의 일수가 줄지 않는다(예전 규칙은 마드리드가 1일이 됐다)
  assert.deepEqual(d({ mad: 1 }).days, { mad: 4, sev: 2, gra: 1, bcn: 3 }); assert.deepEqual(d({ mad: 5 }).days, { mad: 4, sev: 2, gra: 1, bcn: 3 });
  const r = d({ mad: 12, sev: 8, gra: 4 });
  assert.deepEqual(r.days, { mad: 4, sev: 2, gra: 1, bcn: 3 }); assert.equal(r.over, false); assert.deepEqual(r.need, { mad: 3, sev: 2, gra: 1, bcn: 0 });
  // 고른 장소가 받은 일수를 넘는 여행지만 늘리고, 늘린 만큼은 여유가 있는 여행지에서 여유에 비례해 줄인다
  assert.deepEqual(d({ gra: 9 }).days, { mad: 3, sev: 2, gra: 3, bcn: 2 });  // 그라나다 1 → 3일. 여유는 마드리드 3, 세비야 1, 바르셀로나 2
  assert.deepEqual(d({ mad: 20 }).days, { mad: 5, sev: 2, gra: 1, bcn: 2 }); // 마드리드 4 → 5일. 여유는 세비야 1, 바르셀로나 2
  assert.deepEqual(d({ mad: 16, sev: 8 }).days, { mad: 4, sev: 2, gra: 1, bcn: 3 }); // 딱 맞으면 그대로
  // 줄이는 쪽은 자기가 고른 장소에 필요한 일수 밑으로 내려가지 않는다
  const k = d({ gra: 9, mad: 16 });
  assert.equal(k.days.mad, 4); assert.equal(k.days.gra, 3); assert.equal(k.days.sev + k.days.bcn, 3); assert.equal(k.over, false);
  // 여유를 다 모아도 모자라면 필요한 일수에 비례해 나누고 알린다
  const o = defaultDays({ order, totalDays: 6, known, picked: { mad: 20, sev: 12, gra: 4 } });
  assert.equal(Object.values(o.days).reduce((a, b) => a + b, 0), 6); assert.equal(o.over, true); assert.ok(o.days.mad >= o.days.sev && o.days.bcn === 1);
  // 숙박 탭에서 직접 정한 일수는 그대로 두고 나머지만 나눈다
  const fx = d({}, { fixed: { bcn: 5 } });
  assert.equal(fx.days.bcn, 5); assert.deepEqual([fx.days.mad, fx.days.sev, fx.days.gra], [2, 2, 1]); // 남은 5일: 1일씩 주고 2일을 119:42:21로
  assert.deepEqual(defaultDays({ order: ["mad"], totalDays: 5, known }).days, { mad: 5 });
  for (const p of [{}, { mad: 1 }, { gra: 9 }, { mad: 20 }, { gra: 9, mad: 16 }]) assert.equal(Object.values(d(p).days).reduce((a, b) => a + b, 0), 10); // 합은 언제나 여행 일수
});
test("daysToNights: 숙박 일수는 마지막 여행지만 하루 적다", () => {
  assert.deepEqual(daysToNights(["a", "b", "c"], { a: 3, b: 2, c: 5 }), { a: 3, b: 2, c: 4 }); assert.deepEqual(daysToNights(["a"], { a: 1 }), { a: 0 });
});
// 도시 간 시간(분). 마드리드에서 세비야·그라나다는 남쪽, 바르셀로나는 동쪽
const LEGS = { "mad>sev": 158, "mad>gra": 200, "mad>bcn": 182, "sev>gra": 157, "sev>bcn": 330, "gra>bcn": 400 };
const legMin = (a, b) => LEGS[a + ">" + b] ?? LEGS[b + ">" + a];
test("shortestOrder: 첫 여행지는 그대로, 이동 합이 가장 작은 순서, 같으면 원래 순서", () => {
  assert.deepEqual(shortestOrder(["mad", "bcn", "gra", "sev"], legMin), ["mad", "bcn", "sev", "gra"]); // 182+330+157=669. 원래 순서는 182+400+157=739
  assert.deepEqual(shortestOrder(["mad", "gra", "sev", "bcn"], legMin), ["mad", "bcn", "sev", "gra"]); // 687 → 669
  assert.deepEqual(shortestOrder(["mad", "bcn", "sev", "gra"], legMin), ["mad", "bcn", "sev", "gra"]); // 이미 가장 짧으면 그대로
  assert.deepEqual(shortestOrder(["sev", "mad"], legMin), ["sev", "mad"]); assert.deepEqual(shortestOrder(["a"], legMin), ["a"]);
  // 여행지가 9곳 이상이면 근사 계산: 한 줄로 늘어선 곳을 뒤섞어 넣어도 줄 순서를 찾는다
  const line = (a, b) => Math.abs(Number(a.slice(1)) - Number(b.slice(1)));
  assert.deepEqual(shortestOrder(["p0", "p5", "p2", "p8", "p1", "p7", "p3", "p9", "p4", "p6"], line), ["p0", "p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"]);
});
test("stopovers: 두 여행지를 잇는 길 가까이의 여행지를 참고 순위순으로, 섬이 끼면 없음", () => {
  const D = [{ id: "mad", lat: 40.42, lon: -3.70, dest: { rank: 2 } }, { id: "gra", lat: 37.18, lon: -3.60, dest: { rank: 6 } },
    { id: "tol", lat: 39.86, lon: -4.02, dest: { rank: 21 } }, { id: "jae", lat: 37.77, lon: -3.79, dest: { rank: 80 } }, { id: "ube", lat: 38.01, lon: -3.37, dest: { rank: 143 } },
    { id: "bcn", lat: 41.38, lon: 2.18, dest: { rank: 1 } }, { id: "near", lat: 40.45, lon: -3.69, dest: { rank: 3 } }, { id: "nodest", lat: 39.0, lon: -3.7 }, { id: "isl", kind: "island", lat: 39.57, lon: 2.65, dest: { rank: 4 } }];
  assert.deepEqual(stopovers(D[0], D[1], D).map((c) => c.id), ["tol", "jae", "ube"]); // 바르셀로나는 길에서 멀고, 마드리드 바로 옆과 목록 밖은 뺀다
  assert.deepEqual(stopovers(D[0], D[1], D, ["tol"]).map((c) => c.id), ["jae", "ube"]); // 이미 가는 여행지는 뺀다
  assert.deepEqual(stopovers(D[0], D[8], D), []); assert.deepEqual(stopovers(null, D[1], D), []);
});
test("tripAlternatives: 기준별 조합 네 가지 안, 기본안과 같은지, 긴 구간과 넘치는 고른 장소 (D-051)", () => {
  const order = ["mad", "bcn", "gra", "sev"], known = { mad: 119, sev: 42, gra: 21, bcn: 99 }, tasteKnown = { mad: 10, sev: 30, gra: 20, bcn: 5 };
  const leg = (a, b) => ({ mode: a === "bcn" || b === "bcn" ? "flight" : "train", min: legMin(a, b), estimate: a === "bcn" || b === "bcn" });
  const alts = tripAlternatives({ order, totalDays: 10, picked: { gra: 9 }, known, tasteKnown, tastes: ["religious"], leg });
  assert.deepEqual(alts.map((a) => a.key), ["base", "move", "landmark", "taste"]); assert.equal(LONG_LEG_MIN, 240);
  const [base, move, land, taste] = alts;
  assert.deepEqual(base.order, order); assert.deepEqual(base.days, { gra: 3, mad: 3, bcn: 2, sev: 2 }); // 그라나다 9곳 → 3일, 남은 7일을 알려진 곳 수로 assert.equal(base.balance, "balance"); assert.equal(base.travelMin, 739);
  assert.deepEqual(move.order, ["mad", "bcn", "sev", "gra"]); assert.equal(move.travelMin, 669); assert.deepEqual(move.days, base.days); assert.equal(move.same, false);
  assert.deepEqual(move.nights, { mad: 3, bcn: 2, sev: 2, gra: 2 }); // 마지막 여행지만 하루 적다
  assert.equal(base.estimateLegs, 2); assert.deepEqual(base.longLegs.map((l) => [l.from, l.to, l.min]), [["bcn", "gra", 400]]); assert.deepEqual(move.longLegs.map((l) => l.to), ["sev"]);
  assert.deepEqual(land.days, { mad: 4, bcn: 3, sev: 2, gra: 1 }); assert.equal(land.balance, "landmark"); assert.deepEqual(land.overPicked, { gra: 5 }); // 그라나다 9곳을 골랐는데 1일(4곳)
  assert.deepEqual(taste.days, { mad: 2, bcn: 1, sev: 4, gra: 3 }); assert.equal(taste.balance, "other"); assert.deepEqual(taste.overPicked, {});
  // 취향을 고르지 않으면 취향안이 없다. 여행지가 한 곳이면 대안이 없다. 순서가 이미 가장 짧으면 이동 최소안은 기본안과 같다
  assert.deepEqual(tripAlternatives({ order, totalDays: 10, known, leg }).map((a) => a.key), ["base", "move", "landmark"]);
  assert.deepEqual(tripAlternatives({ order: ["mad"], totalDays: 5, known, leg }), []);
  assert.equal(tripAlternatives({ order: ["mad", "bcn", "sev", "gra"], totalDays: 10, known, leg })[1].same, true);
});

