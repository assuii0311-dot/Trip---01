// S2 요약(흐름 2, F-04·F-05). docs/04-wireframes.md S2
import { html, Chip } from "../components/ui.js";
import { firstSentences } from "../../data/places.js";
import { CAT_ICON } from "../../util/format.js";
import { destName, isIsland, inDest } from "../../data/dest.js";
import { placeName } from "../../data/places.js";

export function S2Summary({ trip, cities, categories, prof, onReselect, onExplore, selection = [], getPlace = () => null }) {
  const picks = selection.map(getPlace).filter(Boolean); // 지금까지 고른 장소(D-036)
  const catName = (id) => (categories.find((c) => c.id === id) || {}).ko || id;
  const selected = trip.cities.map((id) => cities.find((c) => c.id === id)).filter(Boolean);
  return html`<div>
    <section class="section">
      <h2>내 선호</h2>
      <p>"${prof.sentence}"</p>
      <div class="chips">${categories.map((c) => html`<${Chip} kind=${prof.weights[c.id] >= 1 ? "on" : ""}>${CAT_ICON[c.id] || ""} ${c.ko} ${prof.weights[c.id] >= 1 ? "▮▮▮" : "▮"}</${Chip}>`)}</div>
      <p class="note">선택 범주 1.0, 비선택 0.3(E2). 예산 ${prof.budget}, 하루 ${prof.dayCapacity}곳 안팎.</p>
      <button class="btn secondary" onClick=${onReselect}>다시 선택</button>
    </section>
    ${selected.length === 0 ? html`<div class="empty">입력에서 여행 도시를 선택하면 요약이 표시됩니다.</div>` : selected.map((c) => {
      const top = Object.entries(c.places?.cat || {}).sort((a, b) => b[1] - a[1]).slice(0, 3);
      const dens = c.lodging_3km >= 100 ? "높음" : c.lodging_3km >= 20 ? "보통" : "낮음";
      const sleepT = c.price_profile?.sleep?.tiers; const mode = sleepT ? Object.entries(sleepT).sort((a, b) => b[1] - a[1])[0]?.[0] : null;
      return html`<div class="card" key=${c.id}>
        <div class="body">
          <div class="title">${destName(c)} <span class="note">${c.n.es && c.n.es !== destName(c) ? c.n.es : ""}</span></div>
          <div class="chips meta">${isIsland(c) && html`<${Chip} kind="user">🏝 섬 · 지자체 ${c.members.length}곳</${Chip}>`}${(c.focus || []).map((f, i) => html`<${Chip} kind=${prof.weights[f] >= 1 ? "on" : "user"}>${CAT_ICON[f] || ""} ${catName(f)}${i === 0 ? " 중심" : ""}</${Chip}>`)}<${Chip} kind="star">★ 대표 명소 ${c.places?.foreign ?? 0}</${Chip}><${Chip}>1등급 ${(c.places?.tier1 ?? 0).toLocaleString()}</${Chip}><${Chip}>2등급 ${(c.places?.tier2 ?? 0).toLocaleString()}</${Chip}></div>
          <p>${c.ko?.summary ? c.ko.summary : c.wv?.lead ? c.wv.lead : c.wv?.understand ? firstSentences(c.wv.understand, 2) : html`<span class="note">${c.wiki?.en ? "가이드 개요 없음(위키백과 문서 있음)" : "가이드 개요 없음"}</span>`}</p>
          <div class="note">주요 범주: ${top.map(([k, v]) => `${catName(k)} ${v}`).join(" · ") || "—"}</div>
          <div class="note">숙박 밀도 ${dens}(중심 3km 안 ${c.lodging_3km}곳)${mode ? ` · 가격대 ${mode} 多` : ""}${c.transit_feeds?.length ? ` · 대중교통 피드 ${c.transit_feeds.length}` : ""}</div>
          ${(c.hl || []).length > 0 && html`<div class="note">대표 명소: ${c.hl.map((h) => h.n.ko || h.n.en || h.n.local).join(" · ")}</div>`}
          ${(c.ko?.summary || c.wv?.lead || c.wv?.understand) && html`<div class="src">출처: <a href=${"https://en.wikivoyage.org/wiki/" + encodeURIComponent((c.wv?.en || "").replace(/ /g, "_"))} target="_blank" rel="noopener">Wikivoyage "${c.wv?.en}"</a> (CC BY-SA 4.0). ${c.ko?.summary ? "한국어 요약은 이 가이드를 바탕으로 만든 생성본입니다(E5, 신뢰도 " + (c.ko.confidence || "보통") + ")." : "한국어 요약은 E5 생성 뒤 표시"}${c.n?.ko_src === "generated" ? " 한글 이름도 생성한 표기입니다." : ""}</div>`}
          ${(() => { const mine = picks.filter((p) => inDest(p, c)); return html`<div class=${"picks " + (mine.length ? "has" : "")}>${mine.length ? html`<b>고른 장소 ${mine.length}곳</b> ${mine.slice(0, 6).map(placeName).join(" · ")}${mine.length > 6 ? ` 외 ${mine.length - 6}곳` : ""}` : "아직 고른 장소가 없습니다."}</div>`; })()}
          <div style="margin-top:8px"><button class="btn secondary" onClick=${() => onExplore(c.id)}>장소 고르기 ▶</button></div>
        </div></div>`;
    })}
  </div>`;
}
