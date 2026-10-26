import { test } from "node:test";
import assert from "node:assert/strict";
import { emptyPlan, migrate, loadPlan, savePlan, dateList, toggleSelect, assignDay, moveInDay, unassigned, addCustomPlace, setLodging, lodgingCheck } from "../../app/src/state/plan.js";

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
