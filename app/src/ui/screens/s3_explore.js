// S3 탐색·추천(흐름 3, F-06~F-08). 묶음 2는 "전체 후보"만. 추천 탭은 묶음 3(E2)에서 채운다.
import { useEffect, useMemo, useRef, useState } from "../../lib.js";
import { exploreFilterCount, clearedExplore } from "../../state/nav.js";
import { html, Chip, Empty } from "../components/ui.js";
import { createMap } from "../components/map.js";
import { filterPlaces, sortByProminence, placeName, altNames, isForeignLandmark, placeLine } from "../../data/places.js";
import { recommendForDestination, cityAlternatives } from "../../engines/e2.js";
import { CAT_ICON } from "../../util/format.js";
import { inDest, destName, isIsland } from "../../data/dest.js";
import { TripAlts } from "../components/trip_alts.js";

export function S3Explore({ trip, cities, categories, tier1, loader, selection, onToggleSelect, onOpenDetail, selectedId, prof, nights, recDays = {}, ui, setUi, role = "local", altIds = [], onClearPicks, onNext, tripAlts = null, onApplyTrip, onAddDest, assignedCount = 0 }) {
  const canPick = role !== "viewer"; // 공유자는 열람만(R-22). 서브 수립자의 선택은 제안으로 보내진다
  const tripCities = trip.cities.length ? trip.cities : cities.filter((c) => c.stratum === "big").sort((a, b) => (b.pop || 0) - (a.pop || 0)).slice(0, 10).map((c) => c.id);
  // 보던 도시, 추천/전체, 검색어, 범주 필터, 추천 기준은 App이 든다(다른 화면에 다녀와도 남는다, D-036). ui가 없으면 화면 안에서만 기억한다
  const [local, setLocal] = useState({ city: null, list: null, q: "", cats: [], balance: null });
  const view = ui || local, patch = setUi || ((p) => setLocal((s) => ({ ...s, ...p })));
  const cityId = tripCities.includes(view.city) ? view.city : tripCities[0] || null;
  const tab = view.list || (trip.cities.length ? "rec" : "all");
  const balance = view.balance || trip.foreignBalance || "balance";
  const cats = view.cats, q = view.q;
  const setCityId = (v) => patch({ city: v }), setTab = (v) => patch({ list: v }), setBalance = (v) => patch({ balance: v }), setCats = (v) => patch({ cats: v }), setQ = (v) => patch({ q: v });
  const [altOpen, setAltOpen] = useState(false);
  const [tier2, setTier2] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mapOpen, setMapOpen] = useState(true);
  const mapEl = useRef(null); const mapRef = useRef(null);
  useEffect(() => {
    let alive = true; setLoading(true);
    loader.tier2(cityId).then((rows) => { if (alive) { setTier2(rows); setLoading(false); } });
    return () => { alive = false; };
  }, [cityId]);
  const city = cities.find((c) => c.id === cityId);
  const all = useMemo(() => tier1.filter((p) => inDest(p, city)).concat(tier2), [tier1, tier2, cityId]); // 섬이면 소속 지자체의 장소를 모두 본다(D-030)
  const shown = useMemo(() => sortByProminence(filterPlaces(all, { cats, query: q })).slice(0, 300), [all, cats, q]);
  const days = recDays?.[cityId] || nights?.[cityId] || 1; // 추천 수 = 하루 수용 × 이 여행지의 일수(E2 4절 4항, D-049)
  const recOpts = { tastes: prof.tastes, dayCapacity: prof.dayCapacity, days, balance };
  const recs = useMemo(() => (tab === "rec" ? recommendForDestination(all, recOpts) : []), [all, tab, prof.tastes.join(","), balance, days, cityId]);
  const alts = useMemo(() => (altOpen ? cityAlternatives(all.filter((p) => p.tier === 1), { ...recOpts, limit: 8 }) : null), [altOpen, all, prof.tastes.join(","), days, cityId]);
  const nTasteRec = recs.filter((r) => r.bundle === "taste").length;
  const topIds = useMemo(() => new Set(recs.filter((r) => r.bundle === "top").map((r) => r.p.id)), [recs]);
  const listed = tab === "rec" ? recs.map((r) => r.p) : shown;
  // 지도에는 목록의 장소와 함께 이 여행지에서 이미 고른 장소를 언제나 보인다(목록의 필터에 걸려 빠졌더라도)
  const picked = useMemo(() => new Set(selection), [selection]);
  const alt = useMemo(() => new Set(altIds), [altIds.join(",")]); // 열어 본 장소의 대안(D-039). 지도에 따로 표시한다
  const mapList = useMemo(() => { const ids = new Set(listed.map((p) => p.id)); return listed.concat(all.filter((p) => (picked.has(p.id) || alt.has(p.id)) && !ids.has(p.id))); }, [listed, all, picked, alt]);
  const pickedHere = useMemo(() => all.filter((p) => picked.has(p.id)).length, [all, picked]);
  useEffect(() => {
    if (!mapEl.current || mapRef.current) return;
    mapRef.current = createMap(mapEl.current, { onSelect: (id) => onOpenDetail(id) });
  }, []);
  useEffect(() => {
    const m = mapRef.current; if (!m) return;
    // 추천 목록에서는 대표 명소 묶음을, 전체 후보에서는 해외 대표 명소(D-020)를 금색으로 보인다(D-049)
    m.setPlaces(mapList, { selectedId, isLandmark: tab === "rec" ? (p) => topIds.has(p.id) : isForeignLandmark, picked, alt });
  }, [mapList, selectedId, picked, alt, tab, topIds]);
  // 지도의 보는 범위는 도시나 목록 조건이 바뀔 때만 옮긴다(장소를 고르거나 상세를 열 때는 그대로 둔다)
  useEffect(() => {
    const m = mapRef.current; if (!m) return;
    if (city && !isIsland(city) && !q && !cats.length) m.flyTo(city.lat, city.lon, 13); else if (listed.length) m.fitTo(listed);
  }, [cityId, tab, q, cats.join(","), listed.length]);
  useEffect(() => { mapRef.current && setTimeout(() => mapRef.current.resize(), 50); }, [mapOpen]);
  const catName = (id) => (categories.find((c) => c.id === id) || {}).ko || id;
  const nFilters = exploreFilterCount({ q, cats });
  return html`<div class="two">
    <div class="list">
      <div class="toolbar">
        <select value=${cityId || ""} onChange=${(e) => setCityId(e.target.value)}>${tripCities.map((id) => { const c = cities.find((x) => x.id === id); return html`<option value=${id}>${c ? destName(c) : id}</option>`; })}</select>
        <div class="seg" style="flex:none"><button class=${tab === "rec" ? "on" : ""} onClick=${() => setTab("rec")}>추천</button><button class=${tab === "all" ? "on" : ""} onClick=${() => setTab("all")}>전체 후보</button></div>
      </div>
      ${tab === "rec" ? html`
        <div class="toolbar"><div class="seg" style="flex:1">${[["landmark", "대표 명소 중심"], ["balance", "균형"], ["other", "취향 중심"]].map(([k, v]) => html`<button class=${balance === k ? "on" : ""} onClick=${() => setBalance(k)}>${v}</button>`)}</div><button class="btn secondary" style="min-height:40px" onClick=${() => setAltOpen(true)}>대안 ▸</button></div>
        <p class="note" style="padding:0 16px">${city ? `${destName(city)} · 추천 ${recs.length}곳(하루 ${prof.dayCapacity}곳 × ${days}일) · 대표 명소 ${recs.length - nTasteRec}곳${nTasteRec ? ` + 취향 추천 ${nTasteRec}곳` : ""}` : ""}${loading ? " · 읽는 중…" : ""}${prof.tastes.length ? "" : " · 취향을 고르면 취향 추천 묶음이 생깁니다"}</p>
        ${recs.length === 0 ? html`<${Empty}>${loading ? "읽는 중…" : "추천할 장소가 없습니다."}</${Empty}>` : recs.map((r, i) => html`${(i === 0 || recs[i - 1].bundle !== r.bundle) && html`<h3 class="bundlehead" key=${"h-" + r.bundle}>${r.bundle === "taste" ? `취향 추천 ${nTasteRec}곳` : `대표 명소 ${recs.length - nTasteRec}곳`} <span class="note">${r.bundle === "taste" ? `고른 취향(${prof.tastes.map(catName).join(", ")})에 드는 곳, 알려진 순` : "취향과 무관하게 이 여행지에서 가장 알려진 곳"}</span></h3>`}<div class=${"card " + (selection.includes(r.p.id) ? "sel" : "")} key=${r.p.id} onClick=${() => onOpenDetail(r.p.id)}>
          <div class="ico">${CAT_ICON[r.p.cat[0]] || "📍"}</div>
          <div class="body"><div class="title">${placeName(r.p)}</div>${altNames(r.p) && html`<div class="sub">${altNames(r.p)}</div>`}${(() => { const ln = placeLine(r.p); return ln && html`<div class=${"line " + (ln.lang === "ko" ? "" : "orig")}>${ln.text}</div>`; })()}
            <div class="meta chips"><${Chip} kind=${r.bundle === "taste" ? "ok" : "star"}>${r.reasons.join(" · ")}</${Chip}>${r.p.cat.slice(0, 2).map((c) => html`<${Chip}>${catName(c)}</${Chip}>`)}<${Chip} kind="est">인기 ${r.score.toFixed(2)}</${Chip}>${r.p.hrs == null && html`<${Chip} kind="warn">⚠ 영업시간</${Chip}>`}</div></div>
          ${canPick && html`<button class="btn secondary" style="min-width:44px;padding:4px 10px" aria-label="선택" onClick=${(e) => { e.stopPropagation(); onToggleSelect(r.p.id); }}>${selection.includes(r.p.id) ? "✓" : "+"}</button>`}</div>`)}
        ${altOpen && alts && html`<div class="sheet" role="dialog" aria-label="대안"><button class="close" aria-label="닫기" onClick=${() => setAltOpen(false)}>✕</button>
          <${TripAlts} alts=${tripAlts} cities=${cities} canEdit=${role === "main" || role === "local"} assignedCount=${assignedCount} onApply=${onApplyTrip} onAddDest=${onAddDest} destCount=${tripCities.length} dayCapacity=${prof.dayCapacity} />
          <h2 style="margin-top:20px">도시 기준 대안 <span class="note">${city ? destName(city) : ""}</span></h2><p class="note">같은 여행지에서 추천 기준만 바꾼 두 세트입니다. 장소 기준 대안은 장소 상세에 있습니다.</p>
          ${[["landmark", "대표 명소 중심 세트"], ["other", "취향 중심 세트"]].map(([k, title]) => html`<h3 style="font-size:17px;margin:12px 0 4px">${title}</h3>${alts[k].map((r) => html`<div class="row" style="padding:6px 0;border-bottom:1px solid var(--line)"><span style="flex:1">${CAT_ICON[r.p.cat[0]] || ""} ${placeName(r.p)} <span class="note">${r.score.toFixed(2)}</span></span><button class="btn secondary" style="min-height:36px;padding:4px 10px" onClick=${() => onToggleSelect(r.p.id)}>${selection.includes(r.p.id) ? "✓" : "+"}</button></div>`)}`)}
        </div>`}` : html`
        <div class="toolbar"><input placeholder="장소 이름 검색" value=${q} onInput=${(e) => setQ(e.target.value)} /><button class="btn secondary" style="min-height:40px" onClick=${() => setMapOpen(!mapOpen)}>${mapOpen ? "지도 접기" : "지도"}</button></div>
        <div class="toolbar chips">${categories.map((c) => html`<button class=${"chip " + (cats.includes(c.id) ? "on" : "")} onClick=${() => setCats(cats.includes(c.id) ? cats.filter((x) => x !== c.id) : [...cats, c.id])}>${CAT_ICON[c.id] || ""} ${c.ko}</button>`)}</div>
        <p class="note" style="padding:0 16px">${city ? `${destName(city)} · 1등급 ${city.places?.tier1 ?? 0}곳, 2등급 ${city.places?.tier2 ?? 0}곳` : ""}${loading ? " · 2등급 읽는 중…" : ""} · 표시 ${shown.length}곳${nFilters > 0 ? html` · <button type="button" class="linkbtn" onClick=${() => patch(clearedExplore())}>필터 지우기</button>` : ""}${shown.length === 300 ? " (상위 300)" : ""}</p>
        ${shown.length === 0 ? html`<${Empty}>${loading ? "읽는 중…" : "조건에 맞는 장소가 없습니다."}</${Empty}>` : shown.map((p) => html`<div class=${"card " + (selection.includes(p.id) ? "sel" : "")} key=${p.id} onClick=${() => onOpenDetail(p.id)}>
          <div class="ico">${CAT_ICON[p.cat[0]] || "📍"}</div>
          <div class="body"><div class="title">${placeName(p)}</div>${altNames(p) && html`<div class="sub">${altNames(p)}</div>`}${(() => { const ln = placeLine(p); return ln && html`<div class=${"line " + (ln.lang === "ko" ? "" : "orig")}>${ln.text}</div>`; })()}
            <div class="meta chips">${isForeignLandmark(p) && html`<${Chip} kind="star">★ 해외 대표 명소</${Chip}>`}${p.cat.slice(0, 2).map((c) => html`<${Chip}>${catName(c)}</${Chip}>`)}${p.hrs == null && html`<${Chip} kind="warn">⚠ 영업시간</${Chip}>`}${p.ver === false && html`<${Chip} kind="x">◌ 검증 안 됨</${Chip}>`}${p.tier === 1 && html`<${Chip} kind="est">1등급</${Chip}>`}</div></div>
          ${canPick && html`<button class="btn secondary" style="min-width:44px;padding:4px 10px" aria-label="선택" onClick=${(e) => { e.stopPropagation(); onToggleSelect(p.id); }}>${selection.includes(p.id) ? "✓" : "+"}</button>`}</div>`)}`}
      <div class="listnav"><button type="button" class="btn secondary clearcity" disabled=${pickedHere === 0 || role === "viewer" || role === "sub"} onClick=${() => onClearPicks && onClearPicks(cityId)}>이 여행지 ${pickedHere}곳 지우기</button><button type="button" class="btn tonext" onClick=${() => onNext && onNext()}>일정 만들기 ▶ <span style="font-weight:400">고른 장소 ${selection.length}곳</span></button></div>
    </div>
    <div class="mapwrap"><div class=${"map " + (mapOpen ? "" : "collapsed")} ref=${mapEl}></div>
      ${mapOpen && html`<div class="maplegend" aria-label="지도 표시"><span><i class="dot picked"></i>고른 곳 ${pickedHere}</span>${alt.size > 0 && html`<span><i class="dot alt"></i>대안 ${alt.size}</span>`}<span><i class="dot landmark"></i>${tab === "rec" ? "대표 명소" : "해외 대표 명소"}</span><span><i class="dot other"></i>${tab === "rec" ? "취향 추천" : "그 밖"}</span></div>`}</div>
  </div>`;
}
