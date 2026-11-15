// E7 동기화 상태 기계(E7 4절). 읽기: 최신 커밋 → 파일 → 복호화. 쓰기: 기준 SHA 확인 → 암호화 → PUT(409면 충돌).
import { deriveKey, encryptJson, decryptJson, randomSalt, PBKDF2_ITERATIONS } from "./crypto.js";
import { GitHubError } from "./github.js";
import { PROPOSAL_DIR, proposalPath, decideProposal } from "./proposals.js";

export const FILES = { meta: "meta.json", trip: "trip.json.enc" };
export const FORMAT_VERSION = 1;

/** 저장소 주소 "owner/repo" 또는 GitHub URL을 {owner, repo}로 */
export function parseRepo(s) {
  const m = String(s || "").trim().match(/(?:github\.com\/)?([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+?)(?:\.git)?\/?$/);
  return m ? { owner: m[1], repo: m[2] } : null;
}

export function makeSync(gh) {
  /** 저장소 초기화(메인 수립자, 4절 10항): meta.json과 빈 본문을 올린다 */
  async function init({ owner, repo, token, passphrase, account }) {
    const salt = randomSalt();
    const meta = { format: FORMAT_VERSION, kdf: { name: "PBKDF2-SHA-256", iterations: PBKDF2_ITERATIONS, salt }, created: new Date().toISOString(), app: "Trip01" };
    const key = await deriveKey(passphrase, salt);
    const body = { roles: { main: account || null, sub: [] }, plan: null, updated: new Date().toISOString() };
    await gh.putFile(owner, repo, FILES.meta, JSON.stringify(meta, null, 1), "초기화: meta.json", { token });
    const put = await gh.putFile(owner, repo, FILES.trip, JSON.stringify(await encryptJson(body, key)), "초기화: 빈 계획", { token });
    return { meta, key, sha: put.sha, commit: put.commit, body };
  }

  /** 읽기(4절 3항): 호출 2회(최신 커밋, 파일). ETag로 변화 없음이면 1회 */
  async function load({ owner, repo, token, passphrase, cachedKey, etag, cachedMeta }) {
    const latest = await gh.latestCommit(owner, repo, FILES.trip, token, etag);
    if (latest.notModified) return { notModified: true, etag: latest.etag };
    if (!latest.sha) throw new Error("저장소에 계획 파일이 없습니다. 초기화가 필요합니다.");
    const meta = cachedMeta || JSON.parse((await gh.getFile(owner, repo, FILES.meta, { ref: latest.sha, token })).content);
    const key = cachedKey || (await deriveKey(passphrase, meta.kdf.salt, meta.kdf.iterations));
    const file = await gh.getFile(owner, repo, FILES.trip, { ref: latest.sha, token });
    const body = await decryptJson(JSON.parse(file.content), key);
    return { body, key, meta, sha: file.sha, commit: latest.sha, date: latest.date, etag: latest.etag, notModified: false };
  }

  /** 쓰기(4절 4~5항): 기준 커밋이 최신이 아니면 conflict. PUT 409도 conflict */
  async function save({ owner, repo, token, key, body, baseCommit, fileSha, message }) {
    const latest = await gh.latestCommit(owner, repo, FILES.trip, token);
    if (baseCommit && latest.sha && latest.sha !== baseCommit) return { conflict: true, latest: latest.sha, date: latest.date };
    const blob = await encryptJson({ ...body, updated: new Date().toISOString() }, key);
    try {
      const put = await gh.putFile(owner, repo, FILES.trip, JSON.stringify(blob), message || "저장", { sha: fileSha, token });
      return { conflict: false, sha: put.sha, commit: put.commit };
    } catch (e) {
      if (e instanceof GitHubError && e.status === 409) return { conflict: true, latest: null };
      throw e;
    }
  }
  /**
   * 제안 목록(4절 6항). 호출: 디렉터리 1회 + 새로 생겼거나 바뀐 파일마다 1회.
   * known은 앞서 읽은 것(경로 → {sha, proposal})이며, blob SHA가 같으면 다시 받지 않는다.
   * 반환: proposals(각 항목에 _path, _sha가 붙는다), cache(다음 호출의 known), unreadable(복호화하지 못한 파일 수)
   */
  async function listProposals({ owner, repo, token, key, known }) {
    const { entries, rate } = await gh.listDir(owner, repo, PROPOSAL_DIR, { token });
    const cache = new Map(), proposals = [];
    let unreadable = 0;
    for (const e of entries) {
      if (e.type !== "file" || !e.name.endsWith(".json.enc")) continue;
      let rec = known && known.get(e.path);
      if (!rec || rec.sha !== e.sha) {
        try { const f = await gh.getFile(owner, repo, e.path, { token }); rec = { sha: f.sha, proposal: await decryptJson(JSON.parse(f.content), key) }; }
        catch { rec = { sha: e.sha, proposal: null }; }
      }
      cache.set(e.path, rec);
      if (rec.proposal) proposals.push({ ...rec.proposal, _path: e.path, _sha: rec.sha }); else unreadable++;
    }
    return { proposals, cache, unreadable, rate };
  }

  /** 제안 작성(서브): proposals/ 아래 새 파일 하나. 본문 파일은 건드리지 않는다 */
  async function createProposal({ owner, repo, token, key, proposal }) {
    const put = await gh.putFile(owner, repo, proposalPath(proposal.id), JSON.stringify(await encryptJson(proposal, key)), `제안: ${proposal.id}`, { token });
    return { sha: put.sha, commit: put.commit };
  }

  /** 제안의 상태를 승인 또는 거절로 바꾼다(메인). 파일은 지우지 않고 다시 쓴다. 다른 기기에서 먼저 처리했으면 conflict */
  async function decide({ owner, repo, token, key, proposal, status, by, note }) {
    const { _path, _sha, ...plain } = proposal;
    const next = decideProposal(plain, status, by, new Date().toISOString(), note);
    try {
      const put = await gh.putFile(owner, repo, _path || proposalPath(plain.id), JSON.stringify(await encryptJson(next, key)), `${status === "approved" ? "승인" : "거절"}: ${plain.id}`, { sha: _sha, token });
      return { conflict: false, proposal: { ...next, _path: _path || proposalPath(plain.id), _sha: put.sha }, commit: put.commit };
    } catch (e) {
      if (e instanceof GitHubError && e.status === 409) return { conflict: true };
      throw e;
    }
  }
  return { init, load, save, listProposals, createProposal, decide };
}
