import { test } from "node:test";
import assert from "node:assert/strict";
import { toKML, toCSV, checkLimits, dayRouteLinks, exportPlanJson, importPlanJson, fileName } from "../../app/src/engines/export.js";

const P = [{ id: "a", n: { ko: "프라도 미술관", local: "Museo del Prado" }, lat: 40.4138, lon: -3.6921, cat: ["museum"] }, { id: "b", n: { local: "Bar \"Pepe\", Sol" }, lat: 40.4169, lon: -3.7033, cat: ["cafe"] }];
test("KML: Placemark 수와 이스케이프", () => {
  const k = toKML(P, { name: "Trip<1>", descOf: (p) => p.cat[0] });
  assert.ok(k.includes("<name>Trip&lt;1&gt;</name>")); assert.equal((k.match(/<Placemark>/g) || []).length, 2); assert.ok(k.includes("-3.692100,40.413800,0")); assert.ok(k.includes("&quot;") === false && k.includes('Bar "Pepe", Sol'));
});
test("CSV: 머리글과 따옴표 처리", () => {
  const c = toCSV(P); const lines = c.trim().split("\n");
  assert.equal(lines[0], "name,description,latitude,longitude"); assert.equal(lines.length, 3); assert.ok(lines[2].startsWith('"Bar ""Pepe"", Sol",'));
});
test("한도 검사: 2,000행과 5MB", () => {
  const many = Array.from({ length: 2001 }, (_, i) => ({ id: String(i), n: { local: "x" }, lat: 40, lon: -3, cat: [] }));
  const r = checkLimits(many, toKML(many)); assert.equal(r.rowsOk, false); assert.equal(r.kmlOk, true);
  assert.equal(checkLimits(P, toKML(P)).rowsOk, true);
});
test("하루 경유지 링크: 숙소 출발, 모바일 3개 단위 분할", () => {
  const items = Array.from({ length: 6 }, (_, i) => ({ kind: "place", id: String(i) })).concat([{ kind: "meal" }]);
  const getPlace = (id) => ({ id, n: { local: "p" + id }, lat: 40 + Number(id) / 100, lon: -3 });
  const links = dayRouteLinks(items, getPlace, { lat: 40.5, lon: -3, name: "숙소" });
  assert.equal(links.length, 2); assert.equal(links[0].from.name, "숙소"); assert.ok(links[0].url.includes("travelmode=walking"));
  assert.equal(dayRouteLinks([], getPlace, null).length, 0);
});
test("JSON 내보내기·가져오기 왕복과 형식 검사", () => {
  const plan = { trip: { cities: ["Q2807"] }, selection: ["a"], days: {}, lodging: {}, reservations: {} };
  const text = exportPlanJson(plan); assert.deepEqual(importPlanJson(text), plan);
  assert.throws(() => importPlanJson("{"), /JSON/); assert.throws(() => importPlanJson('{"format":"x"}'), /Trip01/); assert.throws(() => importPlanJson('{"format":"trip01-plan","plan":{}}'), /비어/);
  assert.equal(fileName("kml", new Date("2026-10-26T01:00:00Z")), "trip-2026-10-26.kml");
});
