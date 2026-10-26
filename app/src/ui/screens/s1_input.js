// S1 입력(흐름 1, F-01~F-03). docs/04-wireframes.md S1
import { useState } from "../../lib.js";
import { html } from "../components/ui.js";
import { validateTrip, tripDays } from "../../state/store.js";
import { CAT_ICON } from "../../util/format.js";
import { airportLabel, airportSub, searchAirports } from "../../util/airports.js";

const BUDGET = [["low", "저가"], ["mid", "중가"], ["high", "고가"]];
const MEALS = [["light", "가볍게"], ["normal", "보통"], ["drink", "반주"], ["snack", "간식 포함"]];

// 공항 선택(D-029): 영문 도시명 기준 표기, 도시명·코드·공항명 검색, 선택 도시 근처 공항을 먼저 제안
function AirportPick({ label, value, time, airports, cities, cityIds, ro, onPick, onTime }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const sel = airports.find((a) => a.id === value);
  const hits = !ro && !sel && (open || q) ? searchAirports(airports, q, { cities, cityIds, limit: 6 }) : [];
  return html`<div class="airport">
    <div class="row"><span class="note" style="min-width:8.5em">${label}</span>
      ${sel ? html`<span class="chip on" onClick=${() => !ro && onPick(null)}>${airportLabel(sel)}${ro ? "" : " ×"}</span>`
        : value ? html`<span class="chip x" onClick=${() => !ro && onPick(null)}>${value} (목록에 없음)${ro ? "" : " ×"}</span>` : null}
      <input type="time" disabled=${ro} value=${time} onInput=${(e) => onTime(e.target.value)} /></div>
    ${!ro && !sel && html`<input placeholder="공항 검색 (도시 영문명, 코드, 공항 이름)" value=${q} onInput=${(e) => { setQ(e.target.value); setOpen(true); }} onFocus=${() => setOpen(true)} />`}
    ${hits.length > 0 && html`<div class="chips">${hits.map((a) => html`<button class="chip wide" onClick=${() => { onPick(a.id); setQ(""); setOpen(false); }}>${airportLabel(a)}<span class="note">${airportSub(a)}</span></button>`)}</div>`}
  </div>`;
}

export function S1Input({ trip, setTrip, cities, airports, categories, role, onDone }) {
  const [step, setStep] = useState(1);
  const [cityQ, setCityQ] = useState("");
  const [showErr, setShowErr] = useState(false);
  const err = validateTrip(trip);
  const ro = role !== "main";
  const upd = (patch) => !ro && setTrip({ ...trip, ...patch });
  const bigCities = cities.filter((c) => (c.pop || 0) >= 20000 || c.stratum === "guide");
  const q = cityQ.trim().toLowerCase();
  const norm = (v) => (v || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const nq = norm(q);
  // 정확히 일치하는 이름 → 인구 순. "Las Rozas de Madrid"가 "Madrid"보다 먼저 나오지 않게 한다
  const cityHits = nq ? bigCities.filter((c) => Object.values(c.n || {}).some((v) => typeof v === "string" && norm(v).includes(nq)))
    .sort((a, b) => (Object.values(b.n || {}).some((v) => norm(v) === nq) - Object.values(a.n || {}).some((v) => norm(v) === nq)) || ((b.pop || 0) - (a.pop || 0))).slice(0, 8) : [];
  const cityName = (c) => c.n?.ko || c.n?.es || c.n?.local;
  const steps = ["기본 정보", "여행 형태", "취향"];
  return html`<div class="section">
    <div class="steps">${steps.map((s, i) => html`<span class=${step === i + 1 ? "on" : ""}>${i + 1} ${s}</span>`)}</div>
    ${ro && html`<p class="note">열람 모드입니다. 수립자만 입력을 바꿀 수 있습니다.</p>`}
    ${step === 1 && html`
      <div class="field"><label>기간</label><div class="row"><input type="date" value=${trip.start} disabled=${ro} onInput=${(e) => upd({ start: e.target.value })} /> ~ <input type="date" value=${trip.end} disabled=${ro} onInput=${(e) => upd({ end: e.target.value })} />
        ${tripDays(trip) > 0 && html`<span class="note">${tripDays(trip)}일</span>`}</div>${showErr && err.period && html`<span class="error">${err.period}</span>`}</div>
      <div class="field"><label>여행 도시</label>
        <div class="chips">${trip.cities.map((id) => { const c = cities.find((x) => x.id === id); return html`<span class="chip on" onClick=${() => upd({ cities: trip.cities.filter((x) => x !== id) })}>${c ? cityName(c) : id} ×</span>`; })}</div>
        ${!ro && html`<input placeholder="도시 이름 검색 (예: 마드리드, Sevilla)" value=${cityQ} onInput=${(e) => setCityQ(e.target.value)} />`}
        ${cityHits.length > 0 && html`<div class="chips">${cityHits.map((c) => html`<button class="chip" onClick=${() => { if (!trip.cities.includes(c.id)) upd({ cities: [...trip.cities, c.id] }); setCityQ(""); }}>${cityName(c)}${c.n?.es && c.n.es !== cityName(c) ? ` (${c.n.es})` : ""} · ${(c.pop || 0).toLocaleString()}명</button>`)}</div>`}
        ${showErr && err.cities && html`<span class="error">${err.cities}</span>`}</div>
      <div class="field"><label>입국·출국 공항과 시각</label>
        <${AirportPick} label="입국(첫날 도착)" value=${trip.airportIn} time=${trip.timeIn} airports=${airports} cities=${cities} cityIds=${trip.cities} ro=${ro} onPick=${(id) => upd({ airportIn: id })} onTime=${(v) => upd({ timeIn: v })} />
        <${AirportPick} label="출국(마지막 날 출발)" value=${trip.airportOut} time=${trip.timeOut} airports=${airports} cities=${cities} cityIds=${trip.cities} ro=${ro} onPick=${(id) => upd({ airportOut: id })} onTime=${(v) => upd({ timeOut: v })} />
        <span class="note">영문 도시명 · 공항 영문명 (코드)로 표기하고 현지어 이름은 아래에 둡니다(D-029). 선택한 여행 도시 근처 공항을 먼저 보입니다.</span></div>
      <div class="field"><label>인원</label><input type="number" min="1" max="20" disabled=${ro} value=${trip.people} onInput=${(e) => upd({ people: Number(e.target.value) })} />${showErr && err.people && html`<span class="error">${err.people}</span>`}</div>
      <button class="btn" onClick=${() => { setShowErr(true); if (!err.period && !err.cities && !err.people) setStep(2); }}>다음 ▶</button>`}
    ${step === 2 && html`
      <div class="field"><label>예산 수준</label><div class="seg">${BUDGET.map(([k, v]) => html`<button class=${trip.budget === k ? "on" : ""} disabled=${ro} onClick=${() => upd({ budget: k })}>${v}</button>`)}</div></div>
      <div class="field"><label>하루 시작·마감</label><div class="row"><input type="time" disabled=${ro} value=${trip.dayStart} onInput=${(e) => upd({ dayStart: e.target.value })} /> ~ <input type="time" disabled=${ro} value=${trip.dayEnd} onInput=${(e) => upd({ dayEnd: e.target.value })} /></div>${err.day && html`<span class="error">${err.day}</span>`}<span class="note">마감은 일정 항목의 시작 시각에 적용됩니다(D-024).</span></div>
      <div class="field"><label>식사 형태 (복수 선택, 가안)</label><div class="chips">${MEALS.map(([k, v]) => html`<button class=${"chip " + (trip.meals.includes(k) ? "on" : "")} disabled=${ro} onClick=${() => upd({ meals: trip.meals.includes(k) ? trip.meals.filter((x) => x !== k) : [...trip.meals, k] })}>${v}</button>`)}</div></div>
      <div class="row"><button class="btn secondary" onClick=${() => setStep(1)}>◀ 이전</button><button class="btn" disabled=${!!err.day} onClick=${() => setStep(3)}>다음 ▶</button></div>`}
    ${step === 3 && html`
      <p class="note">관심 있는 범주를 고르세요. 선택하지 않으면 모든 범주를 같은 비중으로 봅니다(E2). 예시는 1등급 장소 중 대표성이 높은 곳입니다.</p>
      <div class="cats">${categories.map((c) => html`<button class=${"catcard " + (trip.tastes.includes(c.id) ? "on" : "")} disabled=${ro} onClick=${() => upd({ tastes: trip.tastes.includes(c.id) ? trip.tastes.filter((x) => x !== c.id) : [...trip.tastes, c.id] })}>
        <div class="name">${CAT_ICON[c.id] || ""} ${c.ko} <span class="note">${c.tier1.toLocaleString()}곳</span></div>
        <div class="ex">${(c.examples || []).map((e) => e.n).join(", ")}</div></button>`)}</div>
      <div class="row" style="margin-top:12px"><button class="btn secondary" onClick=${() => setStep(2)}>◀ 이전</button><button class="btn" onClick=${onDone}>선택 ${trip.tastes.length}개 · 탐색으로 ▶</button></div>`}
  </div>`;
}
