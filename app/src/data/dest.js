// 여행지(도시 또는 섬) 보조(순수 함수). 섬은 members(소속 지자체 ID)를 가진 도시 모양 레코드다(D-030, E1 4절 14항).
// 장소의 city는 항상 지자체 ID이므로, 섬을 고른 여행에서는 "그 지자체가 속한 여행지"를 이 모듈로 찾는다.

export const isIsland = (c) => !!c && c.kind === "island";

/** 여행지가 포함하는 지자체 ID 목록(도시는 자기 자신) */
export const memberIds = (c) => (c ? (c.members && c.members.length ? c.members : [c.id]) : []);

/** 장소가 여행지 안에 있는가 */
export const inDest = (p, c) => !!c && !!p && (p.city === c.id || (!!c.members && c.members.includes(p.city)));

/** 표시 이름: 한국어 → 영어 → 스페인어 → 현지어 */
export const destName = (c) => (c ? c.n?.ko || c.n?.en || c.n?.es || c.n?.local || c.id : "");

/**
 * 장소 → 여행지 ID 함수를 만든다. 여행 도시 목록에 그 지자체가 직접 있으면 그 지자체,
 * 없으면 그 지자체를 포함하는 섬(목록에서 앞선 것), 둘 다 아니면 null.
 */
export function makeDestOf(cities, tripCityIds) {
  const exact = new Set(tripCityIds);
  const via = new Map();
  for (const id of tripCityIds) {
    const c = cities.find((x) => x.id === id);
    for (const m of (c && c.members) || []) if (!via.has(m)) via.set(m, id);
  }
  return (p) => (p && exact.has(p.city) ? p.city : (p && via.get(p.city)) || null);
}
