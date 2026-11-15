// E7 제안(E7 4절 6항, R-23, D-034). 순수 모듈: 제안 레코드 만들기, 본문(plan)에 적용, 화면용 한 줄 설명.
// 제안은 본문과 따로 proposals/<시각>-<작성자>.json.enc에 저장된다. 승인 전에는 본문을 바꾸지 않는다.
import { dateList, toggleSelect, assignDay } from "../../state/plan.js";

export const PROPOSAL_DIR = "proposals";
export const KINDS = ["add", "remove", "move", "dwell", "memo"];
export const KIND_LABEL = { add: "추가", remove: "삭제", move: "이동", dwell: "체류 시간", memo: "메모" };
export const STATUS_LABEL = { pending: "대기", approved: "승인", rejected: "거절" };
export const MEMO_MAX = 500;
const DWELL_MIN = 15, DWELL_MAX = 600;

/** 시각(ISO)을 파일 이름용으로: 2026-11-15T02:35:00.123Z → 20261115T023500123Z */
const stamp = (iso) => iso.replace(/[-:.]/g, "");

export function proposalPath(id) { return `${PROPOSAL_DIR}/${id}.json.enc`; }

/** 제안의 형식 검사. 문제가 없으면 null, 있으면 사용자에게 보일 문구 */
export function validateProposal(p) {
  if (!p || !KINDS.includes(p.kind)) return "제안 종류를 알 수 없습니다.";
  const t = p.target || {}, v = p.value || {};
  if (p.kind !== "memo" && !t.placeId) return "대상 장소가 없습니다.";
  if (p.kind === "dwell" && !(Number.isFinite(v.minutes) && v.minutes >= DWELL_MIN && v.minutes <= DWELL_MAX)) return `체류 시간은 ${DWELL_MIN}~${DWELL_MAX}분이어야 합니다.`;
  if (p.kind === "memo" && !String(p.memo || "").trim()) return "메모 내용을 적으세요.";
  if (String(p.memo || "").length > MEMO_MAX) return `메모는 ${MEMO_MAX}자 이내여야 합니다.`;
  return null;
}

/**
 * 제안 레코드를 만든다. now(ISO 문자열)를 받아 결정적이다.
 * @param {{author: string, kind: string, target?: {placeId?: string, name?: string, date?: string}, value?: object, memo?: string, base?: string, now: string}} a
 */
export function makeProposal({ author, kind, target = {}, value = {}, memo = "", base = null, now }) {
  const p = { v: 1, id: `${stamp(now)}-${author}`, author, created: now, kind, target, value, memo: String(memo || "").trim(), status: "pending", decided: null, base };
  const err = validateProposal(p);
  if (err) throw new Error(err);
  return p;
}

/**
 * 제안을 본문에 적용한 새 plan을 돌려준다(입력은 바꾸지 않는다). 적용할 수 없으면 {ok: false, reason}.
 * add: 선택에 넣고 날짜가 있으면 그 날에 배치. remove: 선택과 배치에서 뺀다. move: 날짜를 옮긴다(null이면 미배치).
 * dwell: 체류 시간(분). memo: plan.notes에 메모를 남긴다.
 */
export function applyProposal(plan, p) {
  const err = validateProposal(p);
  if (err) return { ok: false, reason: err };
  const id = p.target?.placeId, selected = id ? plan.selection.includes(id) : false;
  const dates = dateList(plan.trip);
  const badDate = (d) => d != null && !dates.includes(d);
  if (p.kind === "add") {
    if (badDate(p.value?.date)) return { ok: false, reason: "제안한 날짜가 여행 기간 밖입니다." };
    if (selected && !p.value?.date) return { ok: false, reason: "이미 선택된 장소입니다." };
    let next = selected ? plan : toggleSelect(plan, id);
    if (p.target?.place && !next.custom?.[id] && String(id).startsWith("user:")) next = { ...next, custom: { ...next.custom, [id]: p.target.place } };
    if (p.value?.date) next = assignDay(next, id, p.value.date);
    return { ok: true, plan: next };
  }
  if (p.kind === "remove") {
    if (!selected) return { ok: false, reason: "선택되지 않은 장소입니다." };
    return { ok: true, plan: toggleSelect(plan, id) };
  }
  if (p.kind === "move") {
    if (!selected) return { ok: false, reason: "선택되지 않은 장소입니다." };
    if (badDate(p.value?.date)) return { ok: false, reason: "제안한 날짜가 여행 기간 밖입니다." };
    return { ok: true, plan: assignDay(plan, id, p.value?.date ?? null) };
  }
  if (p.kind === "dwell") {
    if (!selected) return { ok: false, reason: "선택되지 않은 장소입니다." };
    return { ok: true, plan: { ...plan, dwell: { ...(plan.dwell || {}), [id]: p.value.minutes } } };
  }
  const note = { id: p.id, placeId: id || null, date: p.target?.date || null, text: p.memo, by: p.author, at: p.created };
  return { ok: true, plan: { ...plan, notes: [...(plan.notes || []).filter((n) => n.id !== p.id), note] } };
}

/** 결정(승인·거절)을 적은 새 제안 레코드 */
export function decideProposal(p, status, by, now, note = "") {
  if (!["approved", "rejected"].includes(status)) throw new Error("결정은 승인 또는 거절이어야 합니다.");
  if (p.status !== "pending") throw new Error("이미 처리된 제안입니다.");
  return { ...p, status, decided: { by, at: now, note: String(note || "").trim() } };
}

const md = (d) => (d ? `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}` : "미배치");

/** 화면용 한 줄 설명. nameOf(placeId)는 장소 이름을 돌려준다(없으면 제안에 적힌 이름), dayOf(placeId)는 지금 배치된 날짜 */
export function describeProposal(p, nameOf = () => null, dayOf = () => null) {
  const id = p.target?.placeId;
  const name = (id && nameOf(id)) || p.target?.name || id || "";
  if (p.kind === "add") return `${name} 추가${p.value?.date ? ` (${md(p.value.date)})` : ""}`;
  if (p.kind === "remove") return `${name} 삭제`;
  if (p.kind === "move") { const from = p.value?.from ?? dayOf(id); return `${from ? md(from) + " " : ""}${name} → ${md(p.value?.date)} 이동`; }
  if (p.kind === "dwell") return `${name} 체류 ${p.value.minutes}분`;
  return `${name ? name + ": " : p.target?.date ? md(p.target.date) + ": " : ""}${p.memo}`;
}

/** 목록 정렬: 대기 먼저, 그 안에서는 최근 것이 위 */
export function sortProposals(list) {
  return [...list].sort((a, b) => (a.status === "pending" ? 0 : 1) - (b.status === "pending" ? 0 : 1) || String(b.created).localeCompare(String(a.created)));
}

/** 그 역할이 볼 제안: 메인은 전부, 서브는 자기 것만(와이어프레임 S7), 그 밖은 없음 */
export function visibleProposals(list, role, account) {
  if (role === "main") return list;
  if (role === "sub") { const a = String(account || "").toLowerCase(); return list.filter((p) => String(p.author || "").toLowerCase() === a); }
  return [];
}
