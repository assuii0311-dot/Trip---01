// 내보내기(R-09, R-27, F-13·F-22). 순수 함수. KML·CSV는 Google My Maps 가져오기 형식(poc/gmaps_links.py와 같음), 경로 링크는 경유지 한도 분할.
import { gmapsDirLinks } from "../util/format.js";
import { placeName } from "../data/places.js";

export const MYMAPS_CSV_MAX_ROWS = 2000;
export const MYMAPS_KML_MAX_BYTES = 5_000_000;

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const csvCell = (s) => { const v = String(s ?? ""); return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v; };

/** KML(장소 목록). 설명에는 범주·도시·날짜를 넣는다 */
export function toKML(places, { name = "Trip01", descOf = () => "" } = {}) {
  const pm = places.map((p) => `<Placemark><name>${esc(placeName(p))}</name><description>${esc(descOf(p))}</description><Point><coordinates>${p.lon.toFixed(6)},${p.lat.toFixed(6)},0</coordinates></Point></Placemark>`).join("");
  return `<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>${esc(name)}</name>${pm}</Document></kml>`;
}

export function toCSV(places, { descOf = () => "" } = {}) {
  const rows = [["name", "description", "latitude", "longitude"], ...places.map((p) => [placeName(p), descOf(p), p.lat.toFixed(6), p.lon.toFixed(6)])];
  return rows.map((r) => r.map(csvCell).join(",")).join("\n") + "\n";
}

/** 한도 검사(My Maps: CSV 2,000행, KML 5MB) */
export function checkLimits(places, kmlText) {
  const bytes = new TextEncoder().encode(kmlText).length;
  return { rows: places.length, rowsOk: places.length <= MYMAPS_CSV_MAX_ROWS, kmlBytes: bytes, kmlOk: bytes <= MYMAPS_KML_MAX_BYTES };
}

/** 하루 일정의 경유지 링크(모바일 3개 단위). 숙소(origin)에서 출발 */
export function dayRouteLinks(dayItems, getPlace, origin, mode = "walking", limit = 3) {
  const pts = [];
  if (origin && origin.lat != null) pts.push({ lat: origin.lat, lon: origin.lon, name: origin.name || "숙소" });
  for (const it of dayItems) if (it.kind === "place") { const p = getPlace(it.id); if (p) pts.push({ lat: p.lat, lon: p.lon, name: placeName(p) }); }
  return gmapsDirLinks(pts, mode, limit);
}

/** 계획 JSON 내보내기/가져오기(R-09). 가져올 때 형식을 검사한다 */
export function exportPlanJson(plan) {
  return JSON.stringify({ format: "trip01-plan", version: 1, exported: new Date().toISOString(), plan }, null, 1);
}
export function importPlanJson(text) {
  let obj; try { obj = JSON.parse(text); } catch { throw new Error("JSON을 읽을 수 없습니다."); }
  if (!obj || obj.format !== "trip01-plan" || !obj.plan || typeof obj.plan !== "object") throw new Error("Trip01 계획 파일이 아닙니다.");
  const p = obj.plan;
  if (!p.trip || !Array.isArray(p.selection)) throw new Error("계획 내용이 비어 있거나 손상되었습니다.");
  return p;
}

/** 파일 이름: trip-YYYY-MM-DD.ext */
export function fileName(ext, date = new Date()) { return `trip-${date.toISOString().slice(0, 10)}.${ext}`; }
