// E7 역할 판정과 권한(E7 4절 2항, R-22, D-034). 순수 모듈.
// 역할 목록은 본문 안에 암호화되어 있다: roles = {main: "계정", sub: ["계정", ...]}

export const ROLE_LABEL = { main: "메인 수립자", sub: "서브 수립자", viewer: "공유자(열람)", local: "로컬(미연결)" };

/** GitHub 계정 이름 비교용: 앞뒤 공백과 @를 떼고 소문자로(GitHub 계정은 대소문자를 구분하지 않는다) */
export const normLogin = (s) => String(s || "").trim().replace(/^@/, "").toLowerCase();

/**
 * 역할 판정. 저장소에 연결하기 전이면 local(기기 안에서 자유롭게 편집).
 * 토큰이 없거나 계정을 확인하지 못하면 viewer. 계정이 역할 목록의 메인이면 main, 서브 목록에 있으면 sub, 어디에도 없으면 viewer.
 * 역할 목록의 메인이 비어 있으면 토큰을 가진 계정이 main이다.
 */
export function resolveRole({ connected, hasToken, account, roles }) {
  if (!connected) return "local";
  const a = normLogin(account);
  if (!hasToken || !a || !roles) return "viewer";
  if (!normLogin(roles.main)) return "main"; // 메인이 비어 있는 예전 저장소(초기화 때 계정 확인 실패): 토큰을 가진 계정을 메인으로 본다. 다음 저장 때 기록된다
  if (normLogin(roles.main) === a) return "main";
  if ((roles.sub || []).some((s) => normLogin(s) === a)) return "sub";
  return "viewer";
}

const CAN = {
  local: ["edit"],
  main: ["edit", "save", "decide", "manageRoles", "viewProposals"],
  sub: ["propose", "viewProposals"],
  viewer: [],
};
/** 역할이 그 동작을 할 수 있는가. 동작: edit(본문 편집), save, propose(제안 작성), decide(승인·거절), manageRoles, viewProposals */
export const can = (role, action) => (CAN[role] || []).includes(action);

/** 서브 계정 목록을 정리한다: 공백·@ 제거, 빈 값·중복·메인 계정 제외. 적은 순서를 지킨다 */
export function cleanSubs(main, logins) {
  const seen = new Set([normLogin(main)]);
  const out = [];
  for (const raw of logins || []) {
    const name = String(raw || "").trim().replace(/^@/, "");
    const key = normLogin(name);
    if (!key || seen.has(key)) continue;
    seen.add(key); out.push(name);
  }
  return out;
}

/** GitHub 계정 이름 형식(영문·숫자·하이픈, 39자 이내, 하이픈으로 시작·끝나지 않음) */
export const isLogin = (s) => /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/.test(String(s || "").trim().replace(/^@/, ""));
