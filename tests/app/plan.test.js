import { test } from "node:test";
import assert from "node:assert/strict";
import { emptyPlan, migrate, loadPlan, savePlan, dateList, toggleSelect, assignDay, moveInDay, unassigned, addCustomPlace, setLodging, lodgingCheck, removeSelections, removeDestination, assignMany } from "../../app/src/state/plan.js";

const trip = { start: "2027-05-01", end: "2027-05-04", cities: ["Q2807"], people: 2 };

test("dateList와 숙박 일수 검사", () => {
  const p = { ...emptyPlan(), trip: { ...emptyPlan().trip, ...trip } };
  assert.deepEqual(dateList(p.trip), ["2027-05-01", "2027-05-02", "2027-05-03", "2027-05-04"]);
  assert.deepEqual(lodgingCheck(setLodging(p, "Q2807", { nights: 3 })), { nights: 3, total: 3, ok: true });
  assert.equal(lodgingCheck(p).ok, false);
});
test("선택·배치·순서·미배치", () => {
  let p = { ...emptyPlan(), trip: { ...emptyPlan().trip, ...trip } };
  p = toggleSelect(p, "a"); p = toggleSelect(p, "b"); p = toggleSelect(p, "c");
  p = assignDay(p, "a", "2027-05-01"); p = assignDay(p, "b", "2027-05-01"); p = assignDay(p, "c", "2027-05-02");
  assert.deepEqual(p.days["2027-05-01"], ["a", "b"]); assert.deepEqual(unassigned(p), []);
  p = assignDay(p, "a", "2027-05-02"); assert.deepEqual(p.days["2027-05-01"], ["b"]); assert.deepEqual(p.days["2027-05-02"], ["c", "a"]);
  p = moveInDay(p, "2027-05-02", 1, 0); assert.deepEqual(p.days["2027-05-02"], ["a", "c"]);
  p = assignDay(p, "a", null); assert.deepEqual(unassigned(p), ["a"]);
  p = toggleSelect(p, "c"); assert.deepEqual(p.selection, ["a", "b"]); assert.deepEqual(p.days["2027-05-02"], []);
});
test("직접 추가 장소는 사용자 추가 표시와 함께 선택된다", () => {
  const p = addCustomPlace(emptyPlan(), { name: "친구 집", lat: 40.4, lon: -3.7, cityId: "Q2807" });
  const id = p.selection[0]; assert.ok(id.startsWith("user:")); assert.equal(p.custom[id].cv, "user"); assert.equal(p.custom[id].n.local, "친구 집");
});
test("이전 키에서 옮겨 오기와 저장", () => {
  const mem = { "trip01.draft.v1": JSON.stringify({ cities: ["Q1492"] }), "trip01.selection.v1": JSON.stringify(["x"]) };
  const storage = { getItem: (k) => mem[k] ?? null, setItem: (k, v) => (mem[k] = v) };
  const p = loadPlan(storage); assert.deepEqual(p.trip.cities, ["Q1492"]); assert.deepEqual(p.selection, ["x"]);
  assert.equal(savePlan(storage, p), true); assert.deepEqual(loadPlan(storage).selection, ["x"]);
  assert.deepEqual(migrate({ trip: { people: 3 } }).trip.people, 3);
});

import { addSelections } from "../../app/src/state/plan.js";
test("addSelections: 여러 곳을 한 번에 담되 이미 있는 곳과 중복은 건너뛴다 (D-039)", () => {
  const plan = { selection: ["Q1"], days: {}, custom: {} };
  const out = addSelections(plan, ["Q2", "Q1", "Q3", "Q2"]);
  assert.deepEqual(out.selection, ["Q1", "Q2", "Q3"]); assert.deepEqual(plan.selection, ["Q1"]);
  assert.equal(addSelections(plan, ["Q1"]), plan); assert.equal(addSelections(plan, []), plan);
});


// 묶음 13: 고른 장소 한꺼번에 빼기, 여행지 빼기, 날짜 한꺼번에 배정
test("removeSelections: 선택과 날짜 배치에서 빼고, 직접 추가한 장소는 정의도 지운다", () => {
  const plan = { ...emptyPlan(), selection: ["a", "b", "user:1", "c"], days: { "2027-05-01": ["a", "user:1"], "2027-05-02": ["b"] }, custom: { "user:1": { id: "user:1" } }, reservations: { a: { status: "required" } } };
  const r = removeSelections(plan, ["a", "user:1"]);
  assert.deepEqual(r.selection, ["b", "c"]); assert.deepEqual(r.days, { "2027-05-01": [], "2027-05-02": ["b"] }); assert.deepEqual(r.custom, {});
  assert.deepEqual(r.reservations, { a: { status: "required" } }); // 예약 메모는 남긴다
  assert.equal(removeSelections(plan, []), plan); assert.deepEqual(plan.selection, ["a", "b", "user:1", "c"]); // 입력은 바꾸지 않는다
});
test("removeDestination: 여행지와 그 여행지의 고른 장소, 숙박 설정을 함께 뺀다", () => {
  const plan = { ...emptyPlan(), trip: { ...emptyPlan().trip, cities: ["Q2807", "Q8828"] }, selection: ["m1", "p1", "p2"], days: { "2027-05-03": ["p1"] }, lodging: { Q2807: { nights: 3 }, Q8828: { nights: 2 } } };
  const r = removeDestination(plan, "Q8828", ["p1", "p2"]);
  assert.deepEqual(r.trip.cities, ["Q2807"]); assert.deepEqual(r.selection, ["m1"]); assert.deepEqual(r.days, { "2027-05-03": [] }); assert.deepEqual(r.lodging, { Q2807: { nights: 3 } });
});
test("assignMany: 여러 장소를 날짜에 넣고 일부는 미배치로 돌린다", () => {
  const plan = { ...emptyPlan(), selection: ["a", "b", "c", "d"], days: { "2027-05-01": ["a", "b"], "2027-05-02": ["c"] } };
  const r = assignMany(plan, { "2027-05-02": ["a"], "2027-05-03": ["d"] }, ["b"]);
  assert.deepEqual(r.days, { "2027-05-01": [], "2027-05-02": ["c", "a"], "2027-05-03": ["d"] });
});

import { moveCity, applyTripPlan } from "../../app/src/state/plan.js";
test("moveCity: 여행지 순서를 한 칸 옮기고 끝에서는 그대로 (D-051)", () => {
  const p = { ...emptyPlan(), trip: { ...emptyPlan().trip, ...trip, cities: ["A", "B", "C"] } };
  assert.deepEqual(moveCity(p, "B", -1).trip.cities, ["B", "A", "C"]); assert.deepEqual(moveCity(p, "B", 1).trip.cities, ["A", "C", "B"]);
  assert.equal(moveCity(p, "A", -1), p); assert.equal(moveCity(p, "C", 1), p); assert.equal(moveCity(p, "X", 1), p);
  assert.deepEqual(p.trip.cities, ["A", "B", "C"]); // 입력은 바꾸지 않는다
});
test("applyTripPlan: 순서·숙박 일수·추천 기준을 쓰고, 날짜 배치는 유지하거나 푼다 (D-051)", () => {
  let p = { ...emptyPlan(), trip: { ...emptyPlan().trip, ...trip, cities: ["A", "B", "C"] }, selection: ["x", "y"], days: { "2027-05-01": ["x"], "2027-05-02": ["y"] }, lodging: { A: { nights: 9, zone: "z1" } } };
  const alt = { order: ["A", "C", "B"], nights: { A: 2, C: 1, B: 0 }, balance: "landmark" };
  const keep = applyTripPlan(p, alt);
  assert.deepEqual(keep.trip.cities, ["A", "C", "B"]); assert.equal(keep.trip.foreignBalance, "landmark");
  assert.deepEqual(keep.lodging, { A: { nights: 2, zone: "z1" }, C: { nights: 1 }, B: { nights: 0 } }); // 고른 숙박 구역은 남는다
  assert.deepEqual(keep.days, p.days); assert.deepEqual(keep.selection, ["x", "y"]);
  const clear = applyTripPlan(p, alt, { keepAssign: false });
  assert.deepEqual(clear.days, { "2027-05-01": [], "2027-05-02": [] }); assert.deepEqual(clear.selection, ["x", "y"]); // 배치만 풀고 고른 장소는 남는다
  assert.equal(applyTripPlan(p, { order: ["A", "B"] }), p); assert.equal(applyTripPlan(p, { order: ["A", "B", "X"] }), p); assert.equal(applyTripPlan(p, { order: ["A", "A", "B"] }), p); // 여행지 집합이 다르면 그대로
  assert.deepEqual(p.trip.cities, ["A", "B", "C"]);
});

