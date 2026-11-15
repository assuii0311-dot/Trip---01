// S7 공유(F-13·F-22·F-23). 제안·승인, 내보내기·가져오기, My Maps 파일, 하루 경유지 링크, 공유 링크.
import { useState } from "../../lib.js";
import { html, Empty } from "../components/ui.js";
import { toKML, toCSV, checkLimits, dayRouteLinks, exportPlanJson, importPlanJson, fileName } from "../../engines/export.js";
import { placeName } from "../../data/places.js";
import { describeProposal, sortProposals, visibleProposals, STATUS_LABEL, KIND_LABEL } from "../../engines/e7/proposals.js";

function download(name, text, type) {
  const blob = new Blob([text], { type }); const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** 제안 구역: 메인은 전체 목록과 승인·거절, 서브는 자기 제안의 상태와 메모 제안, 그 밖의 역할은 안내만 */
function Proposals({ plan, getPlace, role, account, proposals, onRefresh, onDecide, onProposeMemo }) {
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const nameOf = (id) => { const p = getPlace(id); return p ? placeName(p) : null; };
  const dayOf = (id) => Object.keys(plan.days || {}).find((d) => (plan.days[d] || []).includes(id)) || null;
  const run = async (key, fn) => { setBusy(key); setMsg(null); try { const m = await fn(); setMsg({ ok: true, text: m }); } catch (e) { setMsg({ ok: false, text: e.message || String(e) }); } finally { setBusy(null); } };
  if (role !== "main" && role !== "sub") return html`<section class="section"><h2>제안</h2><p class="note">${role === "viewer" ? "공유자는 계획을 열람만 합니다. 제안은 서브 수립자가 보내고 메인 수립자가 승인합니다." : "여행 저장소에 연결하면 서브 수립자의 제안을 여기서 받고 승인할 수 있습니다."}</p></section>`;
  const list = sortProposals(visibleProposals(proposals.list, role, account));
  const pending = list.filter((p) => p.status === "pending").length;
  return html`<section class="section proposals"><h2>제안 ${pending > 0 ? html`<span class="chip warn">${pending} 대기</span>` : html`<span class="chip x">대기 없음</span>`}
      <button class="btn secondary small" disabled=${!!busy} onClick=${() => run("refresh", onRefresh)}>새로 고침</button></h2>
    ${role === "sub" && html`<p class="note">장소의 선택, 날짜, 체류 시간을 바꾸면 제안으로 보내집니다. 그 밖의 의견은 메모로 보내세요.</p><div class="row"><button class="btn secondary" onClick=${onProposeMemo}>메모 제안 쓰기</button></div>`}
    ${!proposals.loaded ? html`<p class="note">제안을 읽는 중…</p>` : list.length === 0 ? html`<p class="note">${role === "main" ? "받은 제안이 없습니다." : "보낸 제안이 없습니다."}</p>`
      : list.map((p) => html`<div class=${"card proposal " + p.status} key=${p.id}><div class="body">
          <div class="title">${describeProposal(p, nameOf, dayOf)}</div>
          <div class="chips meta"><span class="chip">${KIND_LABEL[p.kind]}</span><span class=${"chip " + (p.status === "pending" ? "warn" : p.status === "approved" ? "ok" : "x")}>${STATUS_LABEL[p.status]}</span><span class="note">${p.author} · ${new Date(p.created).toLocaleString("ko-KR")}</span></div>
          ${p.memo && p.kind !== "memo" && html`<p class="note">“${p.memo}”</p>`}
          ${p.decided && html`<p class="note">${STATUS_LABEL[p.status]}: ${p.decided.by} · ${new Date(p.decided.at).toLocaleString("ko-KR")}${p.decided.note ? ` · ${p.decided.note}` : ""}</p>`}
          ${role === "main" && p.status === "pending" && html`<div class="row"><button class="btn small" disabled=${!!busy} onClick=${() => run(p.id, () => onDecide(p, "approved"))}>${busy === p.id ? "처리 중…" : "승인"}</button><button class="btn secondary small" disabled=${!!busy} onClick=${() => run(p.id, () => onDecide(p, "rejected"))}>거절</button></div>`}
        </div></div>`)}
    ${proposals.unreadable > 0 && html`<p class="note">읽지 못한 제안 파일 ${proposals.unreadable}개(Key가 다르거나 손상됨).</p>`}
    ${msg && html`<p class=${msg.ok ? "note" : "error"} style=${msg.ok ? "" : "color:var(--err)"}>${msg.text}</p>`}
  </section>`;
}

export function S7Share({ plan, getPlace, cities, cfg, onImport, role = "local", account, proposals = { list: [], loaded: false, unreadable: 0 }, onRefreshProposals, onDecide, onProposeMemo }) {
  const [scope, setScope] = useState("itinerary");
  const [msg, setMsg] = useState(null);
  const cityName = (id) => { const c = cities.find((x) => x.id === id); return c ? c.n.ko || c.n.en || c.n.es : id; };
  const dayPlaces = (plan.itinerary?.days || []).flatMap((d) => d.items.filter((i) => i.kind === "place").map((i) => ({ p: getPlace(i.id), date: d.date }))).filter((x) => x.p);
  const selPlaces = plan.selection.map((id) => getPlace(id)).filter(Boolean);
  const places = scope === "itinerary" && dayPlaces.length ? dayPlaces.map((x) => x.p) : selPlaces;
  const dateOf = new Map(dayPlaces.map((x) => [x.p.id, x.date]));
  const descOf = (p) => [p.cat?.[0], cityName(p.city), dateOf.get(p.id)].filter(Boolean).join(" / ");
  const kml = toKML(places, { name: `Trip01 ${plan.trip.start || ""}`, descOf });
  const lim = checkLimits(places, kml);
  const shareUrl = cfg?.repo ? `${location.origin}${location.pathname}?repo=${encodeURIComponent(cfg.repo)}` : null;
  const onFile = async (e) => { const f = e.target.files[0]; if (!f) return; try { const p = importPlanJson(await f.text()); onImport(p); setMsg({ ok: true, text: `가져옴: 선택 ${p.selection.length}곳` }); } catch (err) { setMsg({ ok: false, text: err.message }); } e.target.value = ""; };
  const notes = plan.notes || [];
  const canImport = role === "main" || role === "local";
  return html`<div>
    <${Proposals} plan=${plan} getPlace=${getPlace} role=${role} account=${account} proposals=${proposals} onRefresh=${onRefreshProposals} onDecide=${onDecide} onProposeMemo=${onProposeMemo} />
    ${notes.length > 0 && html`<section class="section"><h2>메모 <span class="note">승인된 메모 제안</span></h2>${notes.map((n) => { const p = n.placeId && getPlace(n.placeId); return html`<p class="memo">${p ? html`<b>${placeName(p)}</b>: ` : n.date ? html`<b>${n.date}</b>: ` : ""}${n.text} <span class="note">— ${n.by}</span></p>`; })}</section>`}
    <section class="section"><h2>구글맵 일괄 저장 (R-27)</h2>
      <div class="seg" style="max-width:320px"><button class=${scope === "itinerary" ? "on" : ""} onClick=${() => setScope("itinerary")}>일정 장소 ${dayPlaces.length}</button><button class=${scope === "selection" ? "on" : ""} onClick=${() => setScope("selection")}>선택 전체 ${selPlaces.length}</button></div>
      <p class="note">Google My Maps에서 "가져오기"로 KML 또는 CSV를 올리면 장소가 한 번에 표시됩니다. 한도: CSV 2,000행, KML 5MB. 현재 ${lim.rows}행, KML ${(lim.kmlBytes / 1000).toFixed(0)}KB ${lim.rowsOk && lim.kmlOk ? "✓" : "⚠ 한도 초과"}</p>
      <div class="row"><button class="btn secondary" disabled=${!places.length || !lim.kmlOk} onClick=${() => download(fileName("kml"), kml, "application/vnd.google-earth.kml+xml")}>KML 내려받기</button><button class="btn secondary" disabled=${!places.length || !lim.rowsOk} onClick=${() => download(fileName("csv"), toCSV(places, { descOf }), "text/csv")}>CSV 내려받기</button></div>
    </section>
    <section class="section"><h2>하루 경유지 링크</h2>
      ${!plan.itinerary ? html`<p class="note">일정을 생성하면 날짜별 구글맵 경로 링크가 생깁니다(경유지 모바일 3개 단위로 나눔).</p>` : plan.itinerary.days.map((d, i) => { const links = dayRouteLinks(d.items, getPlace, d.origin || null); return html`<div class="card" style="margin:0 0 8px"><div class="body"><div class="title">${i + 1}일 ${d.date} <span class="note">${cityName(d.cityId)} · ${links.length}구간</span></div>
        ${links.length === 0 ? html`<div class="note">장소 없음</div>` : links.map((l, k) => html`<div class="row" style="padding:4px 0"><a href=${l.url} target="_blank" rel="noopener">구간 ${k + 1}: ${l.from.name} → ${l.via.map((v) => v.name).join(" → ")}${l.via.length ? " → " : ""}${l.to.name}</a></div>`)}</div></div>`; })}
    </section>
    <section class="section"><h2>계획 파일 (R-09)</h2>
      <div class="row"><button class="btn secondary" onClick=${() => download(fileName("json"), exportPlanJson(plan), "application/json")}>JSON 내려받기</button>${canImport && html`<label class="btn secondary" style="display:inline-flex;align-items:center">가져오기 <input type="file" accept="application/json,.json" style="display:none" onChange=${onFile} /></label>`}</div>
      ${msg && html`<p class=${msg.ok ? "note" : "error"} style=${msg.ok ? "" : "color:var(--err)"}>${msg.text}</p>`}
      <p class="note">평문 JSON입니다. 가져오면 현재 계획을 덮어쓰고 기기에 저장됩니다(연결된 저장소에는 "저장"을 눌러야 반영).</p>
    </section>
    <section class="section"><h2>공유 링크</h2>
      ${shareUrl ? html`<p class="note">공유자는 이 링크를 열고 Key를 따로 입력합니다(Key는 링크에 넣지 않습니다, E7).</p><div class="row"><input readonly value=${shareUrl} style="flex:1;min-height:40px;padding:6px 10px;border:1px solid var(--line);border-radius:8px" /><button class="btn secondary" onClick=${async () => { try { await navigator.clipboard.writeText(shareUrl); setMsg({ ok: true, text: "링크를 복사했습니다." }); } catch { setMsg({ ok: false, text: "복사 실패. 직접 선택해 복사하세요." }); } }}>복사</button></div>` : html`<p class="note">설정에서 여행 저장소를 연결하면 공유 링크가 생깁니다.</p>`}
    </section>
  </div>`;
}
