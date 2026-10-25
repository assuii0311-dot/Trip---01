import { test } from "node:test";
import assert from "node:assert/strict";
import { gzipSync } from "node:zlib";
import { decodeGzipResponse, makeLoader } from "../../app/src/data/loader.js";

test("decodeGzipResponse: gzip과 평문 모두 JSON으로", async () => {
  const obj = { a: 1, 이름: "프라도" };
  const gz = gzipSync(Buffer.from(JSON.stringify(obj)));
  assert.deepEqual(await decodeGzipResponse(new Response(gz)), obj);
  assert.deepEqual(await decodeGzipResponse(new Response(JSON.stringify(obj))), obj);
});
test("makeLoader: 메모리 캐시와 404 처리", async () => {
  let calls = 0;
  const fetchFn = async (url) => { calls++; if (url.endsWith("missing.json.gz")) return new Response("x", { status: 404 }); return new Response(gzipSync(Buffer.from(JSON.stringify([{ id: url }])))); };
  const L = makeLoader("data/", fetchFn);
  L.clear();
  const a = await L.load("cities.json.gz"); const b = await L.load("cities.json.gz");
  assert.equal(calls, 1); assert.equal(a, b);
  assert.deepEqual(await L.tier2("missing"), []);
  await assert.rejects(L.load("missing.json.gz"));
});
