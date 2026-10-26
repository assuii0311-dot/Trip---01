// 장소 데이터의 순수 함수들(검색, 필터, 거리). 테스트는 tests/app/places.test.js
export function hav(lat1, lon1, lat2, lon2) {
  const p = Math.PI / 180, dLat = (lat2 - lat1) * p, dLon = (lon2 - lon1) * p;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * p) * Math.cos(lat2 * p) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(Math.min(1, a)));
}

export function normalize(s) {
  return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** 해외 대표 명소 구분(E2 4절 2항, D-025): 영어 조회 비중 0.5 이상이고 사이트링크 10 이상 */
export function isForeignLandmark(p, th = { share: 0.5, sitelinks: 10 }) {
  const pop = p.pop || {};
  return (pop.en_share ?? 0) >= th.share && (pop.sl ?? 0) >= th.sitelinks;
}

export function placeName(p) {
  const n = p.n || {};
  return n.ko || n.local || n.es || n.en || p.id;
}

/** 병기 명칭(D-021 ⑥): 한국어가 있으면 현지어/영어를 보조로. 바스크·카탈루냐·갈리시아 명칭이 있으면 현지 명칭 · 스페인어 */
export function altNames(p) {
  const n = p.n || {};
  const local = n.ca || n.eu || n.gl ? `${n.local}${n.es && n.es !== n.local ? " · " + n.es : ""}` : n.local;
  const parts = [];
  if (local && local !== placeName(p)) parts.push(local);
  if (n.en && n.en !== local && n.en !== placeName(p) && n.en !== n.local) parts.push(n.en);
  return parts.join(" / ");
}

export function filterPlaces(places, { cityId, cats, query, tier } = {}) {
  const q = normalize(query);
  return places.filter((p) => {
    if (cityId && p.city !== cityId) return false;
    if (tier && p.tier !== tier) return false;
    if (cats && cats.length && !p.cat.some((c) => cats.includes(c))) return false;
    if (q) {
      const hay = Object.values(p.n || {}).filter((v) => typeof v === "string").map(normalize).join(" ");
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

/** 기본 정렬: 대표성(사이트링크, 영어 조회) 내림차순 */
export function sortByProminence(places) {
  return [...places].sort((a, b) => ((b.pop?.sl ?? 0) - (a.pop?.sl ?? 0)) || (((b.pop?.pv?.en ?? 0) + (b.pop?.pv?.es ?? 0)) - ((a.pop?.pv?.en ?? 0) + (a.pop?.pv?.es ?? 0))) || String(a.id).localeCompare(String(b.id)));
}

/** 설명 출처의 영어 원문 앞 두 문장(E5 미생성 시 표시) */
export function firstSentences(text, n = 2) {
  if (!text) return "";
  const parts = text.replace(/\s+/g, " ").match(/[^.!?]+[.!?]+(\s|$)/g) || [text];
  return parts.slice(0, n).join("").trim();
}
