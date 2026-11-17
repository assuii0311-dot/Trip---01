// S4 선택·배치(흐름 4, F-10·F-11·F-14). docs/04-wireframes.md S4. 왼쪽 날짜, 오른쪽 장소(묶음 13). 끌어 놓기와 함께 "집고 날짜 누르기"를 대체 동작으로 둔다.
import { useState } from "../../lib.js";
import { html, Chip, Empty } from "../components/ui.js";
import { dateList, unassigned, lodgingCheck } from "../../state/plan.js";
import { placeName } from "../../data/places.js";
import { lodgingZones } from "../../engines/e2.js";
import { CAT_ICON } from "../../util/format.js";
import { inDest, makeDestOf, destName } from "../../data/dest.js";

export function S4Arrange({ plan, cities, byId, prof, nights, dayPlan = null, onMoveCity, onAssign, onMove, onSetLodging, onAddCustom, onOpenDetail, onGenerate, role = "local", dayCities = [], onAutoAssign, onAssignMany, onClearPicks, orphanCount = 0 }) {
  const canEdit = role === "main" || role === "local", canPropose = role === "sub"; // 역할에 없는 편집 요소는 숨기거나 잠근다(R-22)
  const dates = dateList(plan.trip);
  const un = unassigned(plan);
  const get = (id) => byId.get(id) || plan.custom[id];
  const [custom, setCustom] = useState({ name: "", lat: "", lon: "", city: plan.trip.cities[0] || "" });
  const [tab, setTab] = useState("place");
  // 배치(묶음 13): 왼쪽 날짜, 오른쪽 장소. 장소를 눌러 집은 뒤 날짜를 누르거나, 손잡이(⠿)를 끌어 날짜에 놓는다
  const dayCity = Object.fromEntries(dayCities.map((d) => [d.date, d.cityId]));
  const dayOf = (id) => Object.keys(plan.days).find((d) => plan.days[d].includes(id)) || "";
  const [held, setHeld] = useState([]);
  const [drag, setDrag] = useState(null); // {ids, x, y, over}
  const hold = (id) => setHeld((h) => (h.includes(id) ? h.filter((v) => v !== id) : [...h, id]));
  const drop = (ids, date) => { (onAssignMany || ((list, d) => list.forEach((id) => onAssign(id, d))))(ids, date); setHeld([]); };
  // 끌기는 포인터 이벤트로 직접 처리한다(아이패드 사파리의 기본 끌어 놓기는 길게 눌러야 하고 스크롤과 겹친다). 손잡이에는 touch-action: none을 준다
  const startDrag = (e, id) => {
    e.preventDefault(); e.stopPropagation();
    const ids = held.includes(id) && held.length > 1 && canEdit ? held : [id];
    // 알림 같은 겹친 요소가 날짜 위를 덮고 있어도 그 아래의 날짜를 찾는다
    const target = (ev) => { for (const el of document.elementsFromPoint(ev.clientX, ev.clientY)) { const t = el.closest && el.closest("[data-drop]"); if (t) return t.getAttribute("data-drop"); } return null; };
    const edge = (ev) => { for (const sel of [".arr-days", ".main"]) { const pane = document.querySelector(sel); if (!pane) continue; const r = pane.getBoundingClientRect(); if (ev.clientY < r.top + 48) pane.scrollTop -= 14; else if (ev.clientY > r.bottom - 48) pane.scrollTop += 14; } };
    const move = (ev) => { edge(ev); setDrag({ ids, x: ev.clientX, y: ev.clientY, over: target(ev) }); };
    const up = (ev) => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); window.removeEventListener("pointercancel", up); const t = ev.type === "pointerup" ? target(ev) : null; setDrag(null); if (t) drop(ids, t === "none" ? null : t); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up); window.addEventListener("pointercancel", up);
    setDrag({ ids, x: e.clientX, y: e.clientY, over: null });
  };
  const cityName = (id) => { const c = cities.find((x) => x.id === id); return c ? destName(c) : id; };
  const check = lodgingCheck(plan);
  const destOf = makeDestOf(cities, plan.trip.cities); // 섬을 골랐으면 그 섬의 지자체에 있는 장소를 섬으로 묶는다(D-030)
  const byCity = {};
  for (const id of plan.selection) { const p = get(id); if (p) (byCity[destOf(p) || p.city || "?"] ||= []).push(p); }
  return html`<div>
    <div class="toolbar"><div class="seg" style="flex:1"><button class=${tab === "place" ? "on" : ""} onClick=${() => setTab("place")}>장소 배치 (${plan.selection.length})</button><button class=${tab === "lodging" ? "on" : ""} onClick=${() => setTab("lodging")}>숙박 ${check.ok ? "✓" : "⚠"}</button></div></div>
    ${tab === "lodging" ? html`<div class="section">
      <p class="note">기간 ${dates.length}일, 숙박 ${check.total}박. 도시별 일수 합이 ${check.total}박이어야 합니다(현재 ${check.nights}박). 제안 일수는 여행지의 알려진 곳 수에 비례해 나눈 값입니다. 고른 장소가 그 일수(하루 ${prof.dayCapacity}곳)에 들어가지 않는 여행지만 늘리고, 그만큼은 여유가 있는 여행지에서 줄입니다(E2). 일정은 위에서부터 순서대로 날짜를 씁니다.</p>
      ${dayPlan && dayPlan.over && html`<p class="note warnline overnote">⚠ 고른 장소가 일정보다 많습니다. 하루 ${prof.dayCapacity}곳을 넘는 장소는 일정 생성에서 초과분으로 남습니다.</p>`}
      ${plan.trip.cities.length === 0 && html`<${Empty}>입력에서 여행 도시를 먼저 고르세요.</${Empty}>`}
      ${plan.trip.cities.map((cid) => { const c = cities.find((x) => x.id === cid); if (!c) return null; const l = plan.lodging[cid] || {}; const focus = plan.selection.map(get).filter((p) => p && inDest(p, c)); const z = lodgingZones(c, focus);
        return html`<div class="card" key=${cid}><div class="body"><div class="title">${plan.trip.cities.indexOf(cid) + 1}. ${cityName(cid)} <span class="note">제안 ${nights[cid] ?? 1}박${dayPlan ? ` · ${dayPlan.days[cid] ?? 0}일` : ""}</span>${canEdit && onMoveCity && plan.trip.cities.length > 1 ? html`<span class="citymove" style="float:right"><button type="button" class="minibtn moveup" aria-label="순서 앞으로" disabled=${plan.trip.cities.indexOf(cid) === 0} onClick=${() => onMoveCity(cid, -1)}>▲</button><button type="button" class="minibtn movedown" aria-label="순서 뒤로" disabled=${plan.trip.cities.indexOf(cid) === plan.trip.cities.length - 1} onClick=${() => onMoveCity(cid, 1)}>▼</button></span>` : ""}</div>
          <div class="row" style="margin:6px 0"><label class="note">숙박 일수</label><input type="number" min="0" max="30" style="width:80px;min-height:40px" disabled=${!canEdit} value=${l.nights ?? nights[cid] ?? 1} onInput=${(e) => onSetLodging(cid, { nights: Number(e.target.value) })} /></div>
          <div class="note">추천 구역(선택·추천 장소 중심 1.5km 안, 숙박 수 순)</div>
          <div class="chips" style="margin:6px 0">${z.zones.length ? z.zones.map((zz) => html`<button class=${"chip " + (l.zone === zz.id ? "on" : "")} disabled=${!canEdit} onClick=${() => onSetLodging(cid, { zone: zz.id, zoneName: zz.name, zoneLat: c.districts.find((d) => d.id === zz.id)?.lat, zoneLon: c.districts.find((d) => d.id === zz.id)?.lon })} title=${zz.reason}>${zz.name || zz.id} · ${zz.lodging}</button>`) : html`<span class="note">${z.fallback?.reason}</span>`}</div>
          ${l.zoneName && html`<div class="note">선택 구역: ${l.zoneName}. 예약 정보(R-19)는 묶음 5 일정표에서 입력합니다.</div>`}
        </div></div>`; })}
    </div>` : html`
      <div class="arr">
        <div class="arr-days" aria-label="날짜">
          <div class=${"daybox none " + (drag && drag.over === "none" ? "over" : "")} data-drop="none" onClick=${() => held.length && drop(held, null)}>
            <div class="dayhead"><b>미배치</b> <span class="cnt">${un.length}곳</span></div>
            ${held.length > 0 && html`<div class="dropnote">누르면 집은 ${held.length}곳을 미배치로 돌립니다</div>`}</div>
          ${dates.length === 0 ? html`<p class="note" style="padding:8px 12px">입력에서 기간을 정하면 날짜가 생깁니다.</p>` : dates.map((d, i) => { const ids = plan.days[d] || []; const cid = dayCity[d];
            return html`<div class=${"daybox " + (drag && drag.over === d ? "over" : "")} key=${d} data-drop=${d} onClick=${() => held.length && drop(held, d)}>
              <div class="dayhead"><b>${i + 1}일</b> ${d.slice(5).replace("-", "/")} <span class="note">${cid ? cityName(cid) : ""}</span><span class="cnt">${ids.length}곳</span></div>
              ${ids.map((id, j) => { const p = get(id); return p && html`<div class="mini" key=${id}>
                ${(canEdit || canPropose) && html`<button type="button" class="grip" aria-label="끌어서 다른 날짜에 놓기" onPointerDown=${(e) => startDrag(e, id)} onClick=${(e) => e.stopPropagation()}>⠿</button>`}
                <span class="nm" onClick=${(e) => { e.stopPropagation(); onOpenDetail(id); }}>${CAT_ICON[p.cat[0]] || "📍"} ${placeName(p)}</span>
                ${canEdit && html`<button type="button" class="minibtn" aria-label="위로" disabled=${j === 0} onClick=${(e) => { e.stopPropagation(); onMove(d, j, j - 1); }}>▲</button><button type="button" class="minibtn" aria-label="아래로" disabled=${j === ids.length - 1} onClick=${(e) => { e.stopPropagation(); onMove(d, j, j + 1); }}>▼</button>`}
                ${(canEdit || canPropose) && html`<button type="button" class="minibtn" aria-label="미배치로" onClick=${(e) => { e.stopPropagation(); drop([id], null); }}>✕</button>`}</div>`; })}
              ${held.length > 0 && html`<div class="dropnote">누르면 집은 ${held.length}곳을 이 날에 넣습니다</div>`}</div>`; })}
        </div>
        <div class="arr-places">
          <p class="note" style="padding:8px 12px 0">${canEdit ? "장소를 눌러 집고 날짜를 누르면 그 날에 들어갑니다. ⠿을 끌어다 날짜에 놓아도 됩니다. 비워 두면 일정 생성이 자동으로 배치합니다." : canPropose ? "서브 수립자: 장소 하나를 집어 날짜를 누르면 제안으로 보내집니다." : "공유자는 열람만 할 수 있습니다."}</p>
          ${plan.selection.length === 0 && html`<${Empty}>탐색에서 장소를 선택하면 여기에 나타납니다.</${Empty}>`}
          ${orphanCount > 0 && canEdit && html`<div class="picks" style="margin:8px 12px">선택한 여행지에 속하지 않는 장소가 ${orphanCount}곳 있습니다. <button type="button" class="linkbtn clearorphan" onClick=${() => onClearPicks && onClearPicks("orphan")}>지우기</button></div>`}
          ${Object.entries(byCity).map(([cid, ps]) => { const isDest = plan.trip.cities.includes(cid); const free = ps.filter((p) => !dayOf(p.id)).length;
            return html`<div class="arr-city" key=${cid}>
              <div class="arr-cityhead"><h2>${cityName(cid)} <span class="note">${ps.length}곳 · 미배치 ${free}</span></h2>
                ${canEdit && html`<div class="row">${isDest && html`<button type="button" class="btn secondary sm autoassign" onClick=${() => onAutoAssign && onAutoAssign(cid)}>자동 배정</button>`}<button type="button" class="btn secondary sm" disabled=${free === ps.length} onClick=${() => onAssignMany && onAssignMany(ps.map((p) => p.id), null)}>배정 풀기</button></div>`}</div>
              <div class="minilist">${ps.map((p) => { const d = dayOf(p.id); return html`<div class=${"mini place" + (held.includes(p.id) ? " held" : "")} key=${p.id} onClick=${() => (canEdit || canPropose) && hold(p.id)}>
                ${(canEdit || canPropose) && html`<button type="button" class="grip" aria-label="끌어서 날짜에 놓기" onPointerDown=${(e) => startDrag(e, p.id)} onClick=${(e) => e.stopPropagation()}>⠿</button>`}
                <span class="nm">${CAT_ICON[p.cat[0]] || "📍"} ${placeName(p)}${p.cv === "user" ? " · 직접 추가" : ""}${plan.reservations[p.id] ? " 🎫" : ""}</span>
                <span class=${"daytag " + (d ? "on" : "")}>${d ? `${dates.indexOf(d) + 1}일` : "미배치"}</span>
                <button type="button" class="minibtn" aria-label="상세" onClick=${(e) => { e.stopPropagation(); onOpenDetail(p.id); }}>ⓘ</button></div>`; })}</div></div>`; })}
          ${canEdit && html`<div class="section"><h2>직접 추가</h2>
        <div class="row"><input placeholder="이름" value=${custom.name} onInput=${(e) => setCustom({ ...custom, name: e.target.value })} style="flex:2;min-width:120px;min-height:40px;padding:6px 10px;border:1px solid var(--line);border-radius:8px" />
          <input placeholder="위도" value=${custom.lat} onInput=${(e) => setCustom({ ...custom, lat: e.target.value })} style="width:100px;min-height:40px;padding:6px 10px;border:1px solid var(--line);border-radius:8px" />
          <input placeholder="경도" value=${custom.lon} onInput=${(e) => setCustom({ ...custom, lon: e.target.value })} style="width:100px;min-height:40px;padding:6px 10px;border:1px solid var(--line);border-radius:8px" />
          <select value=${custom.city} onChange=${(e) => setCustom({ ...custom, city: e.target.value })} style="min-height:40px">${plan.trip.cities.map((cid) => html`<option value=${cid}>${cityName(cid)}</option>`)}</select>
          <button class="btn secondary" disabled=${!custom.name || isNaN(parseFloat(custom.lat)) || isNaN(parseFloat(custom.lon))} onClick=${() => { onAddCustom({ name: custom.name.trim(), lat: parseFloat(custom.lat), lon: parseFloat(custom.lon), cityId: custom.city || null }); setCustom({ ...custom, name: "", lat: "", lon: "" }); }}>+ 추가</button></div>
        <p class="note">좌표는 구글맵에서 길게 눌러 복사할 수 있습니다.</p></div>`}
        </div>
      </div>
      ${canEdit && html`<div class="stepnav"><button type="button" class="btn secondary clearall" disabled=${plan.selection.length === 0} onClick=${() => onClearPicks && onClearPicks("all")}>고른 장소 모두 지우기</button><button type="button" class="btn" disabled=${plan.selection.length === 0} onClick=${onGenerate}>일정 생성 ▶</button></div>`}
      ${drag && html`<div class="dragghost" style=${`left:${drag.x}px;top:${drag.y}px`}>${drag.ids.length > 1 ? `${drag.ids.length}곳` : placeName(get(drag.ids[0]) || {})}</div>`}`}
  </div>`;
}
