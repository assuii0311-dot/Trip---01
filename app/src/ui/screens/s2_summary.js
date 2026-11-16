// S2 요약(흐름 2, F-04·F-05). docs/04-wireframes.md S2
import { useEffect, useMemo, useState } from "../../lib.js";
import { html, Chip } from "../components/ui.js";
import { recommendForDestination } from "../../engines/e2.js";
import { firstSentences } from "../../data/places.js";
import { CAT_ICON } from "../../util/format.js";
import { destName, isIsland, inDest } from "../../data/dest.js";
import { placeName, placeLine } from "../../data/places.js";

const BALANCE = [["landmark", "대표 명소 중심"], ["balance", "균형"], ["other", "취향 중심"]];
const PREVIEW = 5; // 도시 카드에 미리 보이는 추천 수

/** 미리 보기: 대표 명소 3곳과 취향 추천 2곳. 한쪽이 모자라면 다른 쪽으로 채운다 */
function previewOf(recs) {
  const top = recs.filter((r) => r.bundle !== "taste"), taste = recs.filter((r) => r.bundle === "taste");
  const nTaste = Math.min(taste.length, Math.max(2, PREVIEW - top.length));
  return [...top.slice(0, PREVIEW - nTaste), ...taste.slice(0, nTaste)];
}

export function S2Summary({ trip, cities, categories, prof, onReselect, onExplore, selection = [], getPlace = () => null, tier1 = [], loader, nights = {}, recDays = {}, balance = "balance", onBalance, onToggleSelect, onAddMany, onOpenDetail, role = "local", onRemoveDest, onClearPicks, orphanCount = 0, onNext }) {
  const picks = selection.map(getPlace).filter(Boolean); // 지금까지 고른 장소(D-037)
  const canEdit = role === "main" || role === "local", canPick = role !== "viewer";
  // 추천 미리 보기(D-039): 탐색 화면과 같은 목록을 쓴다. 2등급(식당·카페·시장)은 도시 파일을 읽은 뒤 더해진다
  const [t2, setT2] = useState({});
  useEffect(() => {
    let alive = true;
    for (const id of trip.cities) if (loader && !(id in t2)) loader.tier2(id).then((rows) => alive && setT2((s) => ({ ...s, [id]: rows }))).catch(() => alive && setT2((s) => ({ ...s, [id]: [] })));
    return () => { alive = false; };
  }, [trip.cities.join(",")]);
  const recsBy = useMemo(() => Object.fromEntries(trip.cities.map((id) => {
    const c = cities.find((x) => x.id === id); if (!c) return [id, []];
    const all = tier1.filter((p) => inDest(p, c)).concat(t2[id] || []);
    return [id, recommendForDestination(all, { tastes: prof.tastes, dayCapacity: prof.dayCapacity, days: recDays[id] || nights[id] || 1, balance })];
  })), [trip.cities.join(","), t2, tier1, prof.tastes.join(","), balance, JSON.stringify(recDays), nights]);
  const catName = (id) => (categories.find((c) => c.id === id) || {}).ko || id;
  const selected = trip.cities.map((id) => cities.find((c) => c.id === id)).filter(Boolean);
  return html`<div>
    <section class="section">
      <h2>내 선호</h2>
      <p>"${prof.sentence}"</p>
      <div class="chips">${categories.map((c) => html`<${Chip} kind=${prof.weights[c.id] >= 1 ? "on" : ""}>${CAT_ICON[c.id] || ""} ${c.ko} ${prof.weights[c.id] >= 1 ? "▮▮▮" : "▮"}</${Chip}>`)}</div>
      <p class="note">예산 ${prof.budget}, 하루 ${prof.dayCapacity}곳 안팎. 고른 취향은 "취향 추천" 묶음에 쓰입니다.</p>
      <button class="btn secondary" onClick=${onReselect}>취향 다시 고르기</button>
    </section>
    ${selected.length > 0 && html`<section class="section" style="padding-top:0"><h2>추천 기준</h2>
      <div class="seg recbalance">${BALANCE.map(([k, v]) => html`<button class=${balance === k ? "on" : ""} onClick=${() => onBalance && onBalance(k)}>${v}</button>`)}</div>
      <p class="note">추천은 두 묶음입니다. "대표 명소"는 취향과 무관하게 그 여행지에서 가장 알려진 곳이고, "취향 추천"은 고른 취향에 드는 곳입니다. 기준은 두 묶음의 몫을 정합니다(대표 명소가 3/4, 절반, 1/4).${prof.tastes.length ? "" : " 취향을 고르지 않아 지금은 모두 대표 명소입니다."} "장소 고르기"의 추천 목록에도 같이 적용됩니다.</p></section>`}
    ${orphanCount > 0 && canEdit && html`<div class="picks" style="margin:0 16px 8px">선택한 여행지에 속하지 않는 고른 장소가 ${orphanCount}곳 있습니다(여행지를 빼기 전에 고른 곳). <button type="button" class="linkbtn clearorphan" onClick=${() => onClearPicks && onClearPicks("orphan")}>지우기</button></div>`}
    ${selected.length === 0 ? html`<div class="empty">입력에서 여행 도시를 선택하면 요약이 표시됩니다.</div>` : selected.map((c) => {
      const top = Object.entries(c.places?.cat || {}).sort((a, b) => b[1] - a[1]).slice(0, 3);
      const dens = c.lodging_3km >= 100 ? "높음" : c.lodging_3km >= 20 ? "보통" : "낮음";
      const sleepT = c.price_profile?.sleep?.tiers; const mode = sleepT ? Object.entries(sleepT).sort((a, b) => b[1] - a[1])[0]?.[0] : null;
      return html`<div class="card" key=${c.id}>
        <div class="body">
          <div class="title">${destName(c)} <span class="note">${c.n.es && c.n.es !== destName(c) ? c.n.es : ""}</span>${canEdit && onRemoveDest ? html`<button type="button" class="linkbtn removedest" style="float:right;font-weight:400;font-size:14px" onClick=${() => onRemoveDest(c.id)}>여행지 빼기</button>` : ""}</div>
          <div class="chips meta">${isIsland(c) && html`<${Chip} kind="user">🏝 섬 · 지자체 ${c.members.length}곳</${Chip}>`}${(c.focus || []).map((f, i) => html`<${Chip} kind=${prof.weights[f] >= 1 ? "on" : "user"}>${CAT_ICON[f] || ""} ${catName(f)}${i === 0 ? " 중심" : ""}</${Chip}>`)}<${Chip} kind="star">★ 대표 명소 ${c.places?.foreign ?? 0}</${Chip}><${Chip}>1등급 ${(c.places?.tier1 ?? 0).toLocaleString()}</${Chip}><${Chip}>2등급 ${(c.places?.tier2 ?? 0).toLocaleString()}</${Chip}></div>
          <p>${c.ko?.summary ? c.ko.summary : c.wv?.lead ? c.wv.lead : c.wv?.understand ? firstSentences(c.wv.understand, 2) : html`<span class="note">${c.wiki?.en ? "가이드 개요 없음(위키백과 문서 있음)" : "가이드 개요 없음"}</span>`}</p>
          <div class="note">주요 범주: ${top.map(([k, v]) => `${catName(k)} ${v}`).join(" · ") || "—"}</div>
          <div class="note">숙박 밀도 ${dens}(중심 3km 안 ${c.lodging_3km}곳)${mode ? ` · 가격대 ${mode} 多` : ""}${c.transit_feeds?.length ? ` · 대중교통 피드 ${c.transit_feeds.length}` : ""}</div>
          ${(c.hl || []).length > 0 && html`<div class="note">대표 명소: ${c.hl.map((h) => h.n.ko || h.n.en || h.n.local).join(" · ")}</div>`}
          ${(c.ko?.summary || c.wv?.lead || c.wv?.understand) && html`<div class="src">출처: <a href=${"https://en.wikivoyage.org/wiki/" + encodeURIComponent((c.wv?.en || "").replace(/ /g, "_"))} target="_blank" rel="noopener">Wikivoyage "${c.wv?.en}"</a> (CC BY-SA 4.0). ${c.ko?.summary ? "한국어 요약은 이 가이드를 바탕으로 만든 생성본입니다(E5, 신뢰도 " + (c.ko.confidence || "보통") + ")." : "한국어 요약은 E5 생성 뒤 표시"}${c.n?.ko_src === "generated" ? " 한글 이름도 생성한 표기입니다." : ""}</div>`}
          ${(() => { const mine = picks.filter((p) => inDest(p, c)); return html`<div class=${"picks " + (mine.length ? "has" : "")}>${mine.length ? html`<b>고른 장소 ${mine.length}곳</b> ${mine.slice(0, 6).map(placeName).join(" · ")}${mine.length > 6 ? ` 외 ${mine.length - 6}곳` : ""}` : "아직 고른 장소가 없습니다."}${mine.length > 0 && canEdit ? html` <button type="button" class="linkbtn clearcity" onClick=${() => onClearPicks && onClearPicks(c.id)}>이 여행지에서 고른 장소 지우기</button>` : ""}</div>`; })()}
          ${(() => { const recs = recsBy[c.id] || [], rest = recs.filter((r) => !selection.includes(r.p.id)); const nTaste = recs.filter((r) => r.bundle === "taste").length; const prev = previewOf(recs); return recs.length > 0 && html`<div class="recprev">
            <div class="note">추천 ${recs.length}곳(대표 명소 ${recs.length - nTaste}곳${nTaste ? ` · 취향 추천 ${nTaste}곳` : ""}) 가운데 ${prev.length}곳${!(c.id in t2) ? " · 식당·카페 읽는 중…" : ""}</div>
            ${prev.map((r) => { const ln = placeLine(r.p), on = selection.includes(r.p.id); return html`<div class="recrow" key=${r.p.id}>
              <div class="what" onClick=${() => onOpenDetail && onOpenDetail(r.p.id)}><b>${CAT_ICON[r.p.cat[0]] || "📍"} ${placeName(r.p)}</b> <span class=${"chip bundle " + (r.bundle === "taste" ? "ok" : "star")}>${r.bundle === "taste" ? "취향" : "대표 명소"}</span>${ln ? html`<div class=${"line " + (ln.lang === "ko" ? "" : "orig")}>${ln.text}</div>` : ""}</div>
              ${canPick && html`<button type="button" class="pickbtn" aria-label=${on ? "선택 해제" : "선택"} aria-pressed=${on} onClick=${() => onToggleSelect && onToggleSelect(r.p.id)}>${on ? "✓" : "+"}</button>`}</div>`; })}
            <div class="row" style="margin-top:8px"><button class="btn secondary explore" onClick=${() => onExplore(c.id)}>장소 고르기 ▶</button>
              ${canEdit && html`<button class="btn secondary addall" disabled=${rest.length === 0} onClick=${() => onAddMany && onAddMany(rest.map((r) => r.p.id))}>${rest.length ? `추천 ${rest.length}곳 모두 담기` : "추천을 모두 담았습니다"}</button>`}</div></div>`; })()}
          ${!(recsBy[c.id] || []).length && html`<div style="margin-top:8px"><button class="btn secondary explore" onClick=${() => onExplore(c.id)}>장소 고르기 ▶</button></div>`}
        </div></div>`;
    })}
    <div style="height:64px"></div>
    <div class="stepnav"><button type="button" class="btn secondary clearall" disabled=${selection.length === 0 || !canEdit} onClick=${() => onClearPicks && onClearPicks("all")}>고른 장소 모두 지우기</button><button type="button" class="btn tonext" onClick=${() => onNext && onNext()}>일정 만들기 ▶ <span style="font-weight:400">고른 장소 ${selection.length}곳</span></button></div>
  </div>`;
}
