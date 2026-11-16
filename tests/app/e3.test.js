import { test } from "node:test";
import assert from "node:assert/strict";
import { straightWalk, makeIntraIndex, walkTime, makeTransitIndex, transitEstimate, cityLeg, intercityLeg, PARAMS, makeIslandIndex, islandCar } from "../../app/src/engines/e3.js";

const A = { id: "a", lat: 40.4138, lon: -3.6921 }, B = { id: "b", lat: 40.4154, lon: -3.7074 }, C = { id: "c", lat: 40.4300, lon: -3.7100 };
test("직선 추정: 우회 1.24, 4.5km/h", () => { const w = straightWalk(A, B); assert.ok(w.m > 1500 && w.m < 1800); assert.ok(w.min >= 20 && w.min <= 24); assert.equal(w.confidence, "estimate"); });
test("사전 계산 조회가 있으면 계산값, 없으면 추정", () => {
  const intra = makeIntraIndex({ ids: ["a", "b"], pairs: [[0, 1, 25.3, 2090]] });
  assert.deepEqual(walkTime(A, B, intra), { min: 25, m: 2090, confidence: "computed" });
  assert.equal(walkTime(A, C, intra).confidence, "estimate");
});
test("대중교통 B 추정: 직통과 1회 환승", () => {
  // 정류장 0,1,2는 노선 L1(지하철), 2,3은 L2(버스). A는 0 근처, B는 1 근처, C는 3 근처
  const file = { stops: [[40.4139, -3.6922, "S0"], [40.4155, -3.7075, "S1"], [40.4200, -3.7000, "S2"], [40.4301, -3.7101, "S3"]], routes: [{ id: "L1", name: "1", type: 1, seq: [[0, 2, 1]] }, { id: "L2", name: "27", type: 3, seq: [[2, 3]] }], fares: [] };
  const t = makeTransitIndex(file);
  const direct = transitEstimate(A, B, t); assert.equal(direct.transfers, 0); assert.equal(direct.legs[0].route, "1"); assert.ok(direct.min > 5 && direct.min < 40);
  const x = transitEstimate(A, C, t); assert.equal(x.transfers, 1); assert.equal(x.legs.length, 2);
  assert.equal(transitEstimate(A, { lat: 41, lon: -3 }, t), null);
});
test("cityLeg: 1.5km 이하는 도보 우선, 대안 2개, 택시 요금", () => {
  const near = { id: "n", lat: 40.4140, lon: -3.6950 };
  const r = cityLeg(A, near, { taxi: { base_eur: 2.8, per_km_eur: 1.35, min_eur: 8 } });
  assert.equal(r.best.mode, "walk"); assert.ok(r.alternatives.length <= 2); assert.equal(r.options.find((o) => o.mode === "taxi").fare, 8);
  const far = cityLeg(A, C, {}); assert.notEqual(far.best.mode, "walk");
});
test("intercityLeg: 행렬·기차·섬은 비행기·배 추정", () => {
  const inter = { cities: [{ id: "m", lat: 40.4, lon: -3.7 }, { id: "b", lat: 41.4, lon: 2.2 }, { id: "p", lat: 39.6, lon: 2.65 }], car_min: [[0, 333, null], [333, 0, null], [null, null, 0]], car_km: [[0, 620, null], [620, 0, null], [null, null, 0]], train_min: [[null, 150, null], [150, null, null], [null, null, null]], trains_per_day: [[0, 20, 0], [20, 0, 0], [0, 0, 0]] };
  const mb = intercityLeg(inter.cities[0], inter.cities[1], inter); assert.equal(mb.best.mode, "train"); assert.equal(mb.best.min, 150); assert.ok(mb.options.some((o) => o.mode === "flight"));
  const mp = intercityLeg(inter.cities[0], inter.cities[2], inter); assert.ok(mp.options.some((o) => o.mode === "ferry") && mp.options.some((o) => o.mode === "flight")); assert.equal(mp.best.mode, "flight");
});
test("intercityLeg: 섬 여행지가 끼면 차량 없이 비행기·배만(D-030)", () => {
  const inter = { cities: [], car_min: [], car_km: [], train_min: [], trains_per_day: [] };
  const ibiza = { id: "Q52631", kind: "island", lat: 38.91, lon: 1.43 }, mallorca = { id: "Q8828", kind: "island", lat: 39.57, lon: 2.65 };
  const palma = { id: "Q8826", island: "Q8828", lat: 39.57, lon: 2.65 }, soller = { id: "Qs", island: "Q8828", lat: 39.77, lon: 2.71 }, valencia = { id: "Q8818", lat: 39.47, lon: -0.38 };
  const a = intercityLeg(ibiza, mallorca, inter); assert.deepEqual(a.options.map((o) => o.mode).sort(), ["ferry", "flight"]);
  const b = intercityLeg(valencia, palma, inter); assert.ok(!b.options.some((o) => o.mode === "car"));
  const c = intercityLeg(palma, soller, inter); assert.ok(c.options.some((o) => o.mode === "car")); // 같은 섬 안은 차량 가능
  const d = intercityLeg(mallorca, soller, inter); assert.ok(d.options.some((o) => o.mode === "car"));
});


// T-048: 섬 안의 다른 지자체 사이는 사전 계산한 차량 시간을 쓴다(테네리페 3곳의 가상 행렬)
test("islandCar: 다른 지자체의 먼 구간은 행렬값, 가깝거나 같은 지자체면 직선 추정", () => {
  const file = { cities: [{ id: "SC", lat: 28.4682, lon: -16.2546 }, { id: "AD", lat: 28.1227, lon: -16.7260 }, { id: "LL", lat: 28.4874, lon: -16.3159 }], car_min: [[0, 62, 14], [62, 0, 70], [14, 70, 0]], car_km: [[0, 78.4, 9.1], [78.4, 0, 86.0], [9.1, 86.0, 0]] };
  const isl = makeIslandIndex(file);
  const a = { id: "p1", lat: 28.47, lon: -16.25, city: "SC" }, b = { id: "p2", lat: 28.10, lon: -16.74, city: "AD" }, c = { id: "p3", lat: 28.465, lon: -16.26, city: "SC" };
  assert.deepEqual(islandCar(a, b, isl), { min: 62, m: 78400, confidence: "estimate", source: "island_matrix" });
  assert.equal(islandCar(a, c, isl), null); // 같은 지자체
  assert.equal(islandCar(a, { lat: 28.48, lon: -16.28, city: "LL" }, isl), null); // 다른 지자체지만 직선 5km 미만(약 3km)
  assert.equal(islandCar(a, b, null), null);
  // 소속을 모르는 지점(숙박 구역)은 가장 가까운 지자체로 본다. 15km 안에 없으면 쓰지 않는다
  assert.equal(islandCar({ lat: 28.47, lon: -16.26 }, b, isl).min, 62);
  assert.equal(islandCar({ lat: 29.5, lon: -13.5 }, b, isl), null);
  // cityLeg의 택시 시간이 행렬값에서 나온다: 직선 추정(22km/h)이면 3시간이 넘는 구간
  const leg = cityLeg(a, b, { island: isl }); const taxi = leg.options.find((o) => o.mode === "taxi");
  assert.equal(taxi.min, 62 + PARAMS.taxiWaitMin); assert.equal(taxi.m, 78400); assert.equal(leg.best.mode, "taxi");
  const noMatrix = cityLeg(a, b, {}).options.find((o) => o.mode === "taxi"); assert.ok(noMatrix.min > 150);
});
