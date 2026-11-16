import { test } from "node:test";
import assert from "node:assert/strict";
import { defaultNav, applyNav, navToHash, hashToNav, screenKey, sanitizeNav, saveNav, loadNav, exploreFilterCount, inputFilterCount, clearedExplore, clearedInput, NAV_KEY } from "../../app/src/state/nav.js";
import { itineraryDrift } from "../../app/src/state/plan.js";

test("nav: 화면 주소 만들기와 읽기", () => {
  const n = defaultNav();
  assert.equal(navToHash(n), "#input/1");
  assert.equal(navToHash(applyNav(n, { tab: "explore", exploreTab: "explore" })), "#explore/explore");
  assert.equal(navToHash(applyNav(n, { tab: "plan", planTab: "itinerary", detail: "osm:n1308942334" })), "#plan/itinerary/p/osm%3An1308942334");
  assert.equal(navToHash(applyNav(n, { tab: "settings" })), "#settings");
  assert.deepEqual(hashToNav("#input/3"), { tab: "input", detail: null, inputStep: 3 });
  assert.deepEqual(hashToNav("#input/4"), { tab: "input", detail: null }); // 입력은 3단계(D-039)
  assert.deepEqual(hashToNav("#explore/explore/p/osm%3An1308942334"), { tab: "explore", detail: "osm:n1308942334", exploreTab: "explore" });
  assert.deepEqual(hashToNav("#plan/itinerary"), { tab: "plan", detail: null, planTab: "itinerary" });
  assert.deepEqual(hashToNav("#share"), { tab: "share", detail: null });
  assert.deepEqual(hashToNav("#input/9"), { tab: "input", detail: null }); // 없는 단계는 무시
  assert.equal(hashToNav(""), null); assert.equal(hashToNav("#nowhere/1"), null); assert.equal(hashToNav(undefined), null);
  // 만든 주소를 읽으면 같은 화면이 된다
  for (const patch of [{ tab: "input", inputStep: 2 }, { tab: "explore", exploreTab: "summary" }, { tab: "plan", planTab: "arrange", detail: "Q160112" }, { tab: "share" }]) {
    const a = applyNav(n, patch); assert.equal(navToHash(applyNav(n, hashToNav(navToHash(a)))), navToHash(a));
  }
  assert.equal(screenKey(applyNav(n, { tab: "explore", exploreTab: "explore", detail: "Q1" })), "#explore/explore"); // 상세를 열고 닫아도 같은 화면
});

test("nav: 부분 변경은 나머지를 지키고 입력을 바꾸지 않는다", () => {
  const n = applyNav(defaultNav(), { explore: { city: "Q2807", q: "museo", cats: ["museum"] } });
  const m = applyNav(n, { tab: "plan", explore: { q: "" } });
  assert.equal(m.tab, "plan"); assert.deepEqual(m.explore, { city: "Q2807", list: null, q: "", cats: ["museum"], balance: null });
  assert.equal(n.tab, "input"); assert.equal(n.explore.q, "museo");
  assert.equal(applyNav(n, { input: { kind: "island" } }).input.q, "");
});

test("nav: 저장해 둔 상태를 지금 계획에 맞게 다듬는다", () => {
  const saved = { tab: "explore", inputStep: 3, exploreTab: "explore", planTab: "itinerary", detail: "Q1", input: { q: "sev", kind: "island", rec: true, only: "taste", sort: "taste", focus: ["beach", 3], region: "Q5783" }, explore: { city: "Q8717", list: "all", q: "museo", cats: ["museum"], balance: "other" } };
  const ok = sanitizeNav(saved, { cityIds: ["Q2807", "Q8717"], hasPlace: (id) => id === "Q1" });
  assert.equal(ok.tab, "explore"); assert.equal(ok.inputStep, 3); assert.equal(ok.detail, "Q1"); assert.deepEqual(ok.input, { q: "sev", kind: "island", only: "taste", sort: "taste", region: "Q5783" }); // 예전 값 rec는 버린다(D-049)
  assert.equal(sanitizeNav({ ...saved, inputStep: 4 }).inputStep, 1); // 예전 4단계 값은 처음으로
  assert.deepEqual(ok.explore, { city: "Q8717", list: "all", q: "museo", cats: ["museum"], balance: "other" });
  const moved = sanitizeNav(saved, { cityIds: ["Q2807"] }); // 여행지가 바뀌었으면 보던 도시를 비우고, 열 수 없는 상세는 닫는다
  assert.equal(moved.explore.city, null); assert.equal(moved.detail, null); assert.equal(moved.explore.q, "museo");
  assert.deepEqual(sanitizeNav({ tab: "x", inputStep: 9, exploreTab: 1, input: "?", explore: { list: "?", cats: "museum", balance: 2 } }), defaultNav());
  assert.deepEqual(sanitizeNav(null), defaultNav());
});

test("nav: 기기에 적고 읽기. 열어 둔 상세는 적지 않는다", () => {
  const mem = new Map(); const storage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, v) };
  assert.equal(loadNav(storage), null);
  assert.ok(saveNav(storage, applyNav(defaultNav(), { tab: "plan", detail: "Q1" })));
  assert.equal(loadNav(storage).tab, "plan"); assert.equal(loadNav(storage).detail, null); assert.ok(mem.has(NAV_KEY));
  mem.set(NAV_KEY, "{broken"); assert.equal(loadNav(storage), null);
  assert.equal(saveNav({ setItem() { throw new Error("full"); } }, defaultNav()), false);
});

test("nav: 걸어 둔 필터 수와 지우기", () => {
  const n = applyNav(defaultNav(), { explore: { q: " museo ", cats: ["museum", "heritage"] }, input: { q: "ma", kind: "island", only: "pop", sort: "taste", region: "Q5783" } });
  assert.equal(exploreFilterCount(n.explore), 3); assert.equal(inputFilterCount(n.input), 4);
  const c = applyNav(n, { explore: clearedExplore(), input: clearedInput() });
  assert.equal(exploreFilterCount(c.explore), 0); assert.equal(inputFilterCount(c.input), 0); assert.equal(c.input.sort, "taste"); // 정렬은 필터가 아니라 남는다
  assert.equal(exploreFilterCount(applyNav(defaultNav(), { explore: { q: "   " } }).explore), 0);
});

test("itineraryDrift: 일정표를 만든 뒤 고르거나 뺀 장소", () => {
  const plan = { selection: ["Q1", "Q2", "Q4", "Q5"], itinerary: { days: [{ items: [{ kind: "place", id: "Q1" }, { kind: "meal", meal: "lunch" }, { kind: "place", id: "Q3" }] }, { items: [] }], overflow: [{ id: "Q2", reason: "시간 초과" }] } };
  assert.deepEqual(itineraryDrift(plan), { missing: ["Q4", "Q5"], removed: ["Q3"] });
  assert.deepEqual(itineraryDrift({ selection: ["Q1"] }), { missing: [], removed: [] }); // 일정표가 없으면 차이도 없다
  assert.deepEqual(itineraryDrift({ selection: ["Q1"], itinerary: { days: [{ items: [{ kind: "place", id: "Q1" }] }], overflow: [] } }), { missing: [], removed: [] });
});
