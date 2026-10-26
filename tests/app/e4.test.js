import { test } from "node:test";
import assert from "node:assert/strict";
import { dwellOf, mealSlots, clusterPlaces, orderRoute, parseHours, placeDay, generate, toMin, toHHMM } from "../../app/src/engines/e4.js";

const mk = (id, lat, lon, cat = "heritage", hrs = null) => ({ id, lat, lon, cat: [cat], hrs });
const P = [mk("prado", 40.4138, -3.6921, "museum", "Mon-Sat 10:00-20:00"), mk("retiro", 40.4150, -3.6840, "park"), mk("mayor", 40.4154, -3.7074, "square"), mk("palacio", 40.4180, -3.7143, "heritage", "10:00-18:00"), mk("sol", 40.4169, -3.7033, "square"), mk("debod", 40.4240, -3.7178, "heritage"), mk("eat1", 40.4160, -3.7050, "restaurant")];
const travel = (a, b) => { const d = Math.hypot((a.lat - b.lat) * 111000, (a.lon - b.lon) * 85000) * 1.24; return { min: Math.round(d / 75), m: Math.round(d), mode: "walk" }; };

test("체류 시간 기본값(1.5배)과 식사 슬롯", () => {
  assert.equal(dwellOf(P[0]), 180); assert.equal(dwellOf(P[2]), 45); assert.equal(dwellOf(P[0], { prado: 90 }), 90);
  assert.equal(mealSlots(["light"])[0].min, 60); assert.equal(mealSlots(["snack"]).length, 3);
});
test("k-means와 경로 순서는 결정적", () => {
  const g1 = clusterPlaces(P, 2), g2 = clusterPlaces(P, 2); assert.deepEqual(g1, g2); assert.equal(g1.flat().length, P.length);
  const o1 = orderRoute(P, { lat: 40.4169, lon: -3.7033 }, (a, b) => travel(a, b).min); assert.deepEqual(o1, orderRoute(P, { lat: 40.4169, lon: -3.7033 }, (a, b) => travel(a, b).min)); assert.equal(new Set(o1).size, P.length);
});
test("parseHours: 첫 시간대", () => { assert.deepEqual(parseHours("Mon-Sat 10:00-20:00, Sun 10:00-19:00"), { open: 600, close: 1200 }); assert.equal(parseHours("daily"), null); });
test("placeDay: 시작·마감(시작 시각 기준), 확인 필요 표시, 초과분", () => {
  const d = placeDay({ start: "09:00", end: "22:00", places: P.map((p) => ({ p, dwell: dwellOf(p) })), origin: { lat: 40.4169, lon: -3.7033 }, travel, meals: ["normal"] });
  const items = d.items.filter((i) => i.kind === "place");
  assert.ok(items.every((i) => i.start >= toMin("09:00") && i.start <= toMin("22:00")));
  assert.ok(items.some((i) => i.flag === "no_hours")); // 참고값 없는 장소
  assert.ok(d.items.some((i) => i.kind === "meal"));
  assert.ok(items.length + d.overflow.length === P.length);
  // 마감 10:00: 09:00 시작, 첫 항목만 들어가고 나머지는 초과
  const short = placeDay({ start: "09:00", end: "09:30", places: P.slice(0, 3).map((p) => ({ p, dwell: 180 })), origin: { lat: 40.4138, lon: -3.6921 }, travel, meals: [] });
  assert.equal(short.items.filter((i) => i.kind === "place").length, 1); assert.equal(short.overflow.length, 2);
  // 21:30에 1시간짜리 시작 가능(마감 22:00)
  const late = placeDay({ start: "21:30", end: "22:00", places: [{ p: P[1], dwell: 60 }], origin: { lat: 40.4150, lon: -3.6840 }, travel, meals: [] });
  assert.equal(late.items.length, 1); assert.equal(late.items[0].end, toMin("22:30"));
});
test("generate: 배치된 장소는 그 날에, 나머지는 도시 묶음으로, 초과분은 다음 날로", () => {
  const all = new Map(P.map((p) => [p.id, p]));
  const r = generate({ days: [{ date: "2027-05-01", cityId: "Q2807", origin: { lat: 40.4169, lon: -3.7033 } }, { date: "2027-05-02", cityId: "Q2807", origin: { lat: 40.4169, lon: -3.7033 } }], placesByCity: { Q2807: P, __all: all }, assigned: { "2027-05-02": ["debod"] }, travelFor: () => travel, meals: ["normal"], dayStart: "09:00", dayEnd: "22:00" });
  assert.equal(r.days.length, 2); assert.deepEqual(r.days[0].origin, { lat: 40.4169, lon: -3.7033 });
  const day2 = r.days[1].items.filter((i) => i.kind === "place").map((i) => i.id); assert.ok(day2.includes("debod"));
  const placed = r.days.flatMap((d) => d.items.filter((i) => i.kind === "place").map((i) => i.id)); assert.equal(new Set(placed).size, placed.length);
  assert.equal(placed.length + r.overflow.length, P.length);
  const r2 = generate({ days: [{ date: "2027-05-01", cityId: "Q2807", origin: { lat: 40.4169, lon: -3.7033 } }, { date: "2027-05-02", cityId: "Q2807", origin: { lat: 40.4169, lon: -3.7033 } }], placesByCity: { Q2807: P, __all: all }, assigned: { "2027-05-02": ["debod"] }, travelFor: () => travel, meals: ["normal"], dayStart: "09:00", dayEnd: "22:00" });
  assert.deepEqual(r, r2);
  assert.equal(toHHMM(toMin("13:05")), "13:05");
});
