// S3 탐색·추천(흐름 3, F-06~F-08). 묶음 2는 "전체 후보"만. 추천 탭은 묶음 3(E2)에서 채운다.
import { useEffect, useMemo, useRef, useState } from "../../lib.js";
import { html, Chip, Empty } from "../components/ui.js";
import { createMap } from "../components/map.js";
import { filterPlaces, sortByProminence, placeName, altNames, isForeignLandmark } from "../../data/places.js";
import { CAT_ICON } from "../../util/format.js";

export function S3Explore({ trip, cities, categories, tier1, loader, selection, onToggleSelect, onOpenDetail, selectedId }) {
  const tripCities = trip.cities.length ? trip.cities : cities.filter((c) => c.stratum === "big").sort((a, b) => (b.pop || 0) - (a.pop || 0)).slice(0, 10).map((c) => c.id);
  const [cityId, setCityId] = useState(tripCities[0] || null);
  const [tab, setTab] = useState("all");
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
  const city = cities.find((c) => c.id === cityId);
  useEffect(() => {
    if (!mapEl.current || mapRef.current) return;
    mapRef.current = createMap(mapEl.current, { onSelect: (id) => onOpenDetail(id) });
  }, []);
  useEffect(() => {
    const m = mapRef.current; if (!m) return;
    m.setPlaces(shown, { selectedId, isLandmark: isForeignLandmark });
    if (city && !q && !cats.length) m.flyTo(city.lat, city.lon, 13); else if (shown.length) m.fitTo(shown);
  }, [shown, selectedId]);
  useEffect(() => { mapRef.current && setTimeout(() => mapRef.current.resize(), 50); }, [mapOpen]);
  const catName = (id) => (categories.find((c) => c.id === id) || {}).ko || id;
  return html`<div class="two">
    <div class="list">
      <div class="toolbar">
        <select value=${cityId || ""} onChange=${(e) => setCityId(e.target.value)}>${tripCities.map((id) => { const c = cities.find((x) => x.id === id); return html`<option value=${id}>${c ? c.n.ko || c.n.es : id}</option>`; })}</select>
        <div class="seg" style="flex:none"><button class=${tab === "rec" ? "on" : ""} onClick=${() => setTab("rec")}>추천</button><button class=${tab === "all" ? "on" : ""} onClick=${() => setTab("all")}>전체 후보</button></div>
      </div>
      ${tab === "rec" ? html`<${Empty}>추천과 세 수준의 대안은 묶음 3(E2 추천 엔진)에서 제공됩니다. 지금은 "전체 후보"에서 고를 수 있습니다.</${Empty}>` : html`
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
