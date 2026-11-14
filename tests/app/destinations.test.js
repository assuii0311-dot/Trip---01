import { test } from "node:test";
import assert from "node:assert/strict";
import { destinationList, filterDestinations, searchOthers, nearestAirport, regionOptions, fmtPop } from "../../app/src/util/destinations.js";
import { memberIds, inDest, makeDestOf, destName, isIsland } from "../../app/src/data/dest.js";

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
