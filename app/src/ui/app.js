// 앱 틀: 상단 바, 하단 탭 5개, 화면 전환. docs/03-screen-flow.md 1절
import { useEffect, useState } from "../lib.js";
import { html, Empty } from "./components/ui.js";
import { S1Input } from "./screens/s1_input.js";
import { S3Explore } from "./screens/s3_explore.js";
import { S6Detail } from "./screens/s6_detail.js";
import { loadDraft, saveDraft } from "../state/store.js";

const TABS = [["input", "입력", "📝"], ["explore", "탐색", "🧭"], ["plan", "일정", "📅"], ["share", "공유", "🤝"], ["settings", "설정", "⚙️"]];
const SEL_KEY = "trip01.selection.v1";

export function App({ data, loader }) {
  const [tab, setTab] = useState("input");
  const [trip, setTripState] = useState(() => loadDraft(localStorage));
  const [selection, setSelection] = useState(() => { try { return JSON.parse(localStorage.getItem(SEL_KEY) || "[]"); } catch { return []; } });
  const [detailId, setDetailId] = useState(null);
  const role = "main"; // E7 전까지는 단일 사용자(메인). 묶음 9에서 역할 판정
  const setTrip = (t) => { setTripState(t); saveDraft(localStorage, t); };
  useEffect(() => { try { localStorage.setItem(SEL_KEY, JSON.stringify(selection)); } catch {} }, [selection]);
  const toggleSelect = (id) => setSelection((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const byId = new Map(data.tier1.map((p) => [p.id, p]));
  const detail = detailId ? (byId.get(detailId) || data.tier2cache.get(detailId)) : null;
  const openDetail = (id) => setDetailId(id);
  // 2등급 상세를 위해 로더 결과를 기억한다
  const loaderWithCache = { ...loader, tier2: async (c) => { const rows = await loader.tier2(c); rows.forEach((p) => data.tier2cache.set(p.id, p)); return rows; } };
  const titles = { input: "입력", explore: "탐색·추천", plan: "일정표", share: "공유", settings: "설정" };
  return html`
    <header class="top"><h1>${titles[tab]}</h1><span class="version" title="데이터 갱신일">데이터 ${data.attribution.generated}</span></header>
    <main class="main">
      ${tab === "input" && html`<${S1Input} trip=${trip} setTrip=${setTrip} cities=${data.cities} airports=${data.airports} categories=${data.categories} role=${role} onDone=${() => setTab("explore")} />`}
      ${tab === "explore" && html`<${S3Explore} trip=${trip} cities=${data.cities} categories=${data.categories} tier1=${data.tier1} loader=${loaderWithCache} selection=${selection} onToggleSelect=${toggleSelect} onOpenDetail=${openDetail} selectedId=${detailId} />`}
      ${tab === "plan" && html`<${Empty}>선택 ${selection.length}곳. 배치·숙박(묶음 4)과 일정 생성(묶음 5)은 다음 묶음에서 제공됩니다.</${Empty}>`}
      ${tab === "share" && html`<${Empty}>내보내기·My Maps(묶음 6), 제안·승인(묶음 9)은 다음 묶음에서 제공됩니다.</${Empty}>`}
      ${tab === "settings" && html`<section class="section"><h2>출처 표기</h2><ul>${data.attribution.sources.map((s) => html`<li><a href=${s.url} target="_blank" rel="noopener">${s.source}</a> · ${s.license} · ${s.text}</li>`)}</ul>
        <p class="note">기준 데이터 생성일 ${data.attribution.generated}. 장소 ${data.attribution.counts.places.toLocaleString()}곳(1등급 ${data.attribution.counts.tier1.toLocaleString()}), 도시 ${data.attribution.counts.cities.toLocaleString()}. 데이터 라이선스는 저장소의 data/LICENSE-DATA.md. 지도: © OpenStreetMap contributors, OpenFreeMap.</p>
        <h2>앱 정보</h2><p class="note">Trip01 v0.1 (묶음 2). 저장소·Key·토큰 설정은 묶음 4(E7)에서 제공됩니다.</p></section>`}
    </main>
    ${detail && html`<${S6Detail} place=${detail} categories=${data.categories} loader=${loader} onClose=${() => setDetailId(null)} selected=${selection.includes(detail.id)} onToggleSelect=${() => toggleSelect(detail.id)} />`}
    <nav class="tabs" aria-label="주 탐색">${TABS.map(([k, label, ico]) => html`<button class=${tab === k ? "on" : ""} onClick=${() => { setTab(k); setDetailId(null); }} aria-current=${tab === k ? "page" : undefined}><span class="ico" aria-hidden="true">${ico}</span>${label}</button>`)}</nav>`;
}
