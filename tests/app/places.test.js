import { test } from "node:test";
import assert from "node:assert/strict";
import { hav, filterPlaces, sortByProminence, isForeignLandmark, placeName, altNames, firstSentences, applyPlaceKo, hasPlaceKoShard } from "../../app/src/data/places.js";

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
test("applyPlaceKo: 한국어 이름이 없는 장소에만 생성 이름을 붙이고 입력은 바꾸지 않는다 (D-033)", () => {
  const index = { names: { "osm:n1": "카페 페페", Q160112: "프라도 국립 미술관" }, place_shards: ["00", "a3"] };
  const out = applyPlaceKo(P, index);
  assert.equal(placeName(out[1]), "카페 페페"); assert.equal(out[1].n.ko_src, "generated"); assert.equal(altNames(out[1]), "Café Pepe");
  assert.equal(placeName(out[0]), "프라도 미술관"); assert.equal(out[0], P[0]); assert.equal(out[2], P[2]);
  assert.equal(P[1].n.ko, undefined);
  assert.deepEqual(applyPlaceKo(P, null), P);
  assert.ok(hasPlaceKoShard(index, "a3")); assert.ok(!hasPlaceKoShard(index, "ff")); assert.ok(!hasPlaceKoShard(null, "00")); assert.ok(!hasPlaceKoShard({}, "00"));
});

test("applyPlaceKo: 색인의 이름 보정은 기준 데이터의 한국어 이름을 바꾼다 (D-064)", () => {
  // 고정 입력: 2026-11-22 내보내기의 name_fixes 모양(표기 사전과 다른 기준 이름 4곳)을 축약
  const L = [{ id: "Q1122701", n: { local: "Montjuïc", ko: "몬주이크" } }, { id: "Q160112", n: { local: "Museo del Prado", ko: "프라도 미술관" } }, { id: "osm:n1", n: { local: "Café Pepe" } }];
  const index = { names: { "osm:n1": "카페 페페" }, name_fixes: { Q1122701: "몬주익", "osm:n1": "카페" }, place_shards: [] };
  const out = applyPlaceKo(L, index);
  assert.equal(placeName(out[0]), "몬주익"); assert.equal(out[0].n.ko_src, "fixed"); assert.equal(out[0].n.local, "Montjuïc"); assert.equal(L[0].n.ko, "몬주이크"); // 입력은 바꾸지 않는다
  assert.equal(out[1], L[1]); // 보정이 없는 장소는 그대로
  assert.equal(placeName(out[2]), "카페 페페"); assert.equal(out[2].n.ko_src, "generated"); // 한국어 이름이 없던 장소는 보정 대상이 아니다(생성 이름을 쓴다)
  assert.equal(applyPlaceKo(L, { names: {}, name_fixes: { Q1122701: "몬주이크" } })[0], L[0]); // 같은 이름이면 바꾸지 않는다
  assert.deepEqual(applyPlaceKo(L, { names: {} }), L); // 보정이 없는 예전 색인
});

import { placeLine } from "../../app/src/data/places.js";
test("한 줄 설명: 한국어 생성 설명의 첫 문장이 먼저, 없으면 Wikidata 설명 (D-039)", () => {
  const lines = { lines: { Q160112: "프라도 미술관은 마드리드에 있는 미술관이다." } };
  const out = applyPlaceKo(P, { names: { "osm:n1": "카페 페페" } }, lines);
  assert.equal(out[0].line, "프라도 미술관은 마드리드에 있는 미술관이다."); assert.equal(out[0].n.ko, "프라도 미술관"); assert.equal(out[1].n.ko, "카페 페페"); assert.equal(out[1].line, undefined); assert.equal(out[2], P[2]);
  assert.deepEqual(placeLine(out[0]), { text: "프라도 미술관은 마드리드에 있는 미술관이다.", lang: "ko" });
  assert.deepEqual(placeLine({ desc: [{ src: "wikidata", lang: "es", text: "museo" }, { src: "wikidata", lang: "en", text: "museum in Madrid" }] }), { text: "museum in Madrid", lang: "en" });
  assert.deepEqual(placeLine({ desc: [{ src: "wikidata", lang: "en", text: "museum" }, { src: "wikidata", lang: "ko", text: "미술관" }] }), { text: "미술관", lang: "ko" });
  assert.equal(placeLine({ desc: [{ src: "wikivoyage", lang: "en", page: "Madrid", idx: 1 }] }), null); assert.equal(placeLine({}), null);
});
