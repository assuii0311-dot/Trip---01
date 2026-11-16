// E7 GitHub 호출 계층(E7 4절 3~4항, 05-architecture 6절). fetch를 주입받는 순수 모듈. 호출 수를 최소로 한다.
const API = "https://api.github.com";

export class GitHubError extends Error {
  constructor(status, message, body) { super(message); this.status = status; this.body = body; }
}

export const MAX_FILE_BYTES = 1024 * 1024; // GitHub 읽기 API가 본문을 함께 돌려주는 한도(문서 기준 1MB 이하)
export const SAFE_FILE_BYTES = Math.floor(MAX_FILE_BYTES * 0.8); // 여유 20%를 둔 올리기 한도(D-042). 넘으면 올리지 않는다

/**
 * 글을 UTF-8 바이트로 바꿔 base64로 만든다. 한 번에 바꾸면 브라우저 엔진의 함수 인자 수 한도에 걸리므로
 * (실측: 크롬 124,745바이트, 문서: 사파리 65,536개) 32,768바이트씩 나눠 바꾼다(T-051).
 */
export function utf8ToB64(text) {
  const bytes = new TextEncoder().encode(text); let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return { b64: btoa(bin), bytes: bytes.length };
}

export function makeGitHub(fetchFn = globalThis.fetch) {
  async function call(path, { method = "GET", token, body, etag } = {}) {
    const headers = { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (etag) headers["If-None-Match"] = etag;
    if (body) headers["Content-Type"] = "application/json";
    // cache "no-cache": 브라우저 캐시를 쓰더라도 매번 서버에 최신 여부를 확인한다. GitHub 응답은 60초 캐시가 붙어 있어, 기본값이면 다른 기기의 저장·승인이 1분까지 보이지 않는다
    const res = await fetchFn(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined, cache: "no-cache" });
    const rate = { limit: res.headers.get("x-ratelimit-limit"), remaining: res.headers.get("x-ratelimit-remaining") };
    if (res.status === 304) return { status: 304, data: null, etag, rate };
    const text = await res.text();
    let data = null; try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    if (!res.ok) throw new GitHubError(res.status, (data && data.message) || `GitHub ${res.status}`, data);
    return { status: res.status, data, etag: res.headers.get("etag"), rate };
  }
  return {
    call,
    /** 저장소 존재·공개 여부와 기본 브랜치 */
    repo: (owner, repo, token) => call(`/repos/${owner}/${repo}`, { token }),
    user: (token) => call("/user", { token }),
    /** 경로의 최신 커밋 SHA(없으면 null). 호출 1회 */
    async latestCommit(owner, repo, path, token, etag) {
      const r = await call(`/repos/${owner}/${repo}/commits?path=${encodeURIComponent(path)}&per_page=1`, { token, etag });
      if (r.status === 304) return { sha: undefined, etag: r.etag, notModified: true, rate: r.rate };
      const c = Array.isArray(r.data) && r.data[0];
      return { sha: c ? c.sha : null, date: c ? c.commit?.committer?.date : null, etag: r.etag, notModified: false, rate: r.rate };
    },
    /** 파일 내용(문자열)과 blob SHA. ref는 커밋 SHA 또는 브랜치 */
    async getFile(owner, repo, path, { ref, token } = {}) {
      const r = await call(`/repos/${owner}/${repo}/contents/${path}${ref ? `?ref=${encodeURIComponent(ref)}` : ""}`, { token });
      const d = r.data;
      const content = d.encoding === "base64" ? new TextDecoder().decode(Uint8Array.from(atob(d.content.replace(/\n/g, "")), (c) => c.charCodeAt(0))) : d.content;
      return { content, sha: d.sha, rate: r.rate };
    },
    /** 디렉터리의 파일 목록 [{name, path, sha, type}]. 디렉터리가 없으면 빈 목록. 호출 1회 */
    async listDir(owner, repo, path, { token } = {}) {
      try {
        const r = await call(`/repos/${owner}/${repo}/contents/${path}`, { token });
        return { entries: Array.isArray(r.data) ? r.data.map((e) => ({ name: e.name, path: e.path, sha: e.sha, type: e.type })) : [], rate: r.rate };
      } catch (e) {
        if (e instanceof GitHubError && e.status === 404) return { entries: [], rate: null };
        throw e;
      }
    },
    /** 파일 생성·갱신. sha는 갱신 시 현재 blob SHA(불일치면 GitHub가 409). SAFE_FILE_BYTES를 넘으면 호출하지 않고 413 오류. 반환: 새 blob SHA와 커밋 SHA */
    async putFile(owner, repo, path, content, message, { sha, token, branch } = {}) {
      const { b64, bytes } = utf8ToB64(content);
      const kb = (n) => Math.round(n / 1024);
      if (bytes > SAFE_FILE_BYTES) throw new GitHubError(413, `파일이 너무 큽니다(${kb(bytes)}KB). 여행 저장소에 올릴 수 있는 크기는 ${kb(SAFE_FILE_BYTES)}KB까지입니다. 장소나 메모를 줄여 주세요.`, { tooLarge: true, bytes, limit: SAFE_FILE_BYTES });
      const body = { message, content: b64 };
      if (sha) body.sha = sha;
      if (branch) body.branch = branch;
      const r = await call(`/repos/${owner}/${repo}/contents/${path}`, { method: "PUT", token, body });
      return { sha: r.data.content.sha, commit: r.data.commit.sha, rate: r.rate };
    },
  };
}
