// 제안 보내기 시트(서브 수립자, E7 4절 6항). 대상과 변경 내용을 보여 주고 메모를 받아 보낸다.
import { useState } from "../../lib.js";
import { html } from "./ui.js";
import { KIND_LABEL, MEMO_MAX } from "../../engines/e7/proposals.js";

const md = (d) => `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`;

export function ProposalSheet({ draft, dates = [], describe, onSubmit, onClose }) {
  const [memo, setMemo] = useState("");
  const [date, setDate] = useState(draft.value?.date || "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const withDate = draft.kind === "add"; // 추가 제안은 배치할 날짜를 함께 고를 수 있다
  const current = withDate ? { ...draft, value: { ...draft.value, date: date || undefined } } : draft;
  const needMemo = draft.kind === "memo";
  const send = async () => {
    setBusy(true); setErr(null);
    try { await onSubmit(current, memo); } catch (e) { setErr(e.message || String(e)); setBusy(false); }
  };
  return html`<div class="sheet proposal" role="dialog" aria-label="제안 보내기">
    <button class="close" aria-label="닫기" onClick=${onClose}>✕</button>
    <h2>제안 보내기 <span class="chip">${KIND_LABEL[draft.kind]}</span></h2>
    ${!needMemo && html`<p class="what">${describe({ ...current, memo })}</p>`}
    ${needMemo && draft.target?.name && html`<p class="what">${draft.target.name}에 대한 메모</p>`}
    ${withDate && dates.length > 0 && html`<div class="field"><label>배치할 날짜(선택)</label><select value=${date} onChange=${(e) => setDate(e.target.value)} style="min-height:40px"><option value="">정하지 않음</option>${dates.map((d, i) => html`<option value=${d}>${i + 1}일 ${md(d)}</option>`)}</select></div>`}
    <div class="field"><label>${needMemo ? "메모" : "덧붙일 말(선택)"}</label>
      <textarea rows="3" maxlength=${MEMO_MAX} value=${memo} placeholder=${needMemo ? "메인 수립자에게 전할 내용" : "제안하는 이유"} onInput=${(e) => setMemo(e.target.value)}></textarea></div>
    <p class="note">제안은 계획과 따로 저장됩니다. 메인 수립자가 승인해야 계획에 반영됩니다.</p>
    ${err && html`<p class="error" style="color:var(--err)">보내지 못했습니다: ${err}</p>`}
    <div class="row"><button class="btn" disabled=${busy || (needMemo && !memo.trim())} onClick=${send}>${busy ? "보내는 중…" : "제안 보내기"}</button><button class="btn secondary" onClick=${onClose}>취소</button></div>
  </div>`;
}
