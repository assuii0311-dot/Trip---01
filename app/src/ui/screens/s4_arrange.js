// S4 선택·배치(흐름 4, F-10·F-11·F-14). docs/04-wireframes.md S4. 끌어 놓기 대신 날짜 선택 메뉴(접근성 대체 동작)를 기본으로 둔다.
import { useState } from "../../lib.js";
import { html, Chip, Empty } from "../components/ui.js";
import { dateList, unassigned, lodgingCheck } from "../../state/plan.js";
import { placeName } from "../../data/places.js";
import { lodgingZones } from "../../engines/e2.js";
import { CAT_ICON } from "../../util/format.js";

export function S4Arrange({ plan, cities, byId, prof, nights, onAssign, onMove, onSetLodging, onAddCustom, onOpenDetail, onGenerate }) {
  const dates = dateList(plan.trip);
  const un = unassigned(plan);
  const get = (id) => byId.get(id) || plan.custom[id];
  const [custom, setCustom] = useState({ name: "", lat: "", lon: "", city: plan.trip.cities[0] || "" });
  const [tab, setTab] = useState("place");
  const cityName = (id) => { const c = cities.find((x) => x.id === id); return c ? c.n.ko || c.n.es : id; };
  const check = lodgingCheck(plan);
  const byCity = {};
  for (const id of plan.selection) { const p = get(id); if (p) (byCity[p.city || "?"] ||= []).push(p); }
  return html`<div>
    <div class="toolbar"><div class="seg" style="flex:1"><button class=${tab === "place" ? "on" : ""} onClick=${() => setTab("place")}>장소 배치 (${plan.selection.length})</button><button class=${tab === "lodging" ? "on" : ""} onClick=${() => setTab("lodging")}>숙박 ${check.ok ? "✓" : "⚠"}</button></div></div>
    ${tab === "lodging" ? html`<div class="section">
      <p class="note">기간 ${dates.length}일, 숙박 ${check.total}박. 도시별 일수 합이 ${check.total}박이어야 합니다(현재 ${check.nights}박). 제안 일수는 추천 장소 수 ÷ 하루 ${prof.dayCapacity}곳(E2).</p>
      ${plan.trip.cities.length === 0 && html`<${Empty}>입력에서 여행 도시를 먼저 고르세요.</${Empty}>`}
      ${plan.trip.cities.map((cid) => { const c = cities.find((x) => x.id === cid); if (!c) return null; const l = plan.lodging[cid] || {}; const focus = plan.selection.map(get).filter((p) => p && p.city === cid); const z = lodgingZones(c, focus);
        return html`<div class="card" key=${cid}><div class="body"><div class="title">${cityName(cid)} <span class="note">제안 ${nights[cid] || 1}박</span></div>
          <div class="row" style="margin:6px 0"><label class="note">숙박 일수</label><input type="number" min="0" max="30" style="width:80px;min-height:40px" value=${l.nights ?? nights[cid] ?? 1} onInput=${(e) => onSetLodging(cid, { nights: Number(e.target.value) })} /></div>
          <div class="note">추천 구역(선택·추천 장소 중심 1.5km 안, 숙박 수 순)</div>
          <div class="chips" style="margin:6px 0">${z.zones.length ? z.zones.map((zz) => html`<button class=${"chip " + (l.zone === zz.id ? "on" : "")} onClick=${() => onSetLodging(cid, { zone: zz.id, zoneName: zz.name, zoneLat: c.districts.find((d) => d.id === zz.id)?.lat, zoneLon: c.districts.find((d) => d.id === zz.id)?.lon })} title=${zz.reason}>${zz.name || zz.id} · ${zz.lodging}</button>`) : html`<span class="note">${z.fallback?.reason}</span>`}</div>
          ${l.zoneName && html`<div class="note">선택 구역: ${l.zoneName}. 예약 정보(R-19)는 묶음 5 일정표에서 입력합니다.</div>`}
        </div></div>`; })}
    </div>` : html`
      <div class="section" style="padding-bottom:0"><p class="note">장소마다 날짜를 고르면 그 날 끝에 들어갑니다. 비워 두면 일정 생성(묶음 5)이 자동으로 배치합니다. 미배치 ${un.length}곳.</p></div>
      ${plan.selection.length === 0 && html`<${Empty}>탐색에서 장소를 선택하면 여기에 나타납니다.</${Empty}>`}
      ${Object.entries(byCity).map(([cid, ps]) => html`<div class="section" style="padding-top:8px"><h2>${cityName(cid)} <span class="note">${ps.length}곳</span></h2>
        ${ps.map((p) => { const date = Object.keys(plan.days).find((d) => plan.days[d].includes(p.id)) || ""; return html`<div class="card" key=${p.id} style="margin:0 0 8px">
          <div class="ico">${CAT_ICON[p.cat[0]] || "📍"}</div>
          <div class="body"><div class="title" onClick=${() => onOpenDetail(p.id)}>${placeName(p)}</div>
            <div class="meta chips">${p.cv === "user" && html`<${Chip} kind="user">사용자 추가</${Chip}>`}${plan.reservations[p.id] && html`<${Chip} kind="warn">🎫 ${{ required: "예약 필요", recommended: "예약 권장", none: "불필요" }[plan.reservations[p.id]]}</${Chip}>`}</div></div>
          <select aria-label="날짜" value=${date} onChange=${(e) => onAssign(p.id, e.target.value || null)} style="min-height:40px"><option value="">미배치</option>${dates.map((d, i) => html`<option value=${d}>${i + 1}일 ${d.slice(5)}</option>`)}</select></div>`; })}</div>`)}
      <div class="section"><h2>날짜별</h2>
        ${dates.length === 0 ? html`<p class="note">입력에서 기간을 정하면 날짜가 생깁니다.</p>` : dates.map((d, i) => html`<div class="card" key=${d} style="margin:0 0 8px"><div class="body"><div class="title">${i + 1}일 ${d}</div>
          ${(plan.days[d] || []).length === 0 ? html`<div class="note">비어 있음</div>` : (plan.days[d] || []).map((id, j) => { const p = get(id); return p && html`<div class="row" style="padding:4px 0;border-bottom:1px solid var(--line)"><span style="flex:1">${j + 1}. ${placeName(p)}</span><button class="btn secondary" style="min-height:36px;padding:2px 8px" aria-label="위로" disabled=${j === 0} onClick=${() => onMove(d, j, j - 1)}>▲</button><button class="btn secondary" style="min-height:36px;padding:2px 8px" aria-label="아래로" disabled=${j === plan.days[d].length - 1} onClick=${() => onMove(d, j, j + 1)}>▼</button></div>`; })}
        </div></div>`)}
      </div>
      <div class="section"><h2>직접 추가</h2>
        <div class="row"><input placeholder="이름" value=${custom.name} onInput=${(e) => setCustom({ ...custom, name: e.target.value })} style="flex:2;min-width:120px;min-height:40px;padding:6px 10px;border:1px solid var(--line);border-radius:8px" />
          <input placeholder="위도" value=${custom.lat} onInput=${(e) => setCustom({ ...custom, lat: e.target.value })} style="width:100px;min-height:40px;padding:6px 10px;border:1px solid var(--line);border-radius:8px" />
          <input placeholder="경도" value=${custom.lon} onInput=${(e) => setCustom({ ...custom, lon: e.target.value })} style="width:100px;min-height:40px;padding:6px 10px;border:1px solid var(--line);border-radius:8px" />
          <select value=${custom.city} onChange=${(e) => setCustom({ ...custom, city: e.target.value })} style="min-height:40px">${plan.trip.cities.map((cid) => html`<option value=${cid}>${cityName(cid)}</option>`)}</select>
          <button class="btn secondary" disabled=${!custom.name || isNaN(parseFloat(custom.lat)) || isNaN(parseFloat(custom.lon))} onClick=${() => { onAddCustom({ name: custom.name.trim(), lat: parseFloat(custom.lat), lon: parseFloat(custom.lon), cityId: custom.city || null }); setCustom({ ...custom, name: "", lat: "", lon: "" }); }}>+ 추가</button></div>
        <p class="note">좌표는 구글맵에서 길게 눌러 복사할 수 있습니다. 지도에서 찍기는 묶음 5에서.</p></div>
      <div class="section"><button class="btn" disabled=${plan.selection.length === 0} onClick=${onGenerate}>일정 생성 ▶ <span class="note" style="color:#fff">(묶음 5)</span></button></div>`}
  </div>`;
}
