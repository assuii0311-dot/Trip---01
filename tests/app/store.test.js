import { test } from "node:test";
import assert from "node:assert/strict";
import { createStore, emptyTrip, validateTrip, tripDays, loadDraft, saveDraft } from "../../app/src/state/store.js";

test("createStore: set은 병합하고 구독자에게 알린다", () => {
  const s = createStore({ a: 1, b: 2 });
  let seen = null; s.subscribe((st) => (seen = st));
  s.set({ b: 3 }); assert.deepEqual(s.get(), { a: 1, b: 3 }); assert.deepEqual(seen, { a: 1, b: 3 });
  s.set((st) => ({ a: st.a + 10 })); assert.equal(s.get().a, 11);
});

test("validateTrip: 기간 1~30일, 도시 1개 이상, 인원 1~20, 마감 > 시작", () => {
  const t = { ...emptyTrip(), start: "2027-05-01", end: "2027-05-10", cities: ["Q2807"], people: 2 };
  assert.deepEqual(validateTrip(t), {});
  assert.equal(tripDays(t), 10);
  assert.ok(validateTrip({ ...t, end: "2027-06-15" }).period);
  assert.ok(validateTrip({ ...t, cities: [] }).cities);
  assert.ok(validateTrip({ ...t, people: 0 }).people);
  assert.ok(validateTrip({ ...t, dayStart: "22:00", dayEnd: "09:00" }).day);
});

test("draft 저장은 저장소 오류에도 죽지 않는다", () => {
  const mem = {}; const storage = { getItem: (k) => mem[k] ?? null, setItem: (k, v) => (mem[k] = v) };
  const t = { ...emptyTrip(), cities: ["Q2807"] };
  assert.equal(saveDraft(storage, t), true); assert.deepEqual(loadDraft(storage).cities, ["Q2807"]);
  const broken = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
  assert.equal(saveDraft(broken, t), false); assert.deepEqual(loadDraft(broken), emptyTrip());
});
