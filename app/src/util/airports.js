// 공항 선택 보조(순수 함수). 표기 규칙은 D-029: 영문 도시명 기준, 공항 영문명과 IATA 코드를 옆에, 현지어·한국어 이름은 보조.
import { hav } from "../data/places.js";

export const NEAR_M = 80000; // 선택한 여행 도시에서 이 거리 안의 공항을 먼저 보인다(추정값)
const norm = (v) => (v || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** "Madrid · Adolfo Suárez Madrid-Barajas Airport (MAD)" */
export function airportLabel(a) {
  const city = a.city?.en || a.n?.en || a.iata || "";
  const name = a.n?.en || a.n?.local || "";
  return `${city} · ${name}${a.iata ? ` (${a.iata})` : ""}`;
}

/** 보조 표기: 현지어 이름(영문명과 다를 때) · 한국어 이름 · 연 이용객 */
export function airportSub(a) {
  const parts = [];
  if (a.n?.local && a.n.local !== a.n?.en) parts.push(a.n.local);
  if (a.n?.ko) parts.push(a.n.ko);
  if (a.pax) parts.push(`연 ${Math.round(a.pax / 1e4).toLocaleString()}만 명`);
  return parts.join(" · ");
}

/**
 * 공항 검색. 검색어가 없으면 선택한 도시 80km 안의 공항을 가까운 순, 나머지는 이용객 순.
 * 검색어가 있으면 코드·도시명(영문·한국어)·공항명(영문·현지어·스페인어·한국어)에서 찾고
 * 코드 정확 일치 > 도시명 앞부분 일치 > 공항명 앞부분 일치 > 도시명 포함 > 공항명 포함, 같으면 이용객 순으로 정렬("bar"는 바라하스보다 바르셀로나가 먼저).
 */
export function searchAirports(airports, q, { cities = [], cityIds = [], limit = 8 } = {}) {
  const nq = norm((q || "").trim());
  const pax = (a) => a.pax || 0;
  if (!nq) {
    const sel = cities.filter((c) => cityIds.includes(c.id) && c.lat != null);
    const dist = (a) => sel.reduce((m, c) => Math.min(m, hav(a.lat, a.lon, c.lat, c.lon)), Infinity);
    const near = airports.filter((a) => dist(a) <= NEAR_M).sort((x, y) => dist(x) - dist(y) || pax(y) - pax(x));
    const rest = airports.filter((a) => !near.includes(a)).sort((x, y) => pax(y) - pax(x));
    return [...near, ...rest].slice(0, limit);
  }
  const cityF = (a) => [a.city?.en, a.city?.ko].map(norm).filter(Boolean);
  const nameF = (a) => [a.n?.en, a.n?.local, a.n?.es, a.n?.ko].map(norm).filter(Boolean);
  const rank = (a) => {
    if (norm(a.iata) === nq) return 5;
    if (cityF(a).some((f) => f.startsWith(nq))) return 4;
    if (nameF(a).some((f) => f.startsWith(nq))) return 3;
    if (cityF(a).some((f) => f.includes(nq))) return 2;
    if (nameF(a).some((f) => f.includes(nq))) return 1;
    return 0;
  };
  return airports.filter((a) => rank(a) > 0).sort((x, y) => rank(y) - rank(x) || pax(y) - pax(x)).slice(0, limit);
}
