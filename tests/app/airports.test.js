import { test } from "node:test";
import assert from "node:assert/strict";
import { airportLabel, airportSub, searchAirports } from "../../app/src/util/airports.js";

// 고정 입력: 2026-10-26 수집 결과를 축약(좌표·이용객은 실제값)
const A = [
  { id: "Q166276", iata: "MAD", n: { en: "Adolfo Suárez Madrid-Barajas Airport", local: "Aeropuerto Adolfo Suárez Madrid-Barajas", ko: "마드리드 바라하스 국제공항" }, city: { id: "Q2807", en: "Madrid", ko: "마드리드", guess: false }, lat: 40.4936, lon: -3.5668, pax: 66197066 },
  { id: "Qbcn", iata: "BCN", n: { en: "Josep Tarradellas Barcelona-El Prat Airport", local: "Aeroport Josep Tarradellas Barcelona-el Prat", ko: "바르셀로나 엘프라트 공항" }, city: { id: "Q1492", en: "Barcelona", ko: "바르셀로나", guess: false }, lat: 41.2971, lon: 2.0785, pax: 57483036 },
  { id: "Qtfs", iata: "TFS", n: { en: "Tenerife South Airport", local: "Aeropuerto de Tenerife Sur", ko: null }, city: { id: "Q943431", en: "Tenerife", ko: "테네리페", guess: true }, lat: 28.0445, lon: -16.5725, pax: 10821703 },
  { id: "Qtoj", iata: "TOJ", n: { en: "Madrid-Torrejón Airport", local: "Aeropuerto de Madrid-Torrejón", ko: null }, city: { id: "Q2807", en: "Madrid", ko: "마드리드", guess: true }, lat: 40.4967, lon: -3.4459, pax: 1970 },
];
const cities = [{ id: "Q2807", lat: 40.416944, lon: -3.703333 }, { id: "Q14328", lat: 28.4682, lon: -16.2546 }];

test("표기: 영문 도시명 · 공항 영문명 (IATA), 보조는 현지어·한국어·이용객", () => {
  assert.equal(airportLabel(A[0]), "Madrid · Adolfo Suárez Madrid-Barajas Airport (MAD)");
  assert.equal(airportSub(A[0]), "Aeropuerto Adolfo Suárez Madrid-Barajas · 마드리드 바라하스 국제공항 · 연 6,620만 명");
  assert.equal(airportSub(A[2]), "Aeropuerto de Tenerife Sur · 연 1,082만 명");
});
test("검색어 없음: 선택 도시 80km 안 공항을 가까운 순, 나머지는 이용객 순", () => {
  assert.deepEqual(searchAirports(A, "", { cities, cityIds: ["Q14328"] }).map((a) => a.iata), ["TFS", "MAD", "BCN", "TOJ"]);
  assert.deepEqual(searchAirports(A, "", { cities, cityIds: ["Q2807"] }).map((a) => a.iata), ["MAD", "TOJ", "BCN", "TFS"]);
  assert.deepEqual(searchAirports(A, "", { cities, cityIds: [] }).map((a) => a.iata), ["MAD", "BCN", "TFS", "TOJ"]);
  assert.equal(searchAirports(A, "", { limit: 2 }).length, 2);
});
test("검색: 코드 정확 일치 우선, 도시 영문·한국어, 공항명, 악센트 무시", () => {
  assert.deepEqual(searchAirports(A, "toj").map((a) => a.iata), ["TOJ"]);
  assert.deepEqual(searchAirports(A, "madrid").map((a) => a.iata), ["MAD", "TOJ"]);
  assert.deepEqual(searchAirports(A, "바르셀로나").map((a) => a.iata), ["BCN"]);
  assert.deepEqual(searchAirports(A, "torrejon").map((a) => a.iata), ["TOJ"]);
  assert.deepEqual(searchAirports(A, "prat").map((a) => a.iata), ["BCN"]);
  assert.deepEqual(searchAirports(A, "bar").map((a) => a.iata), ["BCN", "MAD"]); // 도시명 앞부분(바르셀로나)이 공항명 포함(바라하스)보다 먼저
  assert.deepEqual(searchAirports(A, "ten").map((a) => a.iata), ["TFS"]);
  assert.deepEqual(searchAirports(A, "zzz"), []);
});
