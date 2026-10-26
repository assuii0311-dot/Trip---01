// E7 GitHub 호출 계층(E7 4절 3~4항, 05-architecture 6절). fetch를 주입받는 순수 모듈. 호출 수를 최소로 한다.
const API = "https://api.github.com";

export class GitHubError extends Error {
  constructor(status, message, body) { super(message); this.status = status; this.body = body; }
}

export function makeGitHub(fetchFn = globalThis.fetch) {
  async function call(path, { method = "GET", token, body, etag } = {}) {
    const headers = { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (etag) headers["If-None-Match"] = etag;
    if (body) headers["Content-Type"] = "application/json";
    const res = await fetchFn(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
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
    /** 파일 생성·갱신. sha는 갱신 시 현재 blob SHA(불일치면 GitHub가 409). 반환: 새 blob SHA와 커밋 SHA */
    async putFile(owner, repo, path, content, message, { sha, token, branch } = {}) {
      const b64 = btoa(String.fromCharCode(...new TextEncoder().encode(content)));
      const body = { message, content: b64 };
      if (sha) body.sha = sha;
      if (branch) body.branch = branch;
      const r = await call(`/repos/${owner}/${repo}/contents/${path}`, { method: "PUT", token, body });
      return { sha: r.data.content.sha, commit: r.data.commit.sha, rate: r.rate };
    },
  };
}
