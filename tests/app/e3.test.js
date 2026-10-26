import { test } from "node:test";
import assert from "node:assert/strict";
import { straightWalk, makeIntraIndex, walkTime, makeTransitIndex, transitEstimate, cityLeg, intercityLeg, PARAMS } from "../../app/src/engines/e3.js";

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
