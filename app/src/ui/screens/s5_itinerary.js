// S5 일정표(흐름 5·6, F-15·F-17·F-18·F-20). docs/04-wireframes.md S5
import { useMemo, useState } from "../../lib.js";
import { html, Chip, Empty } from "../components/ui.js";
import { placeName } from "../../data/places.js";
import { toHHMM, toMin, dwellOf } from "../../engines/e4.js";
import { modeKo } from "../../engines/e3.js";
import { CAT_ICON, fmtDistance } from "../../util/format.js";

const FLAG = { no_hours: "영업시간 확인 필요(정보 없음)", closed_or_short: "영업시간 확인 필요(참고값과 불일치)" };

export function S5Itinerary({ plan, result, getPlace, cities, onGenerate, onRegenerateDay, onSetDwell, onSetFixed, onToggleLock, onOpenDetail, onMoveToDay, onCost, busy }) {
  const [di, setDi] = useState(0);
  const [showOverflow, setShowOverflow] = useState(false);
  const days = result?.days || [];
  const day = days[di];
  const cityName = (id) => { const c = cities.find((x) => x.id === id); return c ? c.n.ko || c.n.es : id; };
  if (!result) return html`<div class="section"><${Empty}>선택한 장소 ${plan.selection.length}곳으로 일정을 만듭니다. 숙박 일수가 기간과 맞아야 합니다.</${Empty}><div class="row" style="justify-content:center"><button class="btn" disabled=${busy || plan.selection.length === 0} onClick=${onGenerate}>${busy ? "생성 중…" : "일정 생성 ▶"}</button></div></div>`;
  return html`<div>
    <div class="toolbar">${days.map((d, i) => html`<button class=${"chip " + (i === di ? "on" : "")} onClick=${() => setDi(i)}>${i + 1}일 ${d.date.slice(5)}${d.intercity ? " 🚆" : ""}</button>`)}</div>
    ${day && html`<div class="section" style="padding-top:4px">
      <p class="note">${cityName(day.cityId)} · 장소 ${day.summary.places}곳 · 이동 ${day.summary.travelMin}분(${Math.round(day.summary.travelShare * 100)}%${day.summary.warn ? " ⚠ 40% 초과" : ""}) · 도보 ${fmtDistance(day.summary.walkM)} · ${toHHMM(day.summary.start)}~${toHHMM(day.summary.end)}</p>
      ${day.intercity && html`<div class="card" style="margin:0 0 8px"><div class="ico">🚆</div><div class="body"><div class="title">${cityName(day.intercity.from)} → ${cityName(day.intercity.to)}</div><div class="chips meta">${day.intercity.leg.options.map((o) => html`<${Chip} kind=${o === day.intercity.leg.best ? "ok" : "est"}>${modeKo(o.mode)} ${o.min >= 60 ? `${Math.floor(o.min / 60)}시간 ${o.min % 60}분` : `${o.min}분`}${o.perDay ? ` · 하루 ${o.perDay}회` : ""}${o.confidence === "estimate" ? " (추정)" : ""}</${Chip}>`)}</div>${day.intercity.leg.best.link && html`<a class="note" href=${day.intercity.leg.best.link} target="_blank" rel="noopener">구글맵 경로 ↗</a>`}</div></div>`}
      ${day.items.length === 0 && html`<p class="note">이 날에 배치된 장소가 없습니다.</p>`}
      ${day.items.map((it, k) => it.kind === "meal" ? html`<div class="row" style="padding:6px 0;color:var(--muted)">🍽 ${toHHMM(it.start)}–${toHHMM(it.end)} ${{ lunch: "점심", dinner: "저녁", snack: "간식" }[it.meal]} (슬롯)</div>` : (() => {
        const p = getPlace(it.id); if (!p) return null; const tr = it.travel;
        return html`<div key=${it.id}>
          ${tr && tr.min > 0 && html`<div class="row" style="padding:4px 0 4px 32px;color:var(--muted);font-size:14px">${{ walk: "🚶", transit: "🚇", taxi: "🚕", car: "🚗" }[tr.mode] || "➡"} ${modeKo(tr.mode)} ${tr.min}분${tr.m ? ` · ${fmtDistance(tr.m)}` : ""}${tr.legs ? ` · ${tr.legs.map((l) => l.route).join(" → ")}` : ""} <span class="chip est" style="min-height:22px;padding:0 6px">${tr.confidence === "computed" ? "계산" : "추정"}</span>${tr.alternatives && tr.alternatives.length > 0 && html` <span class="note">대안: ${tr.alternatives.map((a) => `${modeKo(a.mode)} ${a.min}분`).join(", ")}</span>`}${tr.link && html` <a href=${tr.link} target="_blank" rel="noopener">구글맵</a>`}</div>`}
          <div class=${"card " + (it.fixed ? "sel" : "")} style="margin:0 0 4px">
            <div class="ico">${CAT_ICON[p.cat[0]] || "📍"}</div>
            <div class="body"><div class="title" onClick=${() => onOpenDetail(p.id)}>${toHHMM(it.start)}–${toHHMM(it.end)} ${placeName(p)}</div>
              <div class="chips meta">${it.flag && html`<${Chip} kind="warn">⚠ ${FLAG[it.flag]}</${Chip}>`}${plan.reservations[p.id] && plan.reservations[p.id] !== "none" && html`<${Chip} kind="warn">🎫 ${plan.reservations[p.id] === "required" ? "예약 필요" : "예약 권장"}</${Chip}>`}${plan.locks?.[p.id] && html`<${Chip}>🔒 잠금</${Chip}>`}</div>
              <div class="row" style="margin-top:6px;font-size:13px"><label class="note">체류</label><input type="number" min="15" max="600" step="15" value=${it.dwell} style="width:70px;min-height:36px" onChange=${(e) => onSetDwell(p.id, Number(e.target.value))} /><span class="note">분</span>
                <label class="note">예약 시각</label><input type="time" value=${plan.fixed?.[p.id] || ""} style="min-height:36px" onChange=${(e) => onSetFixed(p.id, e.target.value || null)} />
                <button class="btn secondary" style="min-height:36px;padding:2px 8px" onClick=${() => onToggleLock(p.id)}>${plan.locks?.[p.id] ? "잠금 해제" : "잠금"}</button>
                <select style="min-height:36px" value="" onChange=${(e) => { if (e.target.value) onMoveToDay(p.id, e.target.value); }}><option value="">다른 날로…</option>${days.map((d2, j) => j !== di && html`<option value=${d2.date}>${j + 1}일 ${d2.date.slice(5)}</option>`)}</select></div>
            </div></div></div>`; })())}
      <div class="row" style="margin-top:12px"><button class="btn secondary" disabled=${busy} onClick=${() => onRegenerateDay(day.date)}>이 날 재생성</button><button class="btn secondary" disabled=${busy} onClick=${onGenerate}>전체 재생성</button><button class="btn secondary" onClick=${() => setShowOverflow(!showOverflow)}>초과분 ${result.overflow.length}곳 ${showOverflow ? "▴" : "▾"}</button><button class="btn secondary" onClick=${onCost}>비용 €</button></div>
      ${showOverflow && html`<div class="card" style="margin:8px 0"><div class="body"><div class="title">초과분</div>${result.overflow.length === 0 ? html`<div class="note">없음</div>` : result.overflow.map((o) => { const p = getPlace(o.id); return p && html`<div class="row" style="padding:4px 0"><span style="flex:1" onClick=${() => onOpenDetail(p.id)}>${placeName(p)} <span class="note">${o.reason}</span></span><select style="min-height:36px" value="" onChange=${(e) => { if (e.target.value) onMoveToDay(p.id, e.target.value); }}><option value="">날짜에 넣기…</option>${days.map((d2, j) => html`<option value=${d2.date}>${j + 1}일 ${d2.date.slice(5)}</option>`)}</select></div>`; })}</div></div>`}
      <p class="note">잠긴 항목과 사용자가 배치한 항목은 재생성에도 유지됩니다(E4 4절 9항).</p>
    </div>`}
  </div>`;
}
