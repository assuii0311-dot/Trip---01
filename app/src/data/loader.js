// 기준 데이터 적재(05-architecture 5절). .json.gz를 DecompressionStream으로 풀고 메모리에 캐시한다.
// IndexedDB 캐시는 묶음 4(저장)에서 붙인다. 지금은 브라우저 HTTP 캐시에 맡긴다.
const mem = new Map();

/** gzip 응답 본문을 JSON으로. 서버가 이미 풀어 보낸 경우(Content-Encoding으로 해제됨)도 처리한다. */
export async function decodeGzipResponse(res) {
  const buf = await res.arrayBuffer();
  const bytes = new Uint8Array(buf);
  const isGzip = bytes.length > 2 && bytes[0] === 0x1f && bytes[1] === 0x8b;
  if (!isGzip) return JSON.parse(new TextDecoder().decode(bytes));
  if (typeof DecompressionStream === "undefined") throw new Error("이 브라우저는 압축 데이터를 풀 수 없습니다(DecompressionStream 없음).");
  const ds = new DecompressionStream("gzip");
  const stream = new Blob([bytes]).stream().pipeThrough(ds);
  const text = await new Response(stream).text();
  return JSON.parse(text);
}

export function makeLoader(base = "data/", fetchFn = globalThis.fetch) {
  async function load(name) {
    if (mem.has(name)) return mem.get(name);
    const p = (async () => {
      const res = await fetchFn(base + name, { cache: "default" });
      if (!res.ok) throw new Error(`${name} ${res.status}`);
      return name.endsWith(".gz") ? decodeGzipResponse(res) : res.json();
    })();
    mem.set(name, p);
    try { return await p; } catch (e) { mem.delete(name); throw e; }
  }
  return {
    load,
    attribution: () => load("attribution.json"),
    cities: () => load("cities.json.gz"),
    regions: () => load("regions.json.gz"),
    categories: () => load("categories.json.gz"),
    airports: () => load("airports.json.gz"),
    tier1: () => load("places_tier1.json.gz"),
    tier2: (cityId) => load(`places_tier2/${cityId}.json.gz`).catch(() => []),
    sourceShard: (shard) => load(`sources/${shard}.json.gz`).catch(() => ({})),
    clear: () => mem.clear(),
  };
}
