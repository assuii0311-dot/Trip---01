// S8 설정(F-12·F-24·F-25). 여행 저장소·Key·토큰, 연결 확인, 초기화, 불러오기, 버전 표시, 출처 표기.
import { useState } from "../../lib.js";
import { html, Chip } from "../components/ui.js";
import { parseRepo } from "../../engines/e7/sync.js";
import { validateKey } from "../../engines/e7/crypto.js";
import { ROLE_LABEL, isLogin, normLogin } from "../../engines/e7/roles.js";

export function S8Settings({ data, cfg, setCfg, syncState, onCheck, onInit, onLoad, onSave, onDisconnect, onSetSubs, hasMine, onRestoreMine, onDropMine }) {
  const [busy, setBusy] = useState(null);
  const [newSub, setNewSub] = useState("");
  const [msg, setMsg] = useState(null);
  const repo = parseRepo(cfg.repo);
  const keyErr = cfg.key ? validateKey(cfg.key) : null;
  const run = async (label, fn) => { setBusy(label); setMsg(null); try { const m = await fn(); setMsg({ ok: true, text: m || `${label} 완료` }); } catch (e) { setMsg({ ok: false, text: `${label} 실패: ${e.message || e}` }); } finally { setBusy(null); } };
  const st = syncState || {};
  const subs = st.roles?.sub || [];
  const isMain = st.role === "main";
  const subErr = newSub.trim() && (!isLogin(newSub) ? "GitHub 계정 이름 형식이 아닙니다." : normLogin(newSub) === normLogin(st.roles?.main) ? "메인 수립자 계정입니다." : subs.some((s) => normLogin(s) === normLogin(newSub)) ? "이미 있는 계정입니다." : null);
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
        <button class="btn" disabled=${!st.connected || !isMain || busy} onClick=${() => run("저장", onSave)}>저장</button>
        ${st.connected && html`<button class="btn secondary" onClick=${onDisconnect}>연결 해제</button>`}
      </div>
      ${busy && html`<p class="note">${busy} 중…</p>`}
      ${msg && html`<p class=${msg.ok ? "note" : "error"} style=${msg.ok ? "" : "color:var(--err)"}>${msg.text}</p>`}
      <dl class="kv">
        <dt>상태</dt><dd>${st.connected ? html`<${Chip} kind="ok">연결됨</${Chip}>` : html`<${Chip} kind="x">연결 안 됨</${Chip}>`} ${st.dirty && html`<${Chip} kind="warn">저장 안 된 변경</${Chip}>`}</dd>
        <dt>역할</dt><dd>${ROLE_LABEL[st.role] || "—"}${st.account ? ` (${st.account})` : ""}${st.connected && cfg.token && !st.account ? html` <${Chip} kind="warn">토큰으로 계정 확인 실패</${Chip}>` : ""}</dd>
        ${st.connected && html`<dt>수립자</dt><dd>메인 ${st.roles?.main || "미기록"}${subs.length ? ` · 서브 ${subs.join(", ")}` : " · 서브 없음"}</dd>`}
        <dt>버전</dt><dd>${st.commit ? html`${st.commit.slice(0, 7)} · ${st.date ? new Date(st.date).toLocaleString("ko-KR") : ""} ${st.stale ? html`<${Chip} kind="warn">오래됨</${Chip}>` : html`<${Chip} kind="ok">최신</${Chip}>`}` : "—"}</dd>
        <dt>API 한도</dt><dd>${st.rate?.remaining != null ? `남은 호출 ${st.rate.remaining}/${st.rate.limit}` : "—"}</dd>
      </dl>
      ${hasMine && html`<div class="card" style="margin:8px 0"><div class="body"><div class="title">보존된 내 변경</div><p class="note">저장 충돌 때 "최신 불러오기"를 골라 기기에 남겨 둔 내 계획입니다. 다시 적용하면 지금 계획을 덮어쓰고, 저장해야 저장소에 반영됩니다.</p>
        <div class="row"><button class="btn secondary" disabled=${st.connected && !isMain} onClick=${() => { if (confirm("보존한 내 변경으로 지금 계획을 바꿉니다. 계속할까요?")) onRestoreMine(); }}>다시 적용</button><button class="btn secondary" onClick=${() => { if (confirm("보존한 내 변경을 지웁니다. 계속할까요?")) onDropMine(); }}>버리기</button></div></div></div>`}
    </section>
    ${st.connected && isMain && html`<section class="section"><h2>서브 수립자</h2>
      <p class="note">서브 수립자는 계획을 열람하고 제안을 보냅니다. 여기에 GitHub 계정을 적고, GitHub에서도 그 계정을 이 저장소의 공동 작업자로 추가해야 제안을 올릴 수 있습니다. 서브 수립자는 자기 토큰을 설정에 입력합니다.</p>
      ${subs.length === 0 ? html`<p class="note">등록된 서브 수립자가 없습니다.</p>` : html`<div class="chips">${subs.map((s) => html`<span class="chip on">${s} <button class="x" aria-label=${s + " 삭제"} disabled=${!!busy} onClick=${() => run("역할 변경", () => onSetSubs(subs.filter((x) => x !== s)))}>×</button></span>`)}</div>`}
      <div class="row" style="margin-top:8px"><input value=${newSub} placeholder="GitHub 계정 이름" aria-label="서브 수립자 계정" onInput=${(e) => setNewSub(e.target.value)} style="flex:1;min-height:40px;padding:6px 10px;border:1px solid var(--line);border-radius:8px" />
        <button class="btn secondary" disabled=${!newSub.trim() || !!subErr || !!busy} onClick=${() => run("역할 변경", async () => { const m = await onSetSubs([...subs, newSub.trim()]); setNewSub(""); return m; })}>추가</button></div>
      ${subErr && html`<span class="error" style="color:var(--err)">${subErr}</span>`}
    </section>`}
    <section class="section"><h2>출처 표기</h2><ul>${data.attribution.sources.map((s) => html`<li><a href=${s.url} target="_blank" rel="noopener">${s.source}</a> · ${s.license} · ${s.text}</li>`)}</ul>
      <p class="note">기준 데이터 생성일 ${data.attribution.generated}. 장소 ${data.attribution.counts.places.toLocaleString()}곳(1등급 ${data.attribution.counts.tier1.toLocaleString()}), 도시 ${data.attribution.counts.cities.toLocaleString()}. 데이터 라이선스는 저장소의 data/LICENSE-DATA.md. 지도: © OpenStreetMap contributors, OpenFreeMap.</p>
      <h2>앱 정보</h2><p class="note">Trip01 v0.1 (묶음 9). 역할: 메인 수립자는 편집·저장·승인, 서브 수립자는 열람·제안, 공유자는 열람.</p></section>
  </div>`;
}
