import { test } from "node:test";
import assert from "node:assert/strict";
import { destinationList, filterDestinations, searchOthers, nearestAirport, regionOptions, fmtPop } from "../../app/src/util/destinations.js";
import { memberIds, inDest, makeDestOf, destName, isIsland, applyDestinationKo } from "../../app/src/data/dest.js";

// 고정 입력: 2026-11-14 빌드 결과의 모양을 축약
const C = [
  { id: "Q8810", n: { ko: "그라나다", en: "Granada", es: "Granada" }, lat: 37.178, lon: -3.6, pop: 233975, region: { community: "Q5783" }, wv: { en: "Granada" }, dest: { tier: 1, rank: 5 }, focus: ["heritage", "museum"], hl: [{ id: "a", n: { ko: "알람브라", en: "Alhambra" } }] },
  { id: "Q1492", n: { ko: "바르셀로나", en: "Barcelona" }, lat: 41.38, lon: 2.17, pop: 1731649, region: { community: "Q5705" }, wv: { en: "Barcelona" }, dest: { tier: 1, rank: 1 }, focus: ["heritage"], hl: [] },
  { id: "Q8828", kind: "island", members: ["Q8826", "Q1"], n: { ko: "마요르카섬", en: "Mallorca" }, lat: 39.57, lon: 2.65, pop: 960610, region: { community: "Q107356467" }, wv: { en: "Mallorca" }, dest: { tier: 2, rank: 23 }, focus: ["beach"], hl: [] },
  { id: "Q8826", n: { ko: "팔마", en: "Palma" }, lat: 39.57, lon: 2.65, pop: 434786, island: "Q8828", region: { community: "Q107356467" }, wv: { en: "Palma" } },
  { id: "Qronda", n: { ko: "론다", en: "Ronda" }, lat: 36.74, lon: -5.16, pop: 33671, region: { community: "Q5783" }, wv: { en: "Ronda" }, dest: { tier: 3, rank: 68 }, focus: [], hl: [] },
  { id: "Qsmall", n: { en: "Rondilla", es: "Rondilla" }, lat: 40, lon: -3, pop: 25000, region: { community: "Q5783" }, wv: { en: null } },
  { id: "Qtiny", n: { en: "Rondita" }, lat: 40, lon: -3, pop: 300, region: {}, wv: { en: null } },
];

test("여행지 목록: dest가 있는 것만 등급·순위 순", () => {
  assert.deepEqual(destinationList(C).map((c) => c.id), ["Q1492", "Q8810", "Q8828", "Qronda"]);
});
test("거르기: 검색어(이름·대표 명소, 악센트 무시), 종류, 취향, 자치주", () => {
  const L = destinationList(C);
  assert.deepEqual(filterDestinations(L, { q: "알람브라" }).map((c) => c.id), ["Q8810"]);
  assert.deepEqual(filterDestinations(L, { q: "mallor" }).map((c) => c.id), ["Q8828"]);
  assert.deepEqual(filterDestinations(L, { kind: "island" }).map((c) => c.id), ["Q8828"]);
  assert.deepEqual(filterDestinations(L, { kind: "city" }).map((c) => c.id), ["Q1492", "Q8810", "Qronda"]);
  assert.deepEqual(filterDestinations(L, { focus: ["beach", "museum"] }).map((c) => c.id), ["Q8810", "Q8828"]);
  assert.deepEqual(filterDestinations(L, { region: "Q5783" }).map((c) => c.id), ["Q8810", "Qronda"]);
  assert.deepEqual(filterDestinations(L, {}).length, 4);
});
test("목록 밖 지자체 검색: 여행지·섬·소규모 무가이드 제외, 정확 일치 우선", () => {
  assert.deepEqual(searchOthers(C, "rond").map((c) => c.id), ["Qsmall"]);
  assert.deepEqual(searchOthers(C, "palma").map((c) => c.id), ["Q8826"]);
  assert.deepEqual(searchOthers(C, ""), []);
});
test("가까운 여객 공항과 자치주 선택지, 인구 표기", () => {
  const A = [{ iata: "GRX", lat: 37.19, lon: -3.78, pax: 908713 }, { iata: "AGP", lat: 36.67, lon: -4.5, pax: 26760549 }, { iata: "X", lat: 37.18, lon: -3.6, pax: 10 }];
  assert.deepEqual(nearestAirport(C[0], A), { iata: "GRX", km: 16 });
  assert.equal(nearestAirport({ lat: null }, A), null);
  assert.deepEqual(regionOptions(destinationList(C), [{ id: "Q5783", n: { local: "Andalucía" } }, { id: "Q5705", n: { local: "Catalunya" } }]).map((r) => [r.name, r.n]), [["Andalucía", 2], ["Catalunya", 1], ["Q107356467", 1]]);
  assert.equal(fmtPop(233975), "23만 명"); assert.equal(fmtPop(8774), "8,774명"); assert.equal(fmtPop(0), "");
});
test("섬 여행지: 소속 지자체, 장소 포함 여부, 장소 → 여행지", () => {
  const isl = C[2], palma = C[3];
  assert.equal(isIsland(isl), true); assert.equal(isIsland(palma), false);
  assert.deepEqual(memberIds(isl), ["Q8826", "Q1"]); assert.deepEqual(memberIds(palma), ["Q8826"]); assert.deepEqual(memberIds(null), []);
  assert.equal(inDest({ city: "Q8826" }, isl), true); assert.equal(inDest({ city: "Q8826" }, palma), true); assert.equal(inDest({ city: "Q8810" }, isl), false);
  assert.equal(destName(isl), "마요르카섬"); assert.equal(destName({ id: "x", n: { es: "Uno" } }), "Uno");
  const viaIsland = makeDestOf(C, ["Q8810", "Q8828"]);
  assert.equal(viaIsland({ city: "Q8826" }), "Q8828"); assert.equal(viaIsland({ city: "Q8810" }), "Q8810"); assert.equal(viaIsland({ city: "Qother" }), null);
  const direct = makeDestOf(C, ["Q8828", "Q8826"]);
  assert.equal(direct({ city: "Q8826" }), "Q8826"); // 지자체를 직접 골랐으면 그 지자체가 우선
  assert.equal(direct({ city: "Q1" }), "Q8828");
});
test("E5 여행지 한국어 소개 붙이기: 요약, 생성 이름, 입력 불변(D-032)", () => {
  const cities = [{ id: "Q8810", n: { ko: "그라나다", en: "Granada" } }, { id: "Q492735", n: { ko: null, en: "Fuengirola" } }, { id: "Qx", n: { en: "X" } }];
  const e5 = { items: { Q8810: { summary: "그라나다는 도시다.", name_ko: "무시", sources: [{ title: "Granada", url: "u" }], confidence: "보통", generated: "2026-11-14", food: "타파스(바에서 음료를 시키면 함께 나옴)" }, Q492735: { summary: "푸엔히롤라는 도시다.", name_ko: "푸엔히롤라", sources: [], confidence: "보통" } } };
  const out = applyDestinationKo(cities, e5);
  assert.equal(out[0].ko.summary, "그라나다는 도시다."); assert.equal(out[0].n.ko, "그라나다"); assert.equal(out[0].n.ko_src, undefined); // 이름이 있으면 그대로
  assert.equal(out[1].n.ko, "푸엔히롤라"); assert.equal(out[1].n.ko_src, "generated"); assert.equal(destName(out[1]), "푸엔히롤라");
  assert.equal(out[0].ko.food, "타파스(바에서 음료를 시키면 함께 나옴)"); assert.equal(out[1].ko.food, null); // 대표 음식은 있는 여행지에만 붙는다(D-046)
  assert.equal(out[2], cities[2]); assert.equal(cities[1].n.ko, null); // 입력은 바꾸지 않는다
  assert.deepEqual(applyDestinationKo(cities, null), cities); assert.deepEqual(applyDestinationKo(cities, {}), cities);
});

import { tasteMatch, destViews, tasteRanking, tasteReasons, sortDestinations, onlyDestinations, isPopular, POPULAR_N, TASTE_TOP_N } from "../../app/src/util/destinations.js";
test("tasteMatch: 고른 취향이 여행지의 중심 범주인지(카드의 칩 강조용)", () => {
  const L = [{ id: "A", focus: ["heritage", "museum"] }, { id: "C", focus: ["museum", "beach"] }, { id: "D" }];
  assert.deepEqual(tasteMatch(L[0], ["museum"]), { matched: ["museum"], weight: 1 });
  assert.deepEqual(tasteMatch(L[1], ["museum", "beach"]), { matched: ["museum", "beach"], weight: 3 });
  assert.deepEqual(tasteMatch(L[2], ["beach"]), { matched: [], weight: 0 });
});
test("여행지의 인기와 취향 추천: 조회수의 크기와 비중으로 순위를 매기고 위 N곳만 추천 (D-049)", () => {
  // 고정 입력: 2026-11-16 시험 계산의 모양을 축약(큰 도시, 한 범주에 치우친 곳, 섬, 조회수가 없는 곳)
  const D = [
    { id: "big", dest: { tier: 1, rank: 1 } }, { id: "mus", dest: { tier: 2, rank: 30 } }, { id: "isl", kind: "island", members: ["m1", "m2"], dest: { tier: 1, rank: 4 } },
    { id: "her", dest: { tier: 3, rank: 60 } }, { id: "none", dest: { tier: 3, rank: 90 } }, { id: "notdest" },
  ];
  const pl = (city, cat, en, es = 0) => ({ city, cat, pop: { pv: en || es ? { en, es } : null } });
  const T1 = [pl("big", ["heritage"], 9000, 1000), pl("big", ["museum"], 1000), pl("big", ["park"], 500), pl("mus", ["museum", "heritage"], 1500), pl("mus", ["park"], 100),
    pl("m1", ["beach"], 800), pl("m2", ["nature"], 700), pl("m2", ["museum"], 0), pl("her", ["heritage"], 300), pl("none", ["museum"], 0), pl("notdest", ["museum"], 99999), pl("gone", ["museum"], 5)];
  const V = destViews(D, T1);
  assert.deepEqual([...V.keys()].sort(), ["big", "her", "isl", "mus"]); // 조회수가 있는 여행지만. 목록 밖 지자체와 조회수 0은 빠진다
  assert.equal(V.get("big").total, 11500); assert.equal(V.get("isl").total, 1500); assert.equal(V.get("isl").rows.length, 2); // 섬은 소속 지자체의 장소를 모은다
  const L = D.filter((c) => c.dest);
  const R = tasteRanking(L, V, ["museum"], 2);
  assert.equal(R.get("big").mass, 1000); assert.equal(R.get("mus").mass, 1500); assert.equal(Math.round(R.get("mus").share * 100), 94); // 범주가 둘인 장소도 한 번만 센다
  assert.deepEqual(L.map((c) => R.get(c.id).order), [2, 1, 3, 4, 5]); // 크기와 비중이 모두 큰 mus가 앞. 0인 곳은 참고 순위순
  assert.deepEqual(L.map((c) => tasteRanking(L, V, ["heritage"]).get(c.id).order), [1, 2, 4, 3, 5]); // 크기 순서와 비중 순서가 정반대라 동점이면 참고 순위순(big 1위, mus 30위, her 60위)
  assert.deepEqual(L.filter((c) => R.get(c.id).top).map((c) => c.id), ["big", "mus"]);
  assert.deepEqual([...tasteRanking(L, V, ["beach"], 3).entries()].filter(([, v]) => v.top).map(([k]) => k), ["isl"]); // 맞는 곳이 없으면(크기 0) 추천을 붙이지 않는다
  assert.equal(tasteRanking(L, V, []).size, 0); assert.equal(tasteRanking([], V, ["museum"]).size, 0);
  // 취향 추천의 이유(D-059): 조회수 합이 큰 범주부터 둘, 범주마다 조회수가 큰 장소 둘. 두 범주에 든 장소는 앞 범주에만
  const np = (name, cat, v) => ({ n: { ko: name }, city: "big", cat, pop: { pv: { en: v, es: 0 } } });
  const W = destViews([{ id: "big", dest: { tier: 1, rank: 1 } }], [np("궁전", ["heritage", "park"], 900), np("성벽", ["heritage"], 500), np("탑", ["heritage"], 300), np("정원", ["park"], 200), np("미술관", ["museum"], 100), np("해변", ["beach"], 50)]).get("big");
  const names = (r) => r.map((x) => [x.cat, x.places.map((p) => p.n.ko)]);
  assert.deepEqual(names(tasteReasons(W, ["park", "heritage", "museum"])), [["heritage", ["궁전", "성벽"]], ["park", ["정원"]]]); // heritage 1,700 > park 1,100 > museum 100. 궁전은 heritage에만
  assert.deepEqual(names(tasteReasons(W, ["museum", "beach", "market"])), [["museum", ["미술관"]], ["beach", ["해변"]]]); // 맞는 장소가 없는 범주(market)는 건너뛴다
  assert.deepEqual(names(tasteReasons(W, ["heritage"], { maxPlaces: 3 })), [["heritage", ["궁전", "성벽", "탑"]]]);
  assert.deepEqual(names(tasteReasons(W, ["park"])), [["park", ["궁전", "정원"]]]); // 한 범주만 고르면 두 범주에 든 장소도 그 범주에 나온다
  assert.deepEqual(tasteReasons(W, []), []); assert.deepEqual(tasteReasons(undefined, ["park"]), []); assert.deepEqual(tasteReasons(W, ["market"]), []);
  // 정렬과 거르기. 인기순은 받은 순서 그대로, 취향순은 순위순
  assert.equal(sortDestinations(L, "pop", R), L); assert.equal(sortDestinations(L, "taste", new Map()), L);
  assert.deepEqual(sortDestinations(L, "taste", R).map((c) => c.id), ["mus", "big", "isl", "her", "none"]);
  assert.deepEqual(onlyDestinations(L, "pop", R).map((c) => c.id), ["big", "isl"]); assert.deepEqual(onlyDestinations(L, "taste", R).map((c) => c.id), ["big", "mus"]); assert.equal(onlyDestinations(L, "", R), L);
  assert.ok(isPopular({ dest: { rank: POPULAR_N } }) && !isPopular({ dest: { rank: POPULAR_N + 1 } }) && !isPopular({}) && TASTE_TOP_N === 10);
});
