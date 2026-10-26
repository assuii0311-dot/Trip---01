import { test } from "node:test";
import assert from "node:assert/strict";
import { fmtDistance, fmtMinutes, fmtEurRange, gmapsCoord, gmapsDirLinks } from "../../app/src/util/format.js";
import { md5 } from "../../app/src/util/hash.js";

test("표기 규칙: 거리·시간·금액", () => {
  assert.equal(fmtDistance(850), "850m"); assert.equal(fmtDistance(1234), "1.2km");
  assert.equal(fmtMinutes(12), "12분"); assert.equal(fmtMinutes(80), "1시간 20분"); assert.equal(fmtMinutes(120), "2시간");
  assert.equal(fmtEurRange(12, 18), "€12~18"); assert.equal(fmtEurRange(null, null), "—");
});
test("구글맵 링크: 좌표 검색과 경유지 분할(모바일 3개)", () => {
  assert.equal(gmapsCoord(40.4138, -3.6921), "https://www.google.com/maps/search/?api=1&query=40.413800,-3.692100");
  const pts = [1, 2, 3, 4, 5, 6].map((i) => ({ lat: 40 + i / 100, lon: -3 }));
  const links = gmapsDirLinks(pts, "walking", 3);
  assert.equal(links.length, 2); assert.equal(links[0].via.length, 3); assert.ok(links[0].url.includes("waypoints=") && links[0].url.includes("travelmode=walking"));
  assert.equal(gmapsDirLinks(pts, "walking", 9).length, 1);
});
test("md5: 파이프라인 샤드 키와 같은 값(RFC 1321 예)", () => {
  assert.equal(md5(""), "d41d8cd98f00b204e9800998ecf8427e");
  assert.equal(md5("abc"), "900150983cd24fb0d6963f7d28e17f72");
  assert.equal(md5("Q160112").slice(0, 2).length, 2);
});
