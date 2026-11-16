// 여행지 목록 보조(순수 함수, D-030). 목록은 E1이 만든 dest(참고 등급·순위), focus(취향 중심), hl(대표 명소), wv.lead(소개 문장)를 쓴다.
// 등급은 정렬과 참고 표시일 뿐이고, 선택은 사용자가 카드의 요약 정보를 보고 한다.
import { hav } from "../data/places.js";

const norm = (v) => (v || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const names = (c) => Object.values(c.n || {}).filter((v) => typeof v === "string");

/** 여행지 목록: dest가 있는 레코드를 참고 등급 → 순위 순으로 */
export function destinationList(cities) {
  return cities.filter((c) => c.dest).sort((a, b) => a.dest.tier - b.dest.tier || a.dest.rank - b.dest.rank || a.id.localeCompare(b.id));
}

/**
 * 목록 거르기. q: 이름(한·영·서·현지어)과 대표 명소 이름, kind: all|city|island,
 * focus: 취향 범주 ID 배열(하나라도 중심이면 통과), region: 자치주 ID.
 */
export function filterDestinations(list, { q = "", kind = "all", focus = [], region = "" } = {}) { // focus: 취향 중심 범주로 거를 때만 넣는다(화면의 거르기는 onlyDestinations)
  const nq = norm(q.trim());
  return list.filter((c) => {
    if (kind === "island" && c.kind !== "island") return false;
    if (kind === "city" && c.kind === "island") return false;
    if (region && (c.region?.community || "") !== region) return false;
    if (focus.length && !focus.some((f) => (c.focus || []).includes(f))) return false;
    if (nq) {
      const hay = names(c).concat((c.hl || []).flatMap((h) => Object.values(h.n || {}))).map(norm);
      if (!hay.some((v) => v.includes(nq))) return false;
    }
    return true;
  });
}

/** 목록 밖 지자체 검색: 이름 정확 일치 → 인구 순. 인구 2만 이상이거나 가이드 문서가 있는 지자체만(섬 레코드와 목록에 있는 여행지는 제외) */
export function searchOthers(cities, q, { limit = 6 } = {}) {
  const nq = norm((q || "").trim());
  if (!nq) return [];
  const pool = cities.filter((c) => !c.dest && c.kind !== "island" && ((c.pop || 0) >= 20000 || c.wv?.en));
  const exact = (c) => (names(c).some((v) => norm(v) === nq) ? 1 : 0);
  return pool.filter((c) => names(c).some((v) => norm(v).includes(nq))).sort((a, b) => exact(b) - exact(a) || (b.pop || 0) - (a.pop || 0)).slice(0, limit);
}

/** 가장 가까운 여객 공항(연 이용객 minPax 이상). 반환 {iata, km} 또는 null */
export function nearestAirport(c, airports, { minPax = 100000 } = {}) {
  if (!c || c.lat == null) return null;
  let best = null;
  for (const a of airports) {
    if ((a.pax || 0) < minPax) continue;
    const d = hav(c.lat, c.lon, a.lat, a.lon);
    if (!best || d < best.d) best = { d, a };
  }
  return best ? { iata: best.a.iata, km: Math.round(best.d / 1000) } : null;
}

/** 자치주 선택지: 목록에 여행지가 있는 자치주만, 여행지 수 내림차순 */
export function regionOptions(list, regions) {
  const count = new Map();
  for (const c of list) { const r = c.region?.community; if (r) count.set(r, (count.get(r) || 0) + 1); }
  const name = (id) => { const r = regions.find((x) => x.id === id); return r ? r.n?.local || r.n?.es || id : id; };
  return [...count.entries()].map(([id, n]) => ({ id, name: name(id), n })).sort((a, b) => b.n - a.n || a.name.localeCompare(b.name));
}

/** 인구 표기: 1만 이상은 "23만 명", 그 밑은 "8,774명" */
export function fmtPop(pop) {
  if (!pop) return "";
  return pop >= 10000 ? `${Math.round(pop / 10000).toLocaleString()}만 명` : `${pop.toLocaleString()}명`;
}

/**
 * 고른 취향과 여행지의 취향 중심 범주(focus, 많아야 둘)의 맞음. 카드의 중심 범주 칩을 강조하는 데만 쓴다(추천 표시는 tasteRanking, D-049).
 * matched: 맞은 범주(중심 순서), weight: 첫째 중심이 맞으면 2, 둘째 중심이 맞으면 1의 합.
 */
export function tasteMatch(c, tastes = []) {
  const focus = c.focus || [];
  const matched = focus.filter((f) => tastes.includes(f));
  return { matched, weight: focus.reduce((s, f, i) => s + (tastes.includes(f) ? (i === 0 ? 2 : 1) : 0), 0) };
}

export const POPULAR_N = 20;   // D-049: 참고 순위 1~20위에 "인기" 표시
export const TASTE_TOP_N = 10; // D-049: 취향 점수 상위 10곳에 "취향 추천"

/** 인기 여행지인가(E2 4절 4-1항): E1 참고 순위가 POPULAR_N 안 */
export const isPopular = (c) => Number.isFinite(c?.dest?.rank) && c.dest.rank <= POPULAR_N;

/**
 * 여행지별 장소 조회수 표. 조회수(en+es)가 있는 1등급 장소만 담는다. 섬은 소속 지자체의 장소를 모은다.
 * 돌려주는 값: Map<여행지 ID, { total, rows: [[범주 배열, 조회수], ...] }>
 */
export function destViews(cities, tier1) {
  const destOf = new Map();
  for (const c of cities) if (c.dest) for (const m of (c.members && c.members.length ? c.members : [c.id])) destOf.set(m, c.id);
  const out = new Map();
  for (const p of tier1) {
    const d = destOf.get(p.city); if (!d) continue;
    const v = (p.pop?.pv?.en ?? 0) + (p.pop?.pv?.es ?? 0); if (!v) continue;
    let e = out.get(d); if (!e) out.set(d, (e = { total: 0, rows: [] }));
    e.total += v; e.rows.push([p.cat, v]);
  }
  return out;
}

/**
 * 여행지의 취향 순위(E2 4절 4-1항, D-049). 고른 취향 범주에 드는 장소의 조회수 합(크기)과 그 여행지 전체에서의 비중을
 * 각각 목록 안 순위 비율(0~1)로 바꿔 평균한다. 높은 순으로 top곳에 top=true. 크기가 0이면 붙이지 않는다. 동점은 참고 순위순.
 * 돌려주는 값: Map<여행지 ID, { score, mass, share, order, top }>. 고른 취향이 없으면 빈 Map.
 */
export function tasteRanking(list, views, tastes = [], top = TASTE_TOP_N) {
  const out = new Map();
  if (!tastes.length || !list.length) return out;
  const sel = new Set(tastes);
  const rows = list.map((c) => {
    const e = views.get(c.id);
    const mass = e ? e.rows.reduce((s, [cat, v]) => s + (cat.some((x) => sel.has(x)) ? v : 0), 0) : 0;
    return { c, mass, share: e && e.total ? mass / e.total : 0 };
  });
  const ratio = (vals) => { const s = [...vals].sort((a, b) => a - b), n = s.length; return (v) => (n <= 1 ? 1 : s.findIndex((x) => x >= v) / (n - 1)); };
  const rm = ratio(rows.map((r) => r.mass)), rs = ratio(rows.map((r) => r.share));
  const rank = (c) => c.dest?.rank ?? 9999;
  rows.map((r) => ({ ...r, score: (rm(r.mass) + rs(r.share)) / 2 }))
    .sort((a, b) => b.score - a.score || rank(a.c) - rank(b.c) || a.c.id.localeCompare(b.c.id))
    .forEach((r, i) => out.set(r.c.id, { score: Math.round(r.score * 1000) / 1000, mass: r.mass, share: r.share, order: i + 1, top: i < top && r.mass > 0 }));
  return out;
}

/** 목록 순서: "pop"은 받은 순서(참고 순위), "taste"는 취향 순위순. 취향 순위가 없으면 그대로 */
export function sortDestinations(list, mode = "pop", ranking = new Map()) {
  if (mode !== "taste" || !ranking.size) return list;
  return list.map((c, i) => ({ c, i, o: ranking.get(c.id)?.order ?? 1e9 })).sort((a, b) => a.o - b.o || a.i - b.i).map((x) => x.c);
}

/** 거르기: "pop"은 인기 여행지만, "taste"는 취향 추천만 */
export function onlyDestinations(list, only = "", ranking = new Map()) {
  if (only === "pop") return list.filter(isPopular);
  if (only === "taste") return list.filter((c) => ranking.get(c.id)?.top);
  return list;
}
