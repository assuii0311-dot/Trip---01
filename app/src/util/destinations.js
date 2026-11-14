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
export function filterDestinations(list, { q = "", kind = "all", focus = [], region = "" } = {}) {
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
