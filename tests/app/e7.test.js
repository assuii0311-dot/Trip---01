import { test } from "node:test";
import assert from "node:assert/strict";
import { deriveKey, encryptJson, decryptJson, randomSalt, validateKey, sha256Hex } from "../../app/src/engines/e7/crypto.js";
import { makeGitHub, GitHubError } from "../../app/src/engines/e7/github.js";
import { makeSync, parseRepo, FILES } from "../../app/src/engines/e7/sync.js";
import { resolveRole, can, cleanSubs, isLogin, ROLE_LABEL } from "../../app/src/engines/e7/roles.js";
import { makeProposal, applyProposal, decideProposal, describeProposal, sortProposals, visibleProposals, validateProposal, proposalPath } from "../../app/src/engines/e7/proposals.js";

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
    state.calls = (state.calls || 0) + 1;
    state.cacheModes = (state.cacheModes || new Set()).add(opts.cache);
    if (m && (opts.method || "GET") === "GET") {
      const f = state.files[m[1]];
      if (f) return json(200, { content: btoa(unescape(encodeURIComponent(f.content))), encoding: "base64", sha: f.sha });
      const kids = Object.keys(state.files).filter((k) => k.startsWith(m[1] + "/")).sort(); // 디렉터리 목록
      return kids.length ? json(200, kids.map((k) => ({ name: k.split("/").pop(), path: k, sha: state.files[k].sha, type: "file" }))) : json(404, { message: "Not Found" });
    }
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
  assert.deepEqual([...st.cacheModes], ["no-cache"]); // 모든 호출이 최신 여부를 확인한다(브라우저의 60초 캐시를 그대로 쓰지 않는다)
  assert.deepEqual((await gh.listDir("o", "r", "none")).entries, []);
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

// --- 묶음 9: 역할, 제안과 승인(E7 4절 2항·6항, D-034)
test("roles: 계정과 역할 목록으로 메인·서브·공유자를 가른다", () => {
  const roles = { main: "Mina-Kim", sub: ["minsu", "@Jiho"] };
  assert.equal(resolveRole({ connected: false, hasToken: true, account: "mina-kim", roles }), "local");
  assert.equal(resolveRole({ connected: true, hasToken: true, account: "mina-kim", roles }), "main"); // 대소문자 무시
  assert.equal(resolveRole({ connected: true, hasToken: true, account: "Minsu", roles }), "sub");
  assert.equal(resolveRole({ connected: true, hasToken: true, account: "jiho", roles }), "sub");
  assert.equal(resolveRole({ connected: true, hasToken: true, account: "stranger", roles }), "viewer"); // 목록에 없는 계정은 열람만
  assert.equal(resolveRole({ connected: true, hasToken: false, account: null, roles }), "viewer");
  assert.equal(resolveRole({ connected: true, hasToken: true, account: null, roles }), "viewer"); // 계정 확인 실패
  assert.equal(resolveRole({ connected: true, hasToken: true, account: "mina-kim", roles: null }), "viewer");
  assert.equal(resolveRole({ connected: true, hasToken: true, account: "anyone", roles: { main: null, sub: [] } }), "main"); // 메인이 비어 있는 예전 저장소
  assert.equal(resolveRole({ connected: true, hasToken: false, account: null, roles: { main: null, sub: [] } }), "viewer");
  assert.ok(can("main", "edit") && can("main", "decide") && can("main", "manageRoles") && can("local", "edit"));
  assert.ok(can("sub", "propose") && can("sub", "viewProposals") && !can("sub", "edit") && !can("sub", "decide"));
  assert.ok(!can("viewer", "edit") && !can("viewer", "propose") && !can("viewer", "viewProposals") && !can("nobody", "edit"));
  assert.deepEqual(cleanSubs("Mina-Kim", [" minsu ", "@Jiho", "MINSU", "", "mina-kim", null]), ["minsu", "Jiho"]);
  assert.ok(isLogin("assuii0311-dot") && isLogin("@a") && !isLogin("-bad") && !isLogin("has space") && !isLogin(""));
  assert.equal(ROLE_LABEL.sub, "서브 수립자");
});

const PLAN = { trip: { start: "2027-05-01", end: "2027-05-03", cities: ["Q2807"] }, selection: ["Q1", "Q2"], custom: {}, days: { "2027-05-01": ["Q1"], "2027-05-02": ["Q2"] }, lodging: {}, reservations: {}, version: 1 };
const NOW = "2026-11-15T02:35:00.123Z";
const mk = (kind, target, value, memo) => makeProposal({ author: "minsu", kind, target, value, memo, base: "c1", now: NOW });

test("proposals: 만들기와 형식 검사", () => {
  const p = mk("move", { placeId: "Q1", name: "레티로 공원" }, { date: "2027-05-03" }, " 오전이 낫다 ");
  assert.equal(p.id, "20261115T023500123Z-minsu"); assert.equal(proposalPath(p.id), "proposals/20261115T023500123Z-minsu.json.enc");
  assert.equal(p.status, "pending"); assert.equal(p.memo, "오전이 낫다"); assert.equal(p.decided, null); assert.equal(p.base, "c1");
  assert.throws(() => mk("fly", { placeId: "Q1" }), /종류/); assert.throws(() => mk("move", {}, { date: "2027-05-03" }), /대상 장소/);
  assert.throws(() => mk("dwell", { placeId: "Q1" }, { minutes: 5 }), /15~600분/); assert.throws(() => mk("memo", {}, {}, "  "), /메모 내용/);
  assert.match(validateProposal({ kind: "memo", memo: "가".repeat(501) }), /500자/); assert.equal(validateProposal(p), null);
});

test("proposals: 적용은 새 plan을 돌려주고 입력을 바꾸지 않는다", () => {
  const before = JSON.stringify(PLAN);
  let r = applyProposal(PLAN, mk("add", { placeId: "Q3", name: "프라도" }, { date: "2027-05-03" }));
  assert.ok(r.ok); assert.deepEqual(r.plan.selection, ["Q1", "Q2", "Q3"]); assert.deepEqual(r.plan.days["2027-05-03"], ["Q3"]);
  r = applyProposal(PLAN, mk("add", { placeId: "Q3" }, {})); assert.ok(r.ok); assert.deepEqual(r.plan.days, PLAN.days);
  r = applyProposal(PLAN, mk("add", { placeId: "Q1" }, { date: "2027-05-03" })); assert.ok(r.ok); assert.deepEqual(r.plan.days["2027-05-01"], []); // 이미 선택된 곳은 날짜만 옮긴다
  assert.match(applyProposal(PLAN, mk("add", { placeId: "Q1" }, {})).reason, /이미 선택/);
  assert.match(applyProposal(PLAN, mk("add", { placeId: "Q3" }, { date: "2027-06-01" })).reason, /기간 밖/);
  r = applyProposal(PLAN, mk("remove", { placeId: "Q2" })); assert.deepEqual(r.plan.selection, ["Q1"]); assert.deepEqual(r.plan.days["2027-05-02"], []);
  assert.match(applyProposal(PLAN, mk("remove", { placeId: "Q9" })).reason, /선택되지 않은/);
  r = applyProposal(PLAN, mk("move", { placeId: "Q1" }, { date: "2027-05-02" })); assert.deepEqual(r.plan.days, { "2027-05-01": [], "2027-05-02": ["Q2", "Q1"] });
  r = applyProposal(PLAN, mk("move", { placeId: "Q1" }, { date: null })); assert.deepEqual(r.plan.days["2027-05-01"], []);
  assert.match(applyProposal(PLAN, mk("move", { placeId: "Q9" }, { date: "2027-05-02" })).reason, /선택되지 않은/);
  r = applyProposal(PLAN, mk("dwell", { placeId: "Q2" }, { minutes: 90 })); assert.deepEqual(r.plan.dwell, { Q2: 90 });
  r = applyProposal(PLAN, mk("memo", { placeId: "Q1" }, {}, "월요일 휴관 확인")); assert.equal(r.plan.notes.length, 1); assert.equal(r.plan.notes[0].text, "월요일 휴관 확인"); assert.equal(r.plan.notes[0].by, "minsu");
  assert.equal(applyProposal(r.plan, mk("memo", { placeId: "Q1" }, {}, "월요일 휴관 확인")).plan.notes.length, 1); // 같은 제안을 두 번 적용해도 메모는 하나
  const custom = { id: "user:abc", n: { local: "친구 집" }, lat: 40.4, lon: -3.7 };
  r = applyProposal(PLAN, mk("add", { placeId: "user:abc", place: custom }, {})); assert.deepEqual(r.plan.custom["user:abc"], custom);
  assert.equal(JSON.stringify(PLAN), before);
});

test("proposals: 결정, 한 줄 설명, 정렬, 역할별 보기", () => {
  const p = mk("move", { placeId: "Q2", name: "레티로 공원" }, { date: "2027-05-03", from: "2027-05-02" });
  const done = decideProposal(p, "approved", "mina", "2026-11-16T00:00:00.000Z");
  assert.equal(done.status, "approved"); assert.deepEqual(done.decided, { by: "mina", at: "2026-11-16T00:00:00.000Z", note: "" }); assert.equal(p.status, "pending");
  assert.throws(() => decideProposal(done, "rejected", "mina", NOW), /이미 처리/); assert.throws(() => decideProposal(p, "pending", "mina", NOW), /승인 또는 거절/);
  assert.equal(describeProposal(p), "5/2 레티로 공원 → 5/3 이동");
  assert.equal(describeProposal(mk("move", { placeId: "Q2" }, { date: null }), () => "레티로", () => "2027-05-02"), "5/2 레티로 → 미배치 이동");
  assert.equal(describeProposal(mk("add", { placeId: "Q3", name: "프라도" }, { date: "2027-05-01" })), "프라도 추가 (5/1)");
  assert.equal(describeProposal(mk("remove", { placeId: "Q3", name: "프라도" })), "프라도 삭제");
  assert.equal(describeProposal(mk("dwell", { placeId: "Q3", name: "프라도" }, { minutes: 120 })), "프라도 체류 120분");
  assert.equal(describeProposal(mk("memo", {}, {}, "숙소를 역 근처로")), "숙소를 역 근처로");
  assert.equal(describeProposal(mk("memo", { date: "2027-05-02" }, {}, "저녁은 가볍게")), "5/2: 저녁은 가볍게");
  const list = [{ ...done, id: "a", created: "2026-11-01" }, { ...p, id: "b", created: "2026-11-02" }, { ...p, id: "c", created: "2026-11-03", author: "Jiho" }];
  assert.deepEqual(sortProposals(list).map((x) => x.id), ["c", "b", "a"]);
  assert.equal(visibleProposals(list, "main", "mina").length, 3); assert.deepEqual(visibleProposals(list, "sub", "jiho").map((x) => x.id), ["c"]);
  assert.equal(visibleProposals(list, "viewer", "jiho").length, 0);
});

test("sync: 제안은 본문 파일을 바꾸지 않고, 승인하면 본문 커밋과 상태 커밋이 차례로 생긴다", async () => {
  const st = { files: {}, commits: {} };
  const sync = makeSync(mockGitHub(st));
  const cfg = { owner: "o", repo: "r", token: "t", passphrase: "a long passphrase 1" };
  await sync.init({ ...cfg, account: "mina" });
  let cur = await sync.load(cfg);
  const s0 = await sync.save({ ...cfg, key: cur.key, body: { roles: { main: "mina", sub: ["minsu"] }, plan: PLAN }, baseCommit: cur.commit, fileSha: cur.sha });
  const tripBefore = { ...st.files[FILES.trip] }, commitBefore = st.commits[FILES.trip];
  assert.deepEqual((await sync.listProposals({ ...cfg, key: cur.key })).proposals, []); // proposals/ 디렉터리가 없어도 빈 목록

  // 서브: 제안 두 건. 본문 파일과 본문의 최신 커밋은 그대로다(R-23)
  const p1 = makeProposal({ author: "minsu", kind: "move", target: { placeId: "Q1", name: "레티로" }, value: { date: "2027-05-03" }, now: "2026-11-15T01:00:00.000Z" });
  const p2 = makeProposal({ author: "minsu", kind: "remove", target: { placeId: "Q9", name: "없는 곳" }, now: "2026-11-15T02:00:00.000Z" });
  await sync.createProposal({ ...cfg, key: cur.key, proposal: p1 }); await sync.createProposal({ ...cfg, key: cur.key, proposal: p2 });
  assert.deepEqual(st.files[FILES.trip], tripBefore); assert.equal(st.commits[FILES.trip], commitBefore);
  assert.ok(!st.files[proposalPath(p1.id)].content.includes("레티로")); // 제안도 암호화되어 올라간다

  // 목록: 처음에는 디렉터리 1회 + 파일 2회, 캐시가 있으면 디렉터리 1회뿐
  let c0 = st.calls; const l1 = await sync.listProposals({ ...cfg, key: cur.key });
  assert.equal(st.calls - c0, 3); assert.deepEqual(l1.proposals.map((p) => p.id), [p1.id, p2.id]); assert.equal(l1.proposals[0].target.name, "레티로"); assert.equal(l1.unreadable, 0);
  c0 = st.calls; const l2 = await sync.listProposals({ ...cfg, key: cur.key, known: l1.cache }); assert.equal(st.calls - c0, 1); assert.equal(l2.proposals.length, 2);

  // 메인: 승인 = 본문에 반영해 저장 → 제안 상태 변경. 제안 커밋은 본문의 기준 버전을 바꾸지 않으므로 충돌이 아니다
  const applied = applyProposal(PLAN, l1.proposals[0]); assert.ok(applied.ok);
  const s1 = await sync.save({ ...cfg, key: cur.key, body: { roles: { main: "mina", sub: ["minsu"] }, plan: applied.plan }, baseCommit: s0.commit, fileSha: s0.sha, message: `승인 반영: ${p1.id}` });
  assert.equal(s1.conflict, false);
  const d1 = await sync.decide({ ...cfg, key: cur.key, proposal: l1.proposals[0], status: "approved", by: "mina" });
  assert.equal(d1.conflict, false); assert.equal(d1.proposal.status, "approved"); assert.notEqual(d1.commit, s1.commit);
  cur = await sync.load({ ...cfg, cachedKey: cur.key, cachedMeta: cur.meta });
  assert.deepEqual(cur.body.plan.days["2027-05-03"], ["Q1"]); assert.deepEqual(cur.body.roles.sub, ["minsu"]);

  // 적용할 수 없는 제안은 본문을 건드리지 않고 거절한다. 파일은 지우지 않는다
  assert.equal(applyProposal(cur.body.plan, l1.proposals[1]).ok, false);
  const d2 = await sync.decide({ ...cfg, key: cur.key, proposal: l1.proposals[1], status: "rejected", by: "mina", note: "선택에 없음" });
  const l3 = await sync.listProposals({ ...cfg, key: cur.key, known: l2.cache });
  assert.deepEqual(l3.proposals.map((p) => p.status), ["approved", "rejected"]); assert.equal(l3.proposals[1].decided.note, "선택에 없음"); assert.equal(Object.keys(st.files).filter((k) => k.startsWith("proposals/")).length, 2);
  // 다른 기기에서 이미 처리한 제안(오래된 blob SHA)은 conflict
  assert.equal((await sync.decide({ ...cfg, key: cur.key, proposal: l1.proposals[1], status: "approved", by: "mina" })).conflict, true);
  assert.equal(d2.proposal._sha, l3.proposals[1]._sha);
  // Key가 다르면 제안을 읽지 못한다(개수만 센다)
  const other = await (await import("../../app/src/engines/e7/crypto.js")).deriveKey("another passphrase!", cur.meta.kdf.salt, cur.meta.kdf.iterations);
  const l4 = await sync.listProposals({ ...cfg, key: other }); assert.equal(l4.proposals.length, 0); assert.equal(l4.unreadable, 2);
});
