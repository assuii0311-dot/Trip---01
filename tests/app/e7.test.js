import { test } from "node:test";
import assert from "node:assert/strict";
import { deriveKey, encryptJson, decryptJson, randomSalt, validateKey, sha256Hex } from "../../app/src/engines/e7/crypto.js";
import { makeGitHub, GitHubError } from "../../app/src/engines/e7/github.js";
import { makeSync, parseRepo, FILES } from "../../app/src/engines/e7/sync.js";

test("crypto: 암호화 왕복, 다른 Key로는 복호화 실패, IV는 매번 다름", async () => {
  const salt = randomSalt();
  const k1 = await deriveKey("correct horse battery", salt, 1000), k2 = await deriveKey("wrong key phrase!", salt, 1000);
  const obj = { plan: { cities: ["Q2807"] }, 한글: "프라도" };
  const b1 = await encryptJson(obj, k1), b2 = await encryptJson(obj, k1);
  assert.equal(b1.v, 1); assert.notEqual(b1.iv, b2.iv);
  assert.deepEqual(await decryptJson(b1, k1), obj);
  await assert.rejects(decryptJson(b1, k2), /복호화 실패/);
  assert.ok(!b1.data.includes("Q2807"));
  assert.equal(validateKey("short"), "Key는 12자 이상이어야 합니다."); assert.equal(validateKey("twelve chars!"), null);
  assert.equal((await sha256Hex("abc")).slice(0, 8), "ba7816bf");
});

function mockGitHub(state) {
  // state.files: path → {content, sha}; state.commits: path → sha. PUT은 sha 불일치면 409
  const fetchFn = async (url, opts = {}) => {
    const u = new URL(url); const p = u.pathname; const headers = { "x-ratelimit-remaining": "59", etag: '"e1"' };
    const json = (status, data) => new Response(JSON.stringify(data), { status, headers });
    if (p.endsWith("/commits")) { const path = u.searchParams.get("path"); const sha = state.commits[path]; return json(200, sha ? [{ sha, commit: { committer: { date: "2026-10-25T00:00:00Z" } } }] : []); }
    const m = p.match(/\/contents\/(.+)$/);
    if (m && (opts.method || "GET") === "GET") { const f = state.files[m[1]]; return f ? json(200, { content: btoa(unescape(encodeURIComponent(f.content))), encoding: "base64", sha: f.sha }) : json(404, { message: "Not Found" }); }
    if (m && opts.method === "PUT") {
      const body = JSON.parse(opts.body); const f = state.files[m[1]];
      if (f && body.sha !== f.sha) return json(409, { message: "sha mismatch" });
      const sha = "blob" + (state.n = (state.n || 0) + 1); const commit = "c" + state.n;
      state.files[m[1]] = { content: decodeURIComponent(escape(atob(body.content))), sha }; state.commits[m[1]] = commit;
      return json(f ? 200 : 201, { content: { sha }, commit: { sha: commit } });
    }
    if (p.endsWith("/user")) return json(200, { login: "tester" });
    return json(200, { default_branch: "main", private: false });
  };
  return makeGitHub(fetchFn);
}

test("github: 최신 커밋, 파일 읽기, PUT 409 → GitHubError", async () => {
  const st = { files: { "a.txt": { content: "hi", sha: "s1" } }, commits: { "a.txt": "c0" } };
  const gh = mockGitHub(st);
  assert.equal((await gh.latestCommit("o", "r", "a.txt")).sha, "c0"); assert.equal((await gh.latestCommit("o", "r", "none")).sha, null);
  assert.equal((await gh.getFile("o", "r", "a.txt")).content, "hi");
  await assert.rejects(gh.putFile("o", "r", "a.txt", "x", "m", { sha: "wrong" }), (e) => e instanceof GitHubError && e.status === 409);
  const put = await gh.putFile("o", "r", "a.txt", "x", "m", { sha: "s1" }); assert.ok(put.commit);
});

test("sync: 초기화 → 읽기 → 저장 → 다른 기기의 저장 뒤 충돌 감지", async () => {
  const st = { files: {}, commits: {} };
  const sync = makeSync(mockGitHub(st));
  const cfg = { owner: "o", repo: "r", token: "t", passphrase: "a long passphrase 1" };
  const ini = await sync.init({ ...cfg, account: "tester" });
  assert.ok(st.files[FILES.meta] && st.files[FILES.trip]);
  const l1 = await sync.load(cfg);
  assert.equal(l1.body.roles.main, "tester"); assert.equal(l1.commit, ini.commit);
  const s1 = await sync.save({ ...cfg, key: l1.key, body: { ...l1.body, plan: { x: 1 } }, baseCommit: l1.commit, fileSha: l1.sha });
  assert.equal(s1.conflict, false);
  // 다른 기기: 오래된 기준으로 저장 → 충돌
  const s2 = await sync.save({ ...cfg, key: l1.key, body: { ...l1.body, plan: { x: 2 } }, baseCommit: l1.commit, fileSha: l1.sha });
  assert.equal(s2.conflict, true);
  const l2 = await sync.load({ ...cfg, cachedKey: l1.key, cachedMeta: l1.meta });
  assert.deepEqual(l2.body.plan, { x: 1 });
  const l3 = await sync.load({ ...cfg, cachedKey: l1.key, cachedMeta: l1.meta, etag: '"e1"' });
  assert.equal(l3.notModified, false);
  await assert.rejects(sync.load({ ...cfg, passphrase: "another passphrase!" }), /복호화 실패/);
});

test("parseRepo: owner/repo와 URL", () => {
  assert.deepEqual(parseRepo("assuii0311-dot/trip-2027-es"), { owner: "assuii0311-dot", repo: "trip-2027-es" });
  assert.deepEqual(parseRepo("https://github.com/o/r.git"), { owner: "o", repo: "r" });
  assert.equal(parseRepo("nope"), null);
});
