// 작은 상태 저장소. DOM과 네트워크를 모른다(규칙 11). 여행 데이터 초안은 localStorage에 둔다(D-011: Key·토큰·작성 중 내용만 기기에).
/** @template T */
export function createStore(initial) {
  let state = initial;
  const subs = new Set();
  return {
    get: () => state,
    /** @param {Partial<T> | ((s: T) => Partial<T>)} patch */
    set(patch) {
      const p = typeof patch === "function" ? patch(state) : patch;
      state = { ...state, ...p };
      subs.forEach((fn) => fn(state));
    },
    subscribe(fn) { subs.add(fn); return () => subs.delete(fn); },
  };
}

export const DRAFT_KEY = "trip01.draft.v1";

/** 여행 입력(R-01~R-03)의 빈 값. 항목은 기획 가안(R-02 비고). */
export function emptyTrip() {
  return {
    start: "", end: "", cities: [], airportOut: null, airportIn: null, timeOut: "", timeIn: "", people: 2,
    budget: "mid", dayStart: "09:00", dayEnd: "22:00", meals: ["normal"], tastes: [],
    foreignBalance: "balance",
  };
}

/** 입력 검증(기능 명세 F-01). 반환: {필드: 메시지} */
export function validateTrip(t) {
  const err = {};
  if (!t.start || !t.end) err.period = "기간을 입력하세요.";
  else {
    const d = (new Date(t.end) - new Date(t.start)) / 86400000 + 1;
    if (!(d >= 1 && d <= 30)) err.period = "기간은 1~30일이어야 합니다.";
  }
  if (!t.cities || t.cities.length === 0) err.cities = "도시를 하나 이상 선택하세요.";
  if (!(t.people >= 1 && t.people <= 20)) err.people = "인원은 1~20명이어야 합니다.";
  if (t.dayStart && t.dayEnd && t.dayStart >= t.dayEnd) err.day = "마감 시각은 시작 시각보다 늦어야 합니다.";
  return err;
}

export function tripDays(t) {
  if (!t.start || !t.end) return 0;
  return Math.round((new Date(t.end) - new Date(t.start)) / 86400000) + 1;
}

/** 저장소(localStorage 등) 접근은 실패할 수 있으므로 감싼다. */
export function loadDraft(storage) {
  try { const raw = storage.getItem(DRAFT_KEY); return raw ? { ...emptyTrip(), ...JSON.parse(raw) } : emptyTrip(); } catch { return emptyTrip(); }
}
export function saveDraft(storage, trip) {
  try { storage.setItem(DRAFT_KEY, JSON.stringify(trip)); return true; } catch { return false; }
}
