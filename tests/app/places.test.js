import { test } from "node:test";
import assert from "node:assert/strict";
import { hav, filterPlaces, sortByProminence, isForeignLandmark, placeName, altNames, firstSentences } from "../../app/src/data/places.js";

const P = [
  { id: "Q160112", city: "Q2807", tier: 1, cat: ["museum"], n: { local: "Museo del Prado", es: "Museo del Prado", en: "Museo del Prado", ko: "프라도 미술관" }, pop: { sl: 80, pv: { en: 14055, es: 8710 }, en_share: 0.617 }, lat: 40.4139, lon: -3.6922 },
  { id: "osm:n1", city: "Q2807", tier: 2, cat: ["cafe"], n: { local: "Café Pepe" }, pop: { sl: 0, pv: null, en_share: null }, ver: false, lat: 40.42, lon: -3.70 },
  { id: "Q5", city: "Q1492", tier: 1, cat: ["religious"], n: { local: "Sagrada Família", ca: "Sagrada Família", es: "Sagrada Familia", en: "Sagrada Família", ko: "사그라다 파밀리아" }, pop: { sl: 120, pv: { en: 90000, es: 30000 }, en_share: 0.75 }, lat: 41.4036, lon: 2.1744 },
];

test("hav: 솔 광장↔프라도 약 1.05km", () => { const d = hav(40.4168, -3.7038, 40.4138, -3.6921); assert.ok(d > 950 && d < 1150); });
test("filterPlaces: 도시·범주·검색(악센트 무시)", () => {
  assert.equal(filterPlaces(P, { cityId: "Q2807" }).length, 2);
  assert.equal(filterPlaces(P, { cats: ["cafe"] })[0].id, "osm:n1");
  assert.equal(filterPlaces(P, { query: "sagrada familia" })[0].id, "Q5");
  assert.equal(filterPlaces(P, { query: "프라도" })[0].id, "Q160112");
  assert.equal(filterPlaces(P, { tier: 1 }).length, 2);
});
test("sortByProminence: 사이트링크 내림차순, 결정적", () => { assert.deepEqual(sortByProminence(P).map((p) => p.id), ["Q5", "Q160112", "osm:n1"]); });
test("isForeignLandmark: 영어 비중 0.5·사이트링크 10 (D-025)", () => { assert.ok(isForeignLandmark(P[0])); assert.ok(!isForeignLandmark(P[1])); assert.ok(!isForeignLandmark({ pop: { sl: 5, en_share: 0.9 } })); });
test("placeName/altNames: 한국어 우선, 카탈루냐어 지역은 현지 · 스페인어 병기 (D-021 ⑥)", () => {
  assert.equal(placeName(P[0]), "프라도 미술관"); assert.equal(altNames(P[0]), "Museo del Prado");
  assert.equal(placeName(P[2]), "사그라다 파밀리아"); assert.equal(altNames(P[2]), "Sagrada Família · Sagrada Familia");
  assert.equal(placeName(P[1]), "Café Pepe"); assert.equal(altNames(P[1]), "");
});
test("firstSentences: 앞 두 문장", () => { assert.equal(firstSentences("One. Two! Three?"), "One. Two!"); assert.equal(firstSentences(""), ""); });
