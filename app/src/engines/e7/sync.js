// E7 동기화 상태 기계(E7 4절). 읽기: 최신 커밋 → 파일 → 복호화. 쓰기: 기준 SHA 확인 → 암호화 → PUT(409면 충돌).
import { deriveKey, encryptJson, decryptJson, randomSalt, PBKDF2_ITERATIONS } from "./crypto.js";
import { GitHubError } from "./github.js";

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
  return { init, load, save };
}
