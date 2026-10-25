// S3 탐색·추천(흐름 3, F-06~F-08). 묶음 2는 "전체 후보"만. 추천 탭은 묶음 3(E2)에서 채운다.
import { useEffect, useMemo, useRef, useState } from "../../lib.js";
import { html, Chip, Empty } from "../components/ui.js";
import { createMap } from "../components/map.js";
import { filterPlaces, sortByProminence, placeName, altNames, isForeignLandmark } from "../../data/places.js";
import { recommend, cityAlternatives } from "../../engines/e2.js";
import { CAT_ICON } from "../../util/format.js";

export function S3Explore({ trip, cities, categories, tier1, loader, selection, onToggleSelect, onOpenDetail, selectedId, prof, nights, initialCity }) {
  const tripCities = trip.cities.length ? trip.cities : cities.filter((c) => c.stratum === "big").sort((a, b) => (b.pop || 0) - (a.pop || 0)).slice(0, 10).map((c) => c.id);
  const [cityId, setCityId] = useState(initialCity || tripCities[0] || null);
  const [tab, setTab] = useState(trip.cities.length ? "rec" : "all");
  const [altOpen, setAltOpen] = useState(false);
  const [balance, setBalance] = useState(trip.foreignBalance || "balance");
  const [cats, setCats] = useState([]);
  const [q, setQ] = useState("");
  const [tier2, setTier2] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mapOpen, setMapOpen] = useState(true);
  const mapEl = useRef(null); const mapRef = useRef(null);
  useEffect(() => { if (!tripCities.includes(cityId)) setCityId(tripCities[0] || null); }, [trip.cities.join(",")]);
  useEffect(() => {
    let alive = true; setLoading(true);
    loader.tier2(cityId).then((rows) => { if (alive) { setTier2(rows); setLoading(false); } });
    return () => { alive = false; };
  }, [cityId]);
  const all = useMemo(() => tier1.filter((p) => p.city === cityId).concat(tier2), [tier1, tier2, cityId]);
  const shown = useMemo(() => sortByProminence(filterPlaces(all, { cats, query: q })).slice(0, 300), [all, cats, q]);
  const recOpts = { weights: prof.weights, dayCapacity: prof.dayCapacity, nights: nights?.[cityId] || 1, balance };
  const recs = useMemo(() => (tab === "rec" ? recommend(all.filter((p) => p.tier === 1 || p.cat.some((c) => ["restaurant", "cafe", "market"].includes(c))), recOpts) : []), [all, tab, prof, balance, nights, cityId]);
  const alts = useMemo(() => (altOpen ? cityAlternatives(all.filter((p) => p.tier === 1), { ...recOpts, limit: 8 }) : null), [altOpen, all, prof, nights, cityId]);
  const mapList = tab === "rec" ? recs.map((r) => r.p) : shown;
  const city = cities.find((c) => c.id === cityId);
  useEffect(() => {
    if (!mapEl.current || mapRef.current) return;
    mapRef.current = createMap(mapEl.current, { onSelect: (id) => onOpenDetail(id) });
  }, []);
  useEffect(() => {
    const m = mapRef.current; if (!m) return;
    m.setPlaces(mapList, { selectedId, isLandmark: isForeignLandmark });
    if (city && !q && !cats.length) m.flyTo(city.lat, city.lon, 13); else if (mapList.length) m.fitTo(mapList);
  }, [mapList, selectedId]);
  useEffect(() => { mapRef.current && setTimeout(() => mapRef.current.resize(), 50); }, [mapOpen]);
  const catName = (id) => (categories.find((c) => c.id === id) || {}).ko || id;
  return html`<div class="two">
    <div class="list">
      <div class="toolbar">
        <select value=${cityId || ""} onChange=${(e) => setCityId(e.target.value)}>${tripCities.map((id) => { const c = cities.find((x) => x.id === id); return html`<option value=${id}>${c ? c.n.ko || c.n.es : id}</option>`; })}</select>
        <div class="seg" style="flex:none"><button class=${tab === "rec" ? "on" : ""} onClick=${() => setTab("rec")}>추천</button><button class=${tab === "all" ? "on" : ""} onClick=${() => setTab("all")}>전체 후보</button></div>
      </div>
      ${tab === "rec" ? html`
        <div class="toolbar"><div class="seg" style="flex:1">${[["landmark", "대표 명소 중심"], ["balance", "균형"], ["other", "그 밖 중심"]].map(([k, v]) => html`<button class=${balance === k ? "on" : ""} onClick=${() => setBalance(k)}>${v}</button>`)}</div><button class="btn secondary" style="min-height:40px" onClick=${() => setAltOpen(true)}>대안 ▸</button></div>
        <p class="note" style="padding:0 16px">${city ? `${city.n.ko || city.n.es} · 추천 ${recs.length}곳(하루 ${prof.dayCapacity}곳 × ${nights?.[cityId] || 1}박 × 1.5)` : ""}${loading ? " · 읽는 중…" : ""} · 점수 = 취향 0.5 + 대표성 0.4 + 유산 0.1</p>
        ${recs.length === 0 ? html`<${Empty}>${loading ? "읽는 중…" : "추천할 장소가 없습니다."}</${Empty}>` : recs.map((r) => html`<div class=${"card " + (selection.includes(r.p.id) ? "sel" : "")} key=${r.p.id} onClick=${() => onOpenDetail(r.p.id)}>
          <div class="ico">${CAT_ICON[r.p.cat[0]] || "📍"}</div>
          <div class="body"><div class="title">${placeName(r.p)}</div>${altNames(r.p) && html`<div class="sub">${altNames(r.p)}</div>`}
            <div class="meta chips">${r.landmark ? html`<${Chip} kind="star">★ 대표 명소</${Chip}>` : html`<${Chip} kind="est">그 밖의 장소</${Chip}>`}${r.p.cat.slice(0, 2).map((c) => html`<${Chip}>${catName(c)}</${Chip}>`)}<${Chip} kind="ok">${r.score.toFixed(2)} · ${r.reasons.join(", ")}</${Chip}>${r.p.hrs == null && html`<${Chip} kind="warn">⚠ 영업시간</${Chip}>`}</div></div>
          <button class="btn secondary" style="min-width:44px;padding:4px 10px" aria-label="선택" onClick=${(e) => { e.stopPropagation(); onToggleSelect(r.p.id); }}>${selection.includes(r.p.id) ? "✓" : "+"}</button></div>`)}
        ${altOpen && alts && html`<div class="sheet" role="dialog" aria-label="대안"><button class="close" aria-label="닫기" onClick=${() => setAltOpen(false)}>✕</button>
          <h2>도시 기준 대안</h2><p class="note">전체 일정 기준 대안(도시 조합·일수)은 묶음 5(이동 시간) 뒤에 제공됩니다. 장소 기준 대안은 장소 상세에 있습니다.</p>
          ${[["landmark", "★ 대표 명소 중심 세트"], ["other", "그 밖의 장소 중심 세트"]].map(([k, title]) => html`<h3 style="font-size:17px;margin:12px 0 4px">${title}</h3>${alts[k].map((r) => html`<div class="row" style="padding:6px 0;border-bottom:1px solid var(--line)"><span style="flex:1">${CAT_ICON[r.p.cat[0]] || ""} ${placeName(r.p)} <span class="note">${r.score.toFixed(2)}</span></span><button class="btn secondary" style="min-height:36px;padding:4px 10px" onClick=${() => onToggleSelect(r.p.id)}>${selection.includes(r.p.id) ? "✓" : "+"}</button></div>`)}`)}
        </div>`}` : html`
        <div class="toolbar"><input placeholder="장소 이름 검색" value=${q} onInput=${(e) => setQ(e.target.value)} /><button class="btn secondary" style="min-height:40px" onClick=${() => setMapOpen(!mapOpen)}>${mapOpen ? "지도 접기" : "지도"}</button></div>
        <div class="toolbar chips">${categories.map((c) => html`<button class=${"chip " + (cats.includes(c.id) ? "on" : "")} onClick=${() => setCats(cats.includes(c.id) ? cats.filter((x) => x !== c.id) : [...cats, c.id])}>${CAT_ICON[c.id] || ""} ${c.ko}</button>`)}</div>
        <p class="note" style="padding:0 16px">${city ? `${city.n.ko || city.n.es} · 1등급 ${city.places?.tier1 ?? 0}곳, 2등급 ${city.places?.tier2 ?? 0}곳` : ""}${loading ? " · 2등급 읽는 중…" : ""} · 표시 ${shown.length}곳${shown.length === 300 ? " (상위 300)" : ""}</p>
        ${shown.length === 0 ? html`<${Empty}>${loading ? "읽는 중…" : "조건에 맞는 장소가 없습니다."}</${Empty}>` : shown.map((p) => html`<div class=${"card " + (selection.includes(p.id) ? "sel" : "")} key=${p.id} onClick=${() => onOpenDetail(p.id)}>
          <div class="ico">${CAT_ICON[p.cat[0]] || "📍"}</div>
          <div class="body"><div class="title">${placeName(p)}</div>${altNames(p) && html`<div class="sub">${altNames(p)}</div>`}
            <div class="meta chips">${isForeignLandmark(p) && html`<${Chip} kind="star">★ 대표 명소</${Chip}>`}${p.cat.slice(0, 2).map((c) => html`<${Chip}>${catName(c)}</${Chip}>`)}${p.hrs == null && html`<${Chip} kind="warn">⚠ 영업시간</${Chip}>`}${p.ver === false && html`<${Chip} kind="x">◌ 검증 안 됨</${Chip}>`}${p.tier === 1 && html`<${Chip} kind="est">1등급</${Chip}>`}</div></div>
          <button class="btn secondary" style="min-width:44px;padding:4px 10px" aria-label="선택" onClick=${(e) => { e.stopPropagation(); onToggleSelect(p.id); }}>${selection.includes(p.id) ? "✓" : "+"}</button></div>`)}`}
    </div>
    <div class=${"map " + (mapOpen ? "" : "collapsed")} ref=${mapEl}></div>
  </div>`;
}
