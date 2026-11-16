// S1 입력(흐름 1, F-01~F-03). docs/04-wireframes.md S1. 단계: 기본 정보 → 취향·여행지(나라 아래 도시·섬 카드, D-030. 고른 취향에 맞는 곳을 추천, D-039) → 공항·여행 형태
import { useState } from "../../lib.js";
import { inputFilterCount, clearedInput } from "../../state/nav.js";
import { html } from "../components/ui.js";
import { validateTrip, tripDays } from "../../state/store.js";
import { CAT_ICON } from "../../util/format.js";
import { airportLabel, airportSub, searchAirports } from "../../util/airports.js";
import { destinationList, filterDestinations, searchOthers, nearestAirport, regionOptions, fmtPop, tasteMatch, sortByTaste } from "../../util/destinations.js";
import { destName, isIsland } from "../../data/dest.js";

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

const COUNTRY = "스페인"; // 요구사항 3절: 1차 스페인. 나라 선택은 나라가 늘면 연다

// 여행지 카드(D-030): 요약 정보로 고르게 한다. 등급은 참고 표시
function DestCard({ c, selected, ro, tastes, catName, airports, cities, onToggle, ko = {} }) {
  const matched = tasteMatch(c, tastes).matched; // 고른 취향이 이 여행지의 중심 범주면 추천(D-039)
  const lines = ko.lines || {}, koNames = ko.names || {};
  const ap = nearestAirport(c, airports);
  const region = c._regionName;
  const meta = [region, fmtPop(c.pop), ap ? `✈ ${ap.iata} ${ap.km}km` : null, c.places?.tier1 ? `1등급 장소 ${c.places.tier1.toLocaleString()}곳` : null].filter(Boolean).join(" · ");
  const towns = isIsland(c) ? c.members.slice(0, 4).map((id) => destName(cities.find((x) => x.id === id))).filter(Boolean) : [];
  return html`<div class=${"card dest " + (selected ? "sel" : "")} data-id=${c.id}>
    <div class="body">
      <div class="title">${destName(c)} <span class="note">${c.n?.en && c.n.en !== destName(c) ? c.n.en : c.n?.es && c.n.es !== destName(c) ? c.n.es : ""}${c.n?.ko_src === "generated" ? " · 한글 표기 생성" : ""}</span></div>
      <div class="chips meta">
        ${matched.length > 0 && html`<span class="chip ok rec" title="고른 취향이 중심인 여행지">★ 추천</span>`}
        ${isIsland(c) && html`<span class="chip user">🏝 섬</span>`}
        ${(c.focus || []).map((f, i) => html`<span class=${"chip " + (tastes.includes(f) ? "on" : "user")}>${CAT_ICON[f] || ""} ${catName(f)}${i === 0 ? " 중심" : ""}</span>`)}
        ${c.dest ? html`<span class="chip est" title="인기 참고 등급(E1 4절 15항)">참고 ${c.dest.tier}등급</span>` : c.island ? html`<span class="chip x">${destName(cities.find((x) => x.id === c.island)) || "섬"}에 포함</span>` : html`<span class="chip x">목록 밖</span>`}
        ${c.dest?.unesco > 0 && html`<span class="chip star">유네스코 ${c.dest.unesco}</span>`}
      </div>
      ${(c.hl || []).length > 0 && html`<ul class="hl" aria-label="대표 명소">${c.hl.map((h) => html`<li><b>${h.n.ko || koNames[h.id] || h.n.en || h.n.local}</b>${lines[h.id] ? html` <span class="line">${lines[h.id]}</span>` : ""}</li>`)}</ul>`}
      ${towns.length > 0 && html`<div class="sub">주요 도시: ${towns.join(" · ")}${c.members.length > towns.length ? ` 외 ${c.members.length - towns.length}곳` : ""}</div>`}
      ${meta && html`<div class="note">${meta}</div>`}
      ${c.ko?.summary ? html`<p class="lead ko">${c.ko.summary}</p>` : c.wv?.lead && html`<p class="lead">${c.wv.lead}</p>`}
    </div>
    <button class="btn secondary pick" disabled=${ro} aria-label=${selected ? "선택 해제" : "선택"} aria-pressed=${selected} onClick=${() => onToggle(c.id)}>${selected ? "✓" : "+"}</button>
  </div>`;
}

export function S1Input({ trip, setTrip, cities, airports, categories, regions = [], role, onDone, ui, setUi, ko = {}, onRemoveDest }) {
  // 단계와 여행지 목록의 검색어·필터는 App이 든다(다른 화면에 다녀와도 남는다, D-036). ui가 없으면 화면 안에서만 기억한다
  const [local, setLocal] = useState({ step: 1, q: "", kind: "all", rec: false, region: "" });
  const view = ui || local, patch = setUi || ((p) => setLocal((s) => ({ ...s, ...p })));
  const { step, q, kind, rec, region } = view;
  const setStep = (s) => patch({ step: s }), setQ = (v) => patch({ q: v }), setKind = (v) => patch({ kind: v }), setRec = (v) => patch({ rec: v }), setRegion = (v) => patch({ region: v });
  const [showErr, setShowErr] = useState(false);
  const err = validateTrip(trip);
  // 단계 표시를 눌러 이동한다. 앞 단계는 언제나, 뒤 단계는 앞 단계의 필수 입력이 채워졌을 때만
  const blockedAt = (s) => (s >= 2 && (err.period || err.people) ? 1 : s >= 3 && err.cities ? 2 : 0);
  const jump = (s) => { const b = blockedAt(s); if (b) { setShowErr(true); setStep(b); } else { setShowErr(false); setStep(s); } };
  const nFilters = inputFilterCount(view);
  const ro = role !== "main";
  const upd = (patch) => !ro && setTrip({ ...trip, ...patch });
  const catName = (id) => (categories.find((c) => c.id === id) || {}).ko || id;
  const regionName = (c) => { const r = regions.find((x) => x.id === c.region?.community); return r ? r.n?.local || r.n?.es : isIsland(c) ? "섬" : ""; };
  const list = destinationList(cities).map((c) => ({ ...c, _regionName: regionName(c) }));
  const tastes = trip.tastes || [];
  const onlyRec = rec && tastes.length > 0; // "추천만 보기": 고른 취향이 중심인 여행지만
  const shown = sortByTaste(filterDestinations(list, { q, kind, focus: onlyRec ? tastes : [], region }), tastes);
  const nRec = tastes.length ? shown.filter((c) => tasteMatch(c, tastes).matched.length > 0).length : 0;
  const toggleTaste = (id) => upd({ tastes: tastes.includes(id) ? tastes.filter((x) => x !== id) : [...tastes, id] });
  const others = q.trim() ? searchOthers(cities, q).map((c) => ({ ...c, _regionName: regionName(c) })) : [];
  const regionOpts = regionOptions(list, regions);
  // 여행지를 뺄 때는 그 여행지에서 고른 장소도 함께 정리해야 하므로 앱 쪽 처리(onRemoveDest)에 맡긴다(묶음 13)
  const toggleCity = (id) => (trip.cities.includes(id) ? (onRemoveDest ? onRemoveDest(id) : upd({ cities: trip.cities.filter((x) => x !== id) })) : upd({ cities: [...trip.cities, id] }));
  const nIsland = list.filter(isIsland).length;
  const steps = ["기본 정보", "취향·여행지", "공항·여행 형태"];
  return html`<div class="section">
    <div class="steps" role="tablist" aria-label="입력 단계">${steps.map((s, i) => html`<button type="button" role="tab" aria-selected=${step === i + 1} class=${step === i + 1 ? "on" : ""} onClick=${() => jump(i + 1)}>${i + 1} ${s}</button>`)}</div>
    ${ro && html`<p class="note">열람 모드입니다. 수립자만 입력을 바꿀 수 있습니다.</p>`}
    ${step === 1 && html`
      <div class="field"><label>나라</label><div class="row"><span class="chip on">${COUNTRY}</span><span class="note">지금은 스페인만 준비되어 있습니다. 다음 단계에서 스페인의 여행지(도시·섬)를 보고 고릅니다.</span></div></div>
      <div class="field"><label>기간</label><div class="row"><input type="date" value=${trip.start} disabled=${ro} onInput=${(e) => upd({ start: e.target.value })} /> ~ <input type="date" value=${trip.end} disabled=${ro} onInput=${(e) => upd({ end: e.target.value })} />
        ${tripDays(trip) > 0 && html`<span class="note">${tripDays(trip)}일</span>`}</div>${showErr && err.period && html`<span class="error">${err.period}</span>`}</div>
      <div class="field"><label>인원</label><input type="number" min="1" max="20" disabled=${ro} value=${trip.people} onInput=${(e) => upd({ people: Number(e.target.value) })} />${showErr && err.people && html`<span class="error">${err.people}</span>`}</div>
      <button class="btn" onClick=${() => { setShowErr(true); if (!err.period && !err.people) { setShowErr(false); setStep(2); } }}>다음 ▶</button>`}
    ${step === 2 && html`
      <div class="field"><label>내 취향 (여러 개 고를 수 있습니다)</label>
        <div class="chips tastes">${categories.map((c) => html`<button type="button" class=${"chip taste " + (tastes.includes(c.id) ? "on" : "")} disabled=${ro} aria-pressed=${tastes.includes(c.id)} onClick=${() => toggleTaste(c.id)}>${CAT_ICON[c.id] || ""} ${c.ko}</button>`)}</div>
        <span class="note">고른 취향이 중심인 여행지에 "추천"이 붙고 위로 올라옵니다. 고르지 않으면 인기 순으로 보입니다. 취향은 장소 추천에도 쓰입니다(E2).</span>
        <details class="tastehelp"><summary>범주 설명 보기</summary>${categories.map((c) => html`<div class="note"><b>${CAT_ICON[c.id] || ""} ${c.ko}</b> ${c.desc ? `${c.desc} · ` : ""}예: ${(c.examples || []).map((e) => e.n).join(", ")}</div>`)}</details></div>
      <p class="note">${COUNTRY}의 여행지 ${list.length}곳(도시 ${list.length - nIsland}, 섬 ${nIsland})입니다. 소개와 대표 명소를 보고 가고 싶은 곳을 고르세요. 등급은 인기를 나타내는 참고값입니다.</p>
      <div class="field"><label>선택한 여행지 ${trip.cities.length}곳</label>
        <div class="chips picked">${trip.cities.length === 0 ? html`<span class="note">아직 없습니다. 아래 카드의 + 를 누르세요.</span>` : trip.cities.map((id) => { const c = cities.find((x) => x.id === id); return html`<span class="chip on" onClick=${() => toggleCity(id)}>${c ? destName(c) : id}${ro ? "" : " ×"}</span>`; })}</div>
        ${showErr && err.cities && html`<span class="error">${err.cities}</span>`}</div>
      <div class="field"><input placeholder="여행지 검색 (도시·섬 이름, 대표 명소)" value=${q} onInput=${(e) => setQ(e.target.value)} />
        <div class="destfilter"><div class="seg">${[["all", "전체"], ["city", "도시"], ["island", "섬"]].map(([k, v]) => html`<button class=${kind === k ? "on" : ""} onClick=${() => setKind(k)}>${v}</button>`)}</div>
          <select aria-label="지역" value=${region} onChange=${(e) => setRegion(e.target.value)}><option value="">전체 지역</option>${regionOpts.map((r) => html`<option value=${r.id}>${r.name} (${r.n})</option>`)}</select></div>
        ${tastes.length > 0 && html`<div class="chips"><button type="button" class=${"chip reconly " + (onlyRec ? "on" : "")} aria-pressed=${onlyRec} onClick=${() => setRec(!rec)}>★ 추천만 보기</button></div>`}</div>
      <p class="note">표시 ${shown.length}곳${tastes.length ? ` · 추천 ${nRec}곳` : ""}${nFilters > 0 && html` · <button type="button" class="linkbtn" onClick=${() => patch(clearedInput())}>필터 지우기</button>`}</p>
      <div class="destlist">
        ${shown.map((c) => html`<${DestCard} key=${c.id} c=${c} selected=${trip.cities.includes(c.id)} ro=${ro} tastes=${tastes} catName=${catName} airports=${airports} cities=${cities} onToggle=${toggleCity} ko=${ko} />`)}
        ${shown.length === 0 && others.length === 0 && html`<div class="empty">조건에 맞는 여행지가 없습니다.</div>`}
        ${others.length > 0 && html`<h2 style="margin:12px 0 8px">목록 밖 지자체</h2><p class="note">여행지 목록에는 없지만 이름으로 찾은 곳입니다. 섬에 속한 곳은 섬 여행지에 포함되어 있고, 그 밖의 곳은 데이터가 적을 수 있습니다.</p>
          ${others.map((c) => html`<${DestCard} key=${c.id} c=${c} selected=${trip.cities.includes(c.id)} ro=${ro} tastes=${tastes} catName=${catName} airports=${airports} cities=${cities} onToggle=${toggleCity} ko=${ko} />`)}`}
        <div class="src">소개: Wikivoyage 영문 가이드(CC BY-SA 4.0)를 바탕으로 만든 한국어 요약입니다(생성본, E5). 요약이 없는 곳은 영문 원문을 보입니다. 취향 표시와 참고 등급은 데이터로 계산한 값입니다(추정, E1 4절 15·16항).</div>
      </div>
      <div class="stepnav"><button class="btn secondary" onClick=${() => setStep(1)}>◀ 이전</button><button class="btn" onClick=${() => { setShowErr(true); if (!err.cities) { setShowErr(false); setStep(3); } }}>선택 ${trip.cities.length}곳 · 다음 ▶</button></div>`}
    ${step === 3 && html`
      <div class="field"><label>입국·출국 공항과 시각</label>
        <${AirportPick} label="입국(첫날 도착)" value=${trip.airportIn} time=${trip.timeIn} airports=${airports} cities=${cities} cityIds=${trip.cities} ro=${ro} onPick=${(id) => upd({ airportIn: id })} onTime=${(v) => upd({ timeIn: v })} />
        <${AirportPick} label="출국(마지막 날 출발)" value=${trip.airportOut} time=${trip.timeOut} airports=${airports} cities=${cities} cityIds=${trip.cities} ro=${ro} onPick=${(id) => upd({ airportOut: id })} onTime=${(v) => upd({ timeOut: v })} />
        <span class="note">영문 도시명 · 공항 영문명 (코드)로 표기하고 현지어 이름은 아래에 둡니다(D-029). 선택한 여행지 근처 공항을 먼저 보입니다.</span></div>
      <div class="field"><label>예산 수준</label><div class="seg">${BUDGET.map(([k, v]) => html`<button class=${trip.budget === k ? "on" : ""} disabled=${ro} onClick=${() => upd({ budget: k })}>${v}</button>`)}</div></div>
      <div class="field"><label>하루 시작·마감</label><div class="row"><input type="time" disabled=${ro} value=${trip.dayStart} onInput=${(e) => upd({ dayStart: e.target.value })} /> ~ <input type="time" disabled=${ro} value=${trip.dayEnd} onInput=${(e) => upd({ dayEnd: e.target.value })} /></div>${err.day && html`<span class="error">${err.day}</span>`}<span class="note">마감은 일정 항목의 시작 시각에 적용됩니다(D-024).</span></div>
      <div class="field"><label>식사 형태 (복수 선택, 가안)</label><div class="chips">${MEALS.map(([k, v]) => html`<button class=${"chip " + (trip.meals.includes(k) ? "on" : "")} disabled=${ro} onClick=${() => upd({ meals: trip.meals.includes(k) ? trip.meals.filter((x) => x !== k) : [...trip.meals, k] })}>${v}</button>`)}</div></div>
      <div class="row"><button class="btn secondary" onClick=${() => setStep(2)}>◀ 이전</button><button class="btn" disabled=${!!err.day} onClick=${onDone}>장소 고르러 가기 ▶</button></div>`}
  </div>`;
}
