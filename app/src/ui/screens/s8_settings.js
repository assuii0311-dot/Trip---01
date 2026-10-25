// S8 설정(F-12·F-24·F-25). 여행 저장소·Key·토큰, 연결 확인, 초기화, 불러오기, 버전 표시, 출처 표기.
import { useState } from "../../lib.js";
import { html, Chip } from "../components/ui.js";
import { parseRepo } from "../../engines/e7/sync.js";
import { validateKey } from "../../engines/e7/crypto.js";

export function S8Settings({ data, cfg, setCfg, syncState, onCheck, onInit, onLoad, onSave, onDisconnect }) {
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const repo = parseRepo(cfg.repo);
  const keyErr = cfg.key ? validateKey(cfg.key) : null;
  const run = async (label, fn) => { setBusy(label); setMsg(null); try { const m = await fn(); setMsg({ ok: true, text: m || `${label} 완료` }); } catch (e) { setMsg({ ok: false, text: `${label} 실패: ${e.message || e}` }); } finally { setBusy(null); } };
  const st = syncState || {};
  return html`<div>
    <section class="section"><h2>여행 저장소 (E7)</h2>
      <p class="note">여행마다 공개 GitHub 저장소 하나를 씁니다. 저장소에는 Key로 암호화된 파일만 올라갑니다(D-011). Key와 토큰은 이 기기에만 저장됩니다.</p>
      <div class="field"><label>저장소 (owner/repo)</label><input value=${cfg.repo || ""} placeholder="예: assuii0311-dot/trip-2027-es" onInput=${(e) => setCfg({ ...cfg, repo: e.target.value })} />${cfg.repo && !repo && html`<span class="error">형식이 맞지 않습니다.</span>`}</div>
      <div class="field"><label>Key (비밀 문구, 12자 이상)</label><input type="password" value=${cfg.key || ""} onInput=${(e) => setCfg({ ...cfg, key: e.target.value })} />${keyErr && html`<span class="error">${keyErr}</span>`}</div>
      <div class="field"><label>개인 접근 토큰 (수립자만. 이 저장소 하나, Contents 쓰기, 만료 90일 권고)</label><input type="password" value=${cfg.token || ""} placeholder="공유자는 비워 둡니다" onInput=${(e) => setCfg({ ...cfg, token: e.target.value })} /></div>
      <div class="row">
        <button class="btn secondary" disabled=${!repo || busy} onClick=${() => run("연결 확인", onCheck)}>연결 확인</button>
        <button class="btn secondary" disabled=${!repo || !cfg.key || keyErr || busy} onClick=${() => run("불러오기", onLoad)}>불러오기</button>
        <button class="btn secondary" disabled=${!repo || !cfg.key || keyErr || !cfg.token || busy} onClick=${() => { if (confirm("저장소를 초기화합니다. 기존 계획 파일이 있으면 덮어씁니다. 계속할까요?")) run("초기화", onInit); }}>초기화(첫 저장)</button>
        <button class="btn" disabled=${!st.connected || !cfg.token || busy} onClick=${() => run("저장", onSave)}>저장</button>
        ${st.connected && html`<button class="btn secondary" onClick=${onDisconnect}>연결 해제</button>`}
      </div>
      ${busy && html`<p class="note">${busy} 중…</p>`}
      ${msg && html`<p class=${msg.ok ? "note" : "error"} style=${msg.ok ? "" : "color:var(--err)"}>${msg.text}</p>`}
      <dl class="kv">
        <dt>상태</dt><dd>${st.connected ? html`<${Chip} kind="ok">연결됨</${Chip}>` : html`<${Chip} kind="x">연결 안 됨</${Chip}>`} ${st.dirty && html`<${Chip} kind="warn">저장 안 된 변경</${Chip}>`}</dd>
        <dt>역할</dt><dd>${st.role || "—"}${st.account ? ` (${st.account})` : ""}</dd>
        <dt>버전</dt><dd>${st.commit ? html`${st.commit.slice(0, 7)} · ${st.date ? new Date(st.date).toLocaleString("ko-KR") : ""} ${st.stale ? html`<${Chip} kind="warn">오래됨</${Chip}>` : html`<${Chip} kind="ok">최신</${Chip}>`}` : "—"}</dd>
        <dt>API 한도</dt><dd>${st.rate?.remaining != null ? `남은 호출 ${st.rate.remaining}/${st.rate.limit}` : "—"}</dd>
      </dl>
    </section>
    <section class="section"><h2>출처 표기</h2><ul>${data.attribution.sources.map((s) => html`<li><a href=${s.url} target="_blank" rel="noopener">${s.source}</a> · ${s.license} · ${s.text}</li>`)}</ul>
      <p class="note">기준 데이터 생성일 ${data.attribution.generated}. 장소 ${data.attribution.counts.places.toLocaleString()}곳(1등급 ${data.attribution.counts.tier1.toLocaleString()}), 도시 ${data.attribution.counts.cities.toLocaleString()}. 데이터 라이선스는 저장소의 data/LICENSE-DATA.md. 지도: © OpenStreetMap contributors, OpenFreeMap.</p>
      <h2>앱 정보</h2><p class="note">Trip01 v0.1 (묶음 4). 제안·승인(서브 수립자)은 묶음 9에서 제공됩니다.</p></section>
  </div>`;
}
