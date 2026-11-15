// 화면 위치와 보기 상태(D-036, 화면 흐름 4절). 어느 탭·하위 화면·단계에 있었는지, 목록의 검색어와 필터가 무엇이었는지를 한곳에 둔다.
// 화면을 옮겨도 잃지 않도록 App이 들고, 주소(#...)와 기기에 적는다. 순수 함수만 있다. 테스트는 tests/app/nav.test.js
export const NAV_KEY = "trip01.nav.v1";
export const TABS = ["input", "explore", "plan", "share", "settings"];
export const EXPLORE_TABS = ["summary", "explore"];
export const PLAN_TABS = ["arrange", "itinerary"];
export const INPUT_STEPS = 3; // 기본 정보 → 취향·여행지 → 공항·여행 형태(D-039)

export function defaultNav() {
  return {
    tab: "input", inputStep: 1, exploreTab: "summary", planTab: "arrange", detail: null,
    input: { q: "", kind: "all", rec: false, region: "" },
    explore: { city: null, list: null, q: "", cats: [], balance: null },
  };
}

/** 바꿀 부분만 받아 새 상태를 만든다. input과 explore는 그 안의 항목 단위로 합친다 */
export function applyNav(nav, patch = {}) {
  const next = { ...nav, ...patch };
  if (patch.input) next.input = { ...nav.input, ...patch.input };
  if (patch.explore) next.explore = { ...nav.explore, ...patch.explore };
  return next;
}

/** 화면 주소. 탭과 하위 화면(입력은 단계)까지가 화면이고, 열어 둔 장소 상세가 있으면 뒤에 붙는다. 검색어와 필터는 주소에 넣지 않는다 */
export function navToHash(nav) {
  let h = nav.tab;
  if (nav.tab === "input") h += "/" + nav.inputStep;
  else if (nav.tab === "explore") h += "/" + nav.exploreTab;
  else if (nav.tab === "plan") h += "/" + nav.planTab;
  if (nav.detail) h += "/p/" + encodeURIComponent(nav.detail);
  return "#" + h;
}

/** 열어 둔 상세를 뺀 화면 이름(목록 위치를 기억하는 열쇠) */
export const screenKey = (nav) => navToHash({ ...nav, detail: null });

/** 주소에서 화면 위치를 읽는다. 읽을 수 없으면 null. 상세가 없는 주소는 detail을 null로 돌려준다 */
export function hashToNav(hash) {
  const raw = String(hash || "").replace(/^#/, "");
  if (!raw) return null;
  const at = raw.indexOf("/p/");
  let detail = null;
  if (at >= 0) { try { detail = decodeURIComponent(raw.slice(at + 3)) || null; } catch { detail = null; } }
  const [tab, sub] = (at >= 0 ? raw.slice(0, at) : raw).split("/");
  if (!TABS.includes(tab)) return null;
  const out = { tab, detail };
  if (tab === "input" && sub) { const n = Number(sub); if (Number.isInteger(n) && n >= 1 && n <= INPUT_STEPS) out.inputStep = n; }
  if (tab === "explore" && EXPLORE_TABS.includes(sub)) out.exploreTab = sub;
  if (tab === "plan" && PLAN_TABS.includes(sub)) out.planTab = sub;
  return out;
}

const str = (v, d = "") => (typeof v === "string" ? v : d);
const strs = (v) => (Array.isArray(v) ? v.filter((x) => typeof x === "string") : []);

/**
 * 저장해 둔 상태나 주소에서 온 값을 지금 계획에 맞게 다듬는다.
 * cityIds: 지금 여행의 여행지. 그 안에 없는 도시를 보고 있었다면 비운다. hasPlace: 그 장소를 지금 열 수 있는가.
 */
export function sanitizeNav(raw, { cityIds = [], hasPlace = () => false } = {}) {
  const d = defaultNav(), r = raw && typeof raw === "object" ? raw : {};
  const ri = r.input && typeof r.input === "object" ? r.input : {}, re = r.explore && typeof r.explore === "object" ? r.explore : {};
  const step = Number(r.inputStep);
  return {
    tab: TABS.includes(r.tab) ? r.tab : d.tab,
    inputStep: Number.isInteger(step) && step >= 1 && step <= INPUT_STEPS ? step : d.inputStep,
    exploreTab: EXPLORE_TABS.includes(r.exploreTab) ? r.exploreTab : d.exploreTab,
    planTab: PLAN_TABS.includes(r.planTab) ? r.planTab : d.planTab,
    detail: typeof r.detail === "string" && hasPlace(r.detail) ? r.detail : null,
    input: { q: str(ri.q), kind: ["all", "city", "island"].includes(ri.kind) ? ri.kind : "all", rec: ri.rec === true, region: str(ri.region) },
    explore: { city: cityIds.includes(re.city) ? re.city : null, list: ["rec", "all"].includes(re.list) ? re.list : null, q: str(re.q), cats: strs(re.cats), balance: ["landmark", "balance", "other"].includes(re.balance) ? re.balance : null },
  };
}

/** 기기에 적어 두는 값. 열어 둔 상세는 적지 않는다(다시 열 때 장소 데이터가 아직 없을 수 있다) */
export function saveNav(storage, nav) {
  try { storage.setItem(NAV_KEY, JSON.stringify({ ...nav, detail: null })); return true; } catch { return false; }
}
export function loadNav(storage) {
  try { const raw = storage.getItem(NAV_KEY); return raw ? JSON.parse(raw) : null; } catch { return null; }
}

/** 걸어 둔 필터 수(검색어 포함). 0이면 '필터 지우기'를 보이지 않는다 */
export const exploreFilterCount = (e) => (e.q.trim() ? 1 : 0) + e.cats.length;
export const inputFilterCount = (i) => (i.q.trim() ? 1 : 0) + (i.kind !== "all" ? 1 : 0) + (i.rec ? 1 : 0) + (i.region ? 1 : 0);
export const clearedExplore = () => ({ q: "", cats: [] });
export const clearedInput = () => ({ q: "", kind: "all", rec: false, region: "" });
