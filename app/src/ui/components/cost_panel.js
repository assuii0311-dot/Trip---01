// 비용 패널(F-21, E6). 일정표 하단 시트
import { html, Chip } from "./ui.js";
import { fmtEurRange } from "../../util/format.js";

const LABEL = { entry: "입장료", meals: "식비", lodging: "숙박비", transit: "대중교통", taxi: "택시" };
const conf = (c) => (c === "computed" ? html`<${Chip} kind="ok">계산</${Chip}>` : c === "none" ? html`<${Chip} kind="x">입력 전</${Chip}>` : html`<${Chip} kind="est">추정</${Chip}>`);

export function CostPanel({ cost, onClose }) {
  if (!cost) return null;
  return html`<div class="sheet" role="dialog" aria-label="비용"><button class="close" aria-label="닫기" onClick=${onClose}>✕</button>
    <h2>예상 비용 <span class="note">${cost.people}명 · ${{ low: "저가", mid: "중가", high: "고가" }[cost.tier]}</span></h2>
    <p style="font-size:20px;font-weight:600">${fmtEurRange(cost.grand?.min, cost.grand?.max)} <span class="note">(요금표 입력 전 항목 제외)</span></p>
    <dl class="kv">${["entry", "meals", "lodging", "transit", "taxi"].map((k) => html`<dt>${LABEL[k]}</dt><dd>${cost.total[k] ? fmtEurRange(cost.total[k].min, cost.total[k].max) : html`<span class="note">—</span>`}</dd>`)}</dl>
    <h3 style="font-size:17px;margin:12px 0 4px">날짜별</h3>
    ${cost.days.map((d, i) => html`<div class="card" style="margin:0 0 8px"><div class="body"><div class="title">${i + 1}일 ${d.date}</div>
      <dl class="kv" style="margin:6px 0">
        <dt>입장료</dt><dd>${d.entry ? html`${fmtEurRange(d.entry.min, d.entry.max)} ${conf(d.entry.confidence)}` : "—"}</dd>
        <dt>식비</dt><dd>${fmtEurRange(d.meals.min, d.meals.max)} ${conf("estimate")}<div class="note">${d.meals.basis}</div></dd>
        <dt>대중교통</dt><dd>${d.transit ? html`${d.transit.min != null ? fmtEurRange(d.transit.min, d.transit.max) : "—"} ${conf(d.transit.confidence)}<div class="note">${d.transit.basis}</div>` : html`<span class="note">이용 없음</span>`}</dd>
        <dt>택시</dt><dd>${d.taxi ? html`${d.taxi.min != null ? fmtEurRange(d.taxi.min, d.taxi.max) : "—"} ${conf(d.taxi.confidence)}<div class="note">${d.taxi.basis}</div>` : html`<span class="note">이용 없음</span>`}</dd>
      </dl></div></div>`)}
    ${cost.notes.length > 0 && html`<p class="note">${cost.notes.join(" · ")}. 교통 요금표는 개발 시점 데이터 입력(D-021 ③).</p>`}
    <p class="note">숙박비는 도시별 Wikivoyage 가격 분포에 예산 수준·일수·객실 수(2인 1실)를 곱한 범위입니다. 입장료는 장소 값이 있으면 그 값, 없으면 전국 분포. 모두 참고값입니다.</p>
  </div>`;
}
