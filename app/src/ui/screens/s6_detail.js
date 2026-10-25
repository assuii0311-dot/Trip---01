// S6 장소 상세(겹침 시트). docs/04-wireframes.md S6, F-09
import { useEffect, useState } from "../../lib.js";
import { md5 } from "../../util/hash.js";
import { html, Chip } from "../components/ui.js";
import { placeName, altNames, isForeignLandmark, firstSentences } from "../../data/places.js";
import { gmapsCoord, gmapsName, CAT_ICON } from "../../util/format.js";
import { reservationHint, placeAlternatives } from "../../engines/e2.js";

const CV = { match: ["ok", "일치"], mismatch: ["warn", "불일치"], single: ["x", "단일 출처"], user: ["user", "사용자 추가"] };

export function S6Detail({ place: p, categories, loader, onClose, selected, onToggleSelect, cityPlaces = [], prof, reservation, onSetReservation, onOpenDetail }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let alive = true;
    (async () => {
      const wv = (p.desc || []).filter((d) => d.src === "wikivoyage");
      if (!wv.length) { setSrc({ none: true }); return; }
      const shard = await md5Prefix(p.id);
      const data = await loader.sourceShard(shard);
      const key = (d) => `${p.id}|${d.lang}|${d.page}|${d.idx}`;
      const en = wv.find((d) => d.lang === "en" && data[key(d)]);
      const es = wv.find((d) => d.lang === "es" && data[key(d)]);
      if (alive) setSrc({ en: en ? { text: data[key(en)], page: en.page } : null, es: es ? { text: data[key(es)], page: es.page } : null });
    })().catch(() => alive && setSrc({ none: true }));
    return () => { alive = false; };
  }, [p.id]);
  const catName = (id) => (categories.find((c) => c.id === id) || {}).ko || id;
  const name = placeName(p), alt = altNames(p);
  const [cvKind, cvLabel] = CV[p.cv] || CV.single;
  const wd = (p.desc || []).find((d) => d.src === "wikidata" && d.lang === "ko") || (p.desc || []).find((d) => d.src === "wikidata" && d.lang === "en");
  const hint = reservationHint(p);
  const alts = prof ? placeAlternatives(p, cityPlaces, prof.weights) : [];
  return html`<div class="sheet" role="dialog" aria-label=${name}>
    <button class="close" aria-label="닫기" onClick=${onClose}>✕</button>
    <h2>${name}${p.n?.ko_src === "generated" && html` <span class="chip x">생성</span>`}</h2>
    ${alt && html`<div class="alt">${alt}</div>`}
    <div class="row" style="margin:8px 0">
      <a class="btn secondary" href=${gmapsCoord(p.lat, p.lon)} target="_blank" rel="noopener">📍 구글맵(좌표)</a>
      <a class="btn secondary" href=${gmapsName(p.n?.local || name)} target="_blank" rel="noopener">🔎 이름 검색</a>
    </div>
    <div class="chips">
      ${isForeignLandmark(p) && html`<${Chip} kind="star">★ 해외 대표 명소</${Chip}>`}
      ${p.cat.map((c) => html`<${Chip}>${CAT_ICON[c] || ""} ${catName(c)}</${Chip}>`)}
      ${p.her && p.her.length > 0 && html`<${Chip}>🏷 유산 지정</${Chip}>`}
      <${Chip} kind=${cvKind}>${cvLabel}</${Chip}>
      ${p.ver === false && html`<${Chip} kind="x">◌ 검증 안 됨</${Chip}>`}
    </div>
    <dl class="kv">
      <dt>영업시간</dt><dd>${p.hrs ? html`${p.hrs} <span class="chip warn">⚠ 참고값, 확인 필요</span>` : html`<span class="note">정보 없음 · 확인 필요</span>`}</dd>
      <dt>입장료·가격</dt><dd>${p.price ? html`${p.price.free ? "무료" : p.price.eur != null ? `€${p.price.eur}` : p.price.raw}${p.price.tier ? ` · ${p.price.tier}` : ""} <span class="note">(${p.price.src === "wikivoyage" ? "Wikivoyage 참고값" : "OSM"})</span>` : html`<span class="note">정보 없음</span>`}</dd>
      <dt>예약</dt><dd><span class=${"chip " + (hint.level === "none" ? "x" : "warn")}>🎫 ${hint.label}</span> <span class="note">${hint.reason}</span>
        ${onSetReservation && html`<div class="row" style="margin-top:4px"><span class="note">확정:</span><select value=${reservation || ""} onChange=${(e) => onSetReservation(e.target.value || null)}><option value="">미확정</option><option value="required">예약 필요</option><option value="recommended">예약 권장</option><option value="none">불필요</option></select></div>`}</dd>
      ${p.osm_tags?.cuisine && html`<dt>음식</dt><dd>${p.osm_tags.cuisine}</dd>`}
      <dt>좌표</dt><dd>${p.lat.toFixed(5)}, ${p.lon.toFixed(5)} <span class="note">(${p.cs}, 신뢰도 ${p.cc})</span></dd>
      ${p.pop && html`<dt>대표성</dt><dd>사이트링크 ${p.pop.sl}${p.pop.pv ? ` · 월 조회 en ${p.pop.pv.en.toLocaleString()} / es ${p.pop.pv.es.toLocaleString()}` : ""}</dd>`}
    </dl>
    <h3 style="font-size:17px;margin:12px 0 4px">설명 <span class="chip x">생성 전</span></h3>
    ${src == null ? html`<p class="note">출처를 읽는 중…</p>`
      : src.none ? html`<p class="note">${wd ? wd.text : "출처 텍스트 없음. 명칭과 분류만 있습니다."}</p>`
      : html`<p>${firstSentences(src.en?.text || src.es?.text, 2)}</p><p class="note">한국어 설명은 E5 생성 뒤 표시됩니다. 위는 ${src.en ? "영문" : "스페인어"} Wikivoyage 원문 앞부분입니다.</p>`}
    <div class="src">출처: ${(p.src?.wd ? ["Wikidata(CC0)"] : []).concat(p.src?.osm?.length ? ["© OpenStreetMap contributors(ODbL)"] : [], p.src?.wv?.length ? [`Wikivoyage(CC BY-SA 4.0)${src?.en ? ` · ${src.en.page}` : ""}`] : []).join(" · ")}
      ${p.links?.enwiki && html` · <a href=${"https://en.wikipedia.org/wiki/" + encodeURIComponent(p.links.enwiki)} target="_blank" rel="noopener">en.wikipedia</a>`}
      ${p.links?.kowiki && html` · <a href=${"https://ko.wikipedia.org/wiki/" + encodeURIComponent(p.links.kowiki)} target="_blank" rel="noopener">ko.wikipedia</a>`}
      ${p.links?.web && html` · <a href=${p.links.web} target="_blank" rel="noopener">웹사이트</a>`}</div>
    ${alts.length > 0 && html`<h3 style="font-size:17px;margin:12px 0 4px">대안 장소 <span class="note">같은 범주, 2km 안</span></h3>${alts.map((a) => html`<div class="row" style="padding:4px 0"><a href="#" style="flex:1" onClick=${(e) => { e.preventDefault(); onOpenDetail && onOpenDetail(a.p.id); }}>${CAT_ICON[a.p.cat[0]] || ""} ${placeName(a.p)}</a><span class="note">${Math.round(a.dist)}m · ${a.score.toFixed(2)}</span></div>`)}`}
    ${onToggleSelect && html`<div style="margin-top:16px"><button class="btn" onClick=${onToggleSelect}>${selected ? "선택 해제" : "+ 선택"}</button></div>`}
  </div>`;
}

/** 파이프라인과 같은 샤드 키: md5(id)의 앞 두 자리 */
export async function md5Prefix(s) { return md5(s).slice(0, 2); }
