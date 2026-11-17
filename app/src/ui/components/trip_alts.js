// 전체 일정 대안(R-06, E2 4절 5항, D-051). 안 하나는 기준 하나와 그 기준에 맞춘 순서·일수·추천 기준의 조합이다.
import { useState } from "../../lib.js";
import { html } from "./ui.js";
import { destName } from "../../data/dest.js";
import { modeKo } from "../../engines/e3.js";

const BALANCE_KO = { landmark: "대표 명소 중심", balance: "균형", other: "취향 중심" };
export const ESTIMATE_NOTE = "(추정)이 붙은 시간은 거리로 어림한 값이며 실제 시간표가 아닙니다. 운행 여부와 시간을 직접 확인하세요.";
export const fmtMin = (m) => (m >= 60 ? `${Math.floor(m / 60)}시간${m % 60 ? ` ${m % 60}분` : ""}` : `${m}분`);

/**
 * alts: tripAlternatives의 결과(읽는 중이면 null). cities: 도시 레코드. canEdit: 적용할 수 있는 역할인가.
 * assignedCount: 날짜에 배치한 장소 수(있으면 적용할 때 유지할지 묻는다). onApply(alt, keepAssign), onAddDest(id).
 */
export function TripAlts({ alts, cities, canEdit, assignedCount = 0, onApply, onAddDest, destCount = 0, dayCapacity = 4 }) {
  const [asking, setAsking] = useState(null); // 배치 유지 여부를 묻고 있는 안
  const name = (id) => { const c = cities.find((x) => x.id === id); return c ? destName(c) : id; };
  if (destCount < 2) return html`<div class="tripalts"><h2>전체 일정 대안</h2><p class="note">여행지를 둘 이상 고르면 순서와 일수를 바꾼 대안을 견줄 수 있습니다.</p></div>`;
  if (!alts) return html`<div class="tripalts"><h2>전체 일정 대안</h2><p class="note">도시 간 이동 시간을 읽는 중…</p></div>`;
  const apply = (a, keep) => { setAsking(null); onApply && onApply(a, keep); };
  const anyEstimate = alts.some((a) => a.estimateLegs > 0);
  return html`<div class="tripalts">
    <h2>전체 일정 대안</h2>
    <p class="note">같은 여행지를 기준만 바꿔 짠 안입니다. 안을 적용하면 여행지 순서, 여행지별 일수, 추천 기준이 함께 바뀝니다. 순서와 일수는 일정 탭의 숙박에서 손으로도 바꿀 수 있습니다.</p>
    ${alts.map((a) => html`<div class=${"altcard " + (a.key === "base" ? "base" : "")} data-key=${a.key} key=${a.key}>
      <div class="alttitle"><b>${a.title}</b> <span class="note">${a.basis}</span>${a.key === "base" ? html` <span class="chip on">지금</span>` : a.same ? html` <span class="chip est">순서와 일수가 기본안과 같음</span>` : ""}</div>
      <div class="altroute">${a.order.map((id, i) => html`${i > 0 ? html`<span class="arrow"> → </span>` : ""}<span class="stop">${name(id)} <b>${a.days[id]}일</b></span>`)}</div>
      <div class="note altlegs">이동: ${a.legs.map((l) => `${name(l.from)}→${name(l.to)} ${modeKo(l.mode)} ${fmtMin(l.min)}${l.estimate ? "(추정)" : ""}`).join(" · ")}</div>
      <div class="note"><b>이동 시간 합 ${fmtMin(a.travelMin)}</b>${a.estimateLegs ? ` · 추정 ${a.estimateLegs}구간 포함` : ""} · 추천 기준 ${BALANCE_KO[a.balance] || a.balance} · 추천 장소 여행지마다 하루 ${dayCapacity}곳 × 일수</div>
      ${a.longLegs.map((l) => html`<div class="note warnline">⚠ ${name(l.from)}→${name(l.to)} 구간이 4시간을 넘습니다(${fmtMin(l.min)}).${l.stopovers.length ? html` 들를 만한 곳: ${l.stopovers.map((id) => html`<span class="chip stopover">${name(id)}${canEdit && onAddDest ? html` <button type="button" class="linkbtn addstop" onClick=${() => onAddDest(id)}>여행지에 추가</button>` : ""}</span>`)}` : ""}</div>`)}
      ${Object.keys(a.overPicked).length > 0 && html`<div class="note warnline">⚠ 고른 장소가 일수보다 많은 여행지: ${Object.entries(a.overPicked).map(([id, n]) => `${name(id)} ${n}곳 초과`).join(", ")}</div>`}
      ${canEdit && a.key !== "base" && (asking === a.key
        ? html`<div class="altask"><span class="note">날짜에 배치한 장소 ${assignedCount}곳이 있습니다. 배치를 유지할까요?</span>
            <div class="row"><button type="button" class="btn secondary sm keepassign" onClick=${() => apply(a, true)}>유지하고 적용</button><button type="button" class="btn secondary sm clearassign" onClick=${() => apply(a, false)}>배치 풀고 적용</button><button type="button" class="linkbtn" onClick=${() => setAsking(null)}>취소</button></div></div>`
        : html`<button type="button" class="btn secondary sm applyalt" onClick=${() => (assignedCount > 0 ? setAsking(a.key) : apply(a, true))}>이 안 적용</button>`)}
    </div>`)}
    ${anyEstimate && html`<p class="note estnote">${ESTIMATE_NOTE}</p>`}
  </div>`;
}
