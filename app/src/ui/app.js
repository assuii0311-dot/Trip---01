// 앱 틀: 상단 바, 하단 탭 5개, 화면 전환, 여행 데이터(plan) 상태와 E7 동기화. docs/03-screen-flow.md
import { useEffect, useRef, useState } from "../lib.js";
import { html, Empty } from "./components/ui.js";
import { S1Input } from "./screens/s1_input.js";
import { S2Summary } from "./screens/s2_summary.js";
import { S3Explore } from "./screens/s3_explore.js";
import { S4Arrange } from "./screens/s4_arrange.js";
import { S5Itinerary } from "./screens/s5_itinerary.js";
import { generate, toMin, toHHMM } from "../engines/e4.js";
import { makeIntraIndex, makeTransitIndex, cityLeg, intercityLeg } from "../engines/e3.js";
import { dateList } from "../state/plan.js";
import { S6Detail } from "./screens/s6_detail.js";
import { S7Share } from "./screens/s7_share.js";
import { S8Settings } from "./screens/s8_settings.js";
import { ProposalSheet } from "./components/proposal_sheet.js";
import { CostPanel } from "./components/cost_panel.js";
import { estimateCost } from "../engines/e6.js";
import { profile, cityNights } from "../engines/e2.js";
import { tripDays } from "../state/store.js";
import { loadPlan, savePlan, toggleSelect as planToggle, assignDay, moveInDay, addCustomPlace, setLodging, itineraryDrift } from "../state/plan.js";
import { defaultNav, applyNav, navToHash, hashToNav, screenKey, sanitizeNav, saveNav, loadNav } from "../state/nav.js";
import { makeGitHub } from "../engines/e7/github.js";
import { makeSync, parseRepo } from "../engines/e7/sync.js";
import { validateKey } from "../engines/e7/crypto.js";
import { resolveRole, can, cleanSubs, ROLE_LABEL } from "../engines/e7/roles.js";
import { makeProposal, applyProposal, describeProposal } from "../engines/e7/proposals.js";
import { placeName } from "../data/places.js";
import { memberIds, makeDestOf, destName } from "../data/dest.js";

const TABS = [["input", "입력", "📝"], ["explore", "탐색", "🧭"], ["plan", "일정", "📅"], ["share", "공유", "🤝"], ["settings", "설정", "⚙️"]];
const CFG_KEY = "trip01.sync.v1";
const SYNCMETA_KEY = "trip01.syncmeta.v1"; // 마지막으로 읽은 버전, 저장 안 된 변경 여부, meta.json(암호화 매개값)
const MINE_KEY = "trip01.plan.mine.v1"; // 충돌 때 보존한 내 변경
const DAY_CAPACITY = 4; // E4 (e) 하루 수용 3~4곳
const AUTOSAVE_MS = 120000; // E7 (g) 유휴 2분

export function App({ data, loader }) {
  const [plan, setPlanState] = useState(() => loadPlan(localStorage));
  // 화면 위치와 보기 상태(D-036): 탭을 옮기거나 새로 고쳐도 보던 자리를 잃지 않게 한곳에 두고, 주소(#...)와 기기에 적는다
  const [nav, setNavState] = useState(() => {
    const cityIds = plan.trip.cities || [];
    const saved = sanitizeNav(loadNav(localStorage), { cityIds });
    const fromHash = hashToNav(location.hash);
    return sanitizeNav(fromHash ? applyNav(saved, { ...fromHash, detail: null }) : saved, { cityIds });
  });
  const navRef = useRef(nav); navRef.current = nav;
  const scrollMem = useRef({}).current; // 화면별 목록 위치
  const scrollNow = () => { const m = document.querySelector(".main"), l = document.querySelector(".two .list"); return { main: m ? m.scrollTop : 0, list: l ? l.scrollTop : 0 }; };
  /** 화면을 옮기거나 보기 상태를 바꾼다. 화면(주소)이 달라질 때만 방문 기록에 남긴다 */
  const go = (patch, { replace = false } = {}) => {
    const cur = navRef.current, next = applyNav(cur, patch);
    if (screenKey(next) !== screenKey(cur)) scrollMem[screenKey(cur)] = scrollNow();
    navRef.current = next; setNavState(next); saveNav(localStorage, next);
    const h = navToHash(next);
    if (h !== location.hash) { try { history[replace ? "replaceState" : "pushState"](null, "", location.pathname + location.search + h); } catch {} }
  };
  const tab = nav.tab, detailId = nav.detail, exploreTab = nav.exploreTab, planTab = nav.planTab;
  const setTab = (k) => go({ tab: k, detail: null });
  const setDetailId = (id) => go({ detail: id });
  const setExploreTab = (k) => go({ exploreTab: k });
  const setPlanTab = (k) => go({ planTab: k });
  const [genBusy, setGenBusy] = useState(false);
  const [costOpen, setCostOpen] = useState(false);
  const travelCache = useRef(new Map()).current;
  const muniCache = useRef(new Map()).current; // 지자체별 이동·대중교통 파일(섬 여행지는 여러 지자체 파일을 합쳐 쓴다)
  const [cfg, setCfgState] = useState(() => { try { return JSON.parse(localStorage.getItem(CFG_KEY) || "{}"); } catch { return {}; } });
  const [sync, setSyncState] = useState({ connected: false, dirty: false });
  const [conflict, setConflict] = useState(null);
  const [proposals, setProposals] = useState({ list: [], loaded: false, unreadable: 0 }); // 제안 목록(메인·서브)
  const [proposalDraft, setProposalDraft] = useState(null); // 서브가 보내려는 제안 {kind, target, value}
  const [notice, setNotice] = useState(null); // 화면 아래 알림
  const [hasMine, setHasMine] = useState(() => { try { return !!localStorage.getItem(MINE_KEY); } catch { return false; } });
  const syncRef = useRef(sync); syncRef.current = sync;
  const planRef = useRef(plan); planRef.current = plan;
  const cfgRef = useRef(cfg); cfgRef.current = cfg;
  const propCache = useRef(null); const accountCache = useRef({});
  const gh = useRef(makeGitHub()).current; const syncer = useRef(makeSync(gh)).current;
  // 역할(E7 4절 2항): 토큰의 계정을 본문의 역할 목록과 대조한다. 연결 전에는 기기 안에서 자유롭게 편집한다
  const role = resolveRole({ connected: sync.connected, hasToken: !!cfg.token, account: sync.account, roles: sync.roles });
  const roleRef = useRef(role); roleRef.current = role;
  const canEdit = can(role, "edit");
  const deny = () => setNotice(roleRef.current === "sub" ? "서브 수립자는 계획을 직접 바꿀 수 없습니다. 장소의 선택·날짜·체류 시간·메모는 제안으로 보낼 수 있습니다." : "공유자는 열람만 할 수 있습니다.");

  const setCfg = (c) => { cfgRef.current = c; setCfgState(c); try { localStorage.setItem(CFG_KEY, JSON.stringify(c)); } catch {} };
  const setPlan = (next) => {
    if (!can(roleRef.current, "edit")) { deny(); return; } // 역할에 없는 편집은 반영하지 않는다(R-22)
    const p = typeof next === "function" ? next(planRef.current) : next; setPlanState(p); savePlan(localStorage, p); if (syncRef.current.connected) setSyncState((s) => ({ ...s, dirty: true }));
  };
  const setTrip = (t) => setPlan((p) => ({ ...p, trip: t }));
  // 서브 수립자의 편집 동작은 제안으로 바뀐다(와이어프레임 S4, E7 4절 6항)
  const placeTarget = (id) => { const pl = getPlace(id); return { placeId: id, name: pl ? placeName(pl) : id, ...(String(id).startsWith("user:") && pl ? { place: pl } : {}) }; };
  const dayOfPlace = (id) => Object.keys(planRef.current.days).find((d) => (planRef.current.days[d] || []).includes(id)) || null;
  const propose = (kind, target = {}, value = {}) => { setNotice(null); setProposalDraft({ kind, target, value }); };
  const toggleSelect = (id) => { if (roleRef.current === "sub") return propose(planRef.current.selection.includes(id) ? "remove" : "add", placeTarget(id)); setPlan((p) => planToggle(p, id)); };
  const assignPlace = (id, d) => { if (roleRef.current === "sub") return propose("move", placeTarget(id), { date: d || null, from: dayOfPlace(id) }); setPlan((p) => assignDay(p, id, d)); };
  const setDwell = (id, v) => { if (roleRef.current === "sub") return propose("dwell", placeTarget(id), { minutes: Number(v) }); setPlan((pl) => ({ ...pl, dwell: { ...(pl.dwell || {}), [id]: v } })); };
  const byId = new Map(data.tier1.map((p) => [p.id, p]));
  const getPlace = (id) => byId.get(id) || data.tier2cache.get(id) || plan.custom[id];
  const getPlaceRef = useRef(getPlace); getPlaceRef.current = getPlace;
  const prof = profile(plan.trip, data.categories, DAY_CAPACITY);
  const nightsTotal = Math.max(0, tripDays(plan.trip) - 1);
  const recCounts = Object.fromEntries(plan.trip.cities.map((id) => [id, (data.cities.find((c) => c.id === id)?.places?.tier1) || 1]));
  const nights = cityNights(recCounts, nightsTotal, DAY_CAPACITY);
  const detail = detailId ? getPlace(detailId) : null;
  const openDetail = (id) => setDetailId(id);
  const cityById = (id) => data.cities.find((c) => c.id === id);
  const loaderWithCache = { ...loader, tier2: async (c) => { const ids = memberIds(cityById(c)).filter((m) => (cityById(m)?.places?.tier2 ?? 1) > 0); /* 2등급이 없는 지자체는 파일도 없다 */ const rows = (await Promise.all(ids.map((m) => loader.tier2(m)))).flat(); rows.forEach((p) => data.tier2cache.set(p.id, p)); return rows; } };
  const cityPlacesOf = (cityId) => data.tier1.filter((p) => p.city === cityId);

  // --- E3·E4: 일정 생성 ---
  async function muniTravel(mid, withTransit) {
    if (!muniCache.has(mid)) {
      const [tr, tz] = await Promise.all([loader.load(`travel/${mid}.json.gz`).catch(() => null), withTransit ? loader.load(`transit/${mid}.json.gz`).catch(() => null) : null]);
      muniCache.set(mid, { intra: tr ? makeIntraIndex(tr) : null, tidx: tz ? makeTransitIndex(tz) : null });
    }
    return muniCache.get(mid);
  }
  // 여행지(도시 또는 섬)의 이동 시간 함수. muniIds: 그 여행지에서 장소가 있는 지자체(섬이면 여러 곳)
  async function travelFor(destId, muniIds = null) {
    const dest = cityById(destId); const island = dest?.kind === "island";
    const ids = island ? (muniIds || []).filter((m) => dest.members.includes(m)) : [destId];
    // 대중교통 파일은 피드가 있는 지자체만 시도한다(섬은 소속 지자체의 피드 목록 기준)
    const parts = await Promise.all(ids.map((m) => muniTravel(m, !island || (cityById(m)?.transit_feeds || []).length > 0)));
    const inter = await loader.load("travel/intercity.json.gz").catch(() => null);
    const intra = parts.some((x) => x.intra) ? { lookup: (a, b) => { for (const x of parts) { const r = x.intra && x.intra.lookup(a, b); if (r) return r; } return null; } } : null;
    const t = { intra, tidx: (parts.find((x) => x.tidx) || {}).tidx || null, taxi: dest?.taxi_fare || null, inter };
    travelCache.set(destId, t);
    return (a, b) => { const leg = cityLeg(a, b, t); return { ...leg.best, alternatives: leg.alternatives }; };
  }
  function buildDays(plan0) {
    const dates = dateList(plan0.trip); const out = []; let k = 0;
    const cityOrder = plan0.trip.cities; if (!dates.length || !cityOrder.length) return out;
    const nightsOf = (cid) => Number(plan0.lodging[cid]?.nights ?? nights[cid] ?? 1);
    let ci = 0, left = nightsOf(cityOrder[0]);
    for (let i = 0; i < dates.length; i++) {
      const cid = cityOrder[Math.min(ci, cityOrder.length - 1)]; const c = data.cities.find((x) => x.id === cid); const l = plan0.lodging[cid] || {};
      const origin = l.zoneLat ? { lat: l.zoneLat, lon: l.zoneLon, name: l.zoneName } : { lat: c?.lat, lon: c?.lon, name: c ? destName(c) : cid };
      const d = { date: dates[i], cityId: cid, origin };
      if (i === 0 && plan0.trip.timeIn) { d.edge = "arrive"; d.arriveAt = toHHMM(toMin(plan0.trip.timeIn) + 60); }  // 입국 절차 60분(추정)
      if (i === dates.length - 1 && plan0.trip.timeOut) { d.edge = "depart"; d.departAt = plan0.trip.timeOut; d.departMode = "flight"; }
      if (i > 0 && out[i - 1].cityId !== cid) d.intercityFrom = out[i - 1].cityId;
      out.push(d); left--; if (left <= 0 && ci < cityOrder.length - 1) { ci++; left = nightsOf(cityOrder[ci]); }
    }
    return out;
  }
  async function runGenerate(onlyDate = null) {
    if (!can(roleRef.current, "edit")) { deny(); return; }
    setGenBusy(true);
    try {
      const plan0 = planRef.current; const days = buildDays(plan0);
      const all = new Map(); const byCity = { __all: all };
      const destOf = makeDestOf(data.cities, plan0.trip.cities); // 장소의 지자체 → 여행지(섬 포함)
      for (const id of plan0.selection) { const p = getPlace(id); if (!p) continue; all.set(id, p); (byCity[destOf(p) || p.city || days[0]?.cityId] ||= []).push(p); }
      const travelFns = {}; for (const cid of new Set(days.map((d) => d.cityId))) travelFns[cid] = await travelFor(cid, [...new Set((byCity[cid] || []).map((p) => p.city).filter(Boolean))]);
      const prev = plan0.itinerary;
      const assigned = { ...plan0.days };
      for (const [id, locked] of Object.entries(plan0.locks || {})) if (locked && prev) { const d = prev.days.find((dd) => dd.items.some((it) => it.id === id)); if (d) assigned[d.date] = [...(assigned[d.date] || []).filter((x) => x !== id), id]; }
      days.forEach((d) => { if (prev && onlyDate && d.date !== onlyDate) { const pd = prev.days.find((x) => x.date === d.date); if (pd) { d.lockedOrder = pd.items.filter((it) => it.kind === "place").map((it) => it.id); assigned[d.date] = d.lockedOrder; } } });
      const r = generate({ days, placesByCity: byCity, assigned, dwellOverrides: plan0.dwell || {}, fixed: plan0.fixed || {}, travelFor: (cid) => travelFns[cid], meals: plan0.trip.meals, dayStart: plan0.trip.dayStart || "09:00", dayEnd: plan0.trip.dayEnd || "22:00" });
      const inter = travelCache.get(days[0]?.cityId)?.inter;
      r.days.forEach((d, i) => { const src = days[i].intercityFrom; if (src && inter) { const a = data.cities.find((c) => c.id === src), b = data.cities.find((c) => c.id === d.cityId); if (a && b) d.intercity = { from: src, to: d.cityId, leg: intercityLeg(a, b, inter) }; } });
      setPlan((pl) => ({ ...pl, itinerary: { ...r, generated: new Date().toISOString() } }));
      go({ tab: "plan", planTab: "itinerary" });
    } catch (e) { alert("일정 생성 실패: " + (e.message || e)); } finally { setGenBusy(false); }
  }

  // --- E7: 여행 저장소 연결, 읽기·쓰기, 역할, 제안(E7 설계 4절) ---
  const repoOf = () => { const r = parseRepo(cfgRef.current.repo); if (!r) throw new Error("저장소 주소를 확인하세요."); return r; };
  const readMeta = () => { try { return JSON.parse(localStorage.getItem(SYNCMETA_KEY) || "null"); } catch { return null; } };
  /** 토큰의 GitHub 계정(호출 1회, 토큰이 같으면 다시 묻지 않는다). 확인하지 못하면 null */
  const whoAmI = async () => {
    const token = cfgRef.current.token; if (!token) return null;
    if (accountCache.current.token === token) return accountCache.current.login;
    try { const login = (await gh.user(token)).data.login; accountCache.current = { token, login }; return login; } catch { return null; }
  };
  const onCheck = async () => { const { owner, repo } = repoOf(); const r = await gh.repo(owner, repo, cfgRef.current.token || undefined); setSyncState((s) => ({ ...s, rate: r.rate })); return `연결됨: ${owner}/${repo} (기본 브랜치 ${r.data.default_branch}, ${r.data.private ? "비공개" : "공개"})`; };
  const onInit = async () => {
    const { owner, repo } = repoOf(); const c = cfgRef.current;
    const account = await whoAmI();
    if (!account) throw new Error("토큰으로 GitHub 계정을 확인하지 못했습니다. 토큰을 확인하세요.");
    const r = await syncer.init({ owner, repo, token: c.token, passphrase: c.key, account });
    const body = { ...r.body, plan: planRef.current, applied: [] };
    const s = await syncer.save({ owner, repo, token: c.token, key: r.key, body, baseCommit: r.commit, fileSha: r.sha, message: "저장: 초기 계획" });
    propCache.current = null; setProposals({ list: [], loaded: true, unreadable: 0 });
    setSyncState({ connected: true, dirty: false, key: r.key, meta: r.meta, commit: s.commit, sha: s.sha, date: new Date().toISOString(), account, roles: body.roles, applied: [], stale: false });
    return "초기화와 첫 저장 완료";
  };
  /** 제안 목록 새로 읽기(메인·서브). 디렉터리 1회 + 바뀐 파일만큼 호출한다 */
  const refreshProposals = async (st = syncRef.current, r0 = roleRef.current) => {
    if (!st.connected || !can(r0, "viewProposals")) { setProposals({ list: [], loaded: false, unreadable: 0 }); return "제안은 메인·서브 수립자만 볼 수 있습니다."; }
    const { owner, repo } = repoOf();
    const r = await syncer.listProposals({ owner, repo, token: cfgRef.current.token, key: st.key, known: propCache.current });
    propCache.current = r.cache; setProposals({ list: r.proposals, loaded: true, unreadable: r.unreadable });
    return `제안 ${r.proposals.length}건`;
  };
  /** 읽기(4절 3항). keepDraft: 저장 안 된 내 변경이 기기에 있으면 본문을 덮어쓰지 않고 기준 버전만 맞춘다 */
  const onLoad = async ({ keepDraft = null } = {}) => {
    const { owner, repo } = repoOf(); const c = cfgRef.current; const s0 = syncRef.current;
    const args = { owner, repo, token: c.token || undefined, passphrase: c.key, cachedKey: s0.key, cachedMeta: s0.meta || readMeta()?.meta };
    let r;
    try { r = await syncer.load(args); }
    catch (e) { if (!args.cachedMeta || !/복호화 실패/.test(e.message || "")) throw e; r = await syncer.load({ ...args, cachedKey: undefined, cachedMeta: undefined }); } // 저장소를 다시 초기화했으면 meta가 바뀐다
    const account = await whoAmI();
    const roles = r.body.roles || { main: null, sub: [] };
    const next = { connected: true, dirty: false, key: r.key, meta: r.meta, commit: r.commit, sha: r.sha, date: r.date, etag: r.etag, account, roles, applied: r.body.applied || [], stale: false };
    const nextRole = resolveRole({ connected: true, hasToken: !!c.token, account, roles });
    if (keepDraft && can(nextRole, "edit")) { next.dirty = true; if (keepDraft.commit !== r.commit) { next.commit = keepDraft.commit; next.stale = true; } }
    else if (r.body.plan) { setPlanState(r.body.plan); savePlan(localStorage, r.body.plan); }
    setSyncState(next);
    propCache.current = null;
    if (can(nextRole, "viewProposals")) refreshProposals(next, nextRole).catch(() => {});
    else setProposals({ list: [], loaded: false, unreadable: 0 });
    return `불러옴: ${r.commit.slice(0, 7)} · ${ROLE_LABEL[nextRole]}${c.token && !account ? " (토큰으로 계정을 확인하지 못했습니다)" : ""}${next.dirty ? " · 저장 안 된 내 변경 유지" : ""}`;
  };
  /** 쓰기(4절 4~5항, 메인만). opts.plan을 주면 저장에 성공한 뒤에만 기기의 계획을 바꾼다(승인 반영) */
  const doSave = async (force = false, opts = {}) => {
    if (!can(roleRef.current, "save")) throw new Error("저장은 메인 수립자만 할 수 있습니다.");
    const { owner, repo } = repoOf(); const c = cfgRef.current; const s0 = syncRef.current;
    const roles = opts.roles || { main: s0.roles?.main || s0.account || null, sub: s0.roles?.sub || [] };
    const applied = opts.applied || s0.applied || [];
    const body = { roles, plan: opts.plan || planRef.current, applied };
    const r = await syncer.save({ owner, repo, token: c.token, key: s0.key, body, baseCommit: force ? null : s0.commit, fileSha: force ? (await gh.getFile(owner, repo, "trip.json.enc", { token: c.token })).sha : s0.sha, message: opts.message || "저장" });
    if (r.conflict) { setConflict({ latest: r.latest, date: r.date }); throw new Error("다른 기기에서 먼저 저장했습니다. 처리 방법을 고르세요."); }
    if (opts.plan) { setPlanState(opts.plan); savePlan(localStorage, opts.plan); }
    setSyncState((s) => ({ ...s, dirty: false, commit: r.commit, sha: r.sha, date: new Date().toISOString(), stale: false, roles, applied }));
    return `저장됨: ${r.commit.slice(0, 7)}`;
  };
  const onSave = () => doSave(false);
  const onDisconnect = () => { setSyncState({ connected: false, dirty: false }); setProposals({ list: [], loaded: false, unreadable: 0 }); propCache.current = null; try { localStorage.removeItem(SYNCMETA_KEY); } catch {} };
  /** 서브 계정 목록 바꾸기(메인). 본문에 암호화되어 저장된다 */
  const onSetSubs = async (logins) => { const s0 = syncRef.current; const main = s0.roles?.main || s0.account; return doSave(false, { roles: { main, sub: cleanSubs(main, logins) }, message: "저장: 역할 변경" }); };
  /** 제안 보내기(서브). 본문 파일은 건드리지 않는다 */
  const submitProposal = async (draft, memo) => {
    if (!can(roleRef.current, "propose")) throw new Error("제안은 서브 수립자만 보낼 수 있습니다.");
    const { owner, repo } = repoOf(); const s0 = syncRef.current;
    const proposal = makeProposal({ author: s0.account, kind: draft.kind, target: draft.target, value: draft.value, memo, base: s0.commit, now: new Date().toISOString() });
    await syncer.createProposal({ owner, repo, token: cfgRef.current.token, key: s0.key, proposal });
    setProposalDraft(null); setNotice("제안을 보냈습니다. 메인 수립자가 승인하면 계획에 반영됩니다.");
    refreshProposals().catch(() => {});
  };
  /** 승인·거절(메인). 승인은 본문에 반영한 커밋 → 제안 상태 커밋 순서다. 이미 반영된 제안은 상태만 바꾼다 */
  const onDecide = async (p, status, note = "") => {
    if (!can(roleRef.current, "decide")) throw new Error("승인·거절은 메인 수립자만 할 수 있습니다.");
    const { owner, repo } = repoOf(); const s0 = syncRef.current;
    if (status === "approved" && !(s0.applied || []).includes(p.id)) {
      const r = applyProposal(planRef.current, p);
      if (!r.ok) throw new Error(`계획에 반영할 수 없습니다: ${r.reason}`);
      await doSave(false, { plan: r.plan, applied: [...(s0.applied || []), p.id], message: `승인 반영: ${p.id}` });
    }
    const d = await syncer.decide({ owner, repo, token: cfgRef.current.token, key: s0.key, proposal: p, status, by: s0.account, note });
    await refreshProposals().catch(() => {});
    if (d.conflict) throw new Error("다른 기기에서 이미 처리한 제안입니다. 목록을 새로 읽었습니다.");
    return status === "approved" ? "승인해 계획에 반영했습니다. 일정표는 다시 생성하면 바뀝니다." : "거절했습니다.";
  };
  const onRestoreMine = () => { try { const mine = JSON.parse(localStorage.getItem(MINE_KEY) || "null"); if (!mine) return; setPlan(mine); if (can(roleRef.current, "edit")) { localStorage.removeItem(MINE_KEY); setHasMine(false); setNotice("보존한 내 변경을 다시 적용했습니다. 저장하면 저장소에 반영됩니다."); } } catch {} };
  const onDropMine = () => { try { localStorage.removeItem(MINE_KEY); } catch {} setHasMine(false); };
  // 마지막으로 읽은 버전과 저장 안 된 변경 여부를 기기에 적어 둔다(다음에 열 때 내 변경을 덮어쓰지 않기 위해)
  useEffect(() => { if (!sync.connected) return; try { localStorage.setItem(SYNCMETA_KEY, JSON.stringify({ commit: sync.commit, dirty: !!sync.dirty, meta: sync.meta })); } catch {} }, [sync.connected, sync.commit, sync.dirty]);
  // 앱을 열 때(4절 3항, R-21): 공유 링크의 ?repo=를 읽고, 저장소와 Key가 있으면 최신 계획을 읽는다
  useEffect(() => {
    let c = cfgRef.current;
    try {
      const q = new URLSearchParams(location.search).get("repo");
      if (q && parseRepo(q) && q !== c.repo) { c = { repo: q }; setCfg(c); try { localStorage.removeItem(SYNCMETA_KEY); } catch {} } // 다른 여행의 Key·토큰은 쓰지 않는다
    } catch {}
    if (!parseRepo(c.repo)) return;
    if (!c.key || validateKey(c.key)) { go({ tab: "settings", detail: null }, { replace: true }); setNotice("공유받은 여행입니다. Key를 입력하고 불러오기를 누르세요."); return; }
    const m = readMeta();
    onLoad({ keepDraft: m && m.dirty ? m : null }).then((msg) => setNotice(msg)).catch((e) => setNotice(`여행 저장소를 읽지 못했습니다: ${e.message || e}`));
  }, []);
  // 자동 저장(유휴 2분, 메인)과 화면 복귀 시 최신 확인
  useEffect(() => {
    if (!sync.connected || !sync.dirty || role !== "main") return;
    const t = setTimeout(() => { doSave(false).catch(() => {}); }, AUTOSAVE_MS);
    return () => clearTimeout(t);
  }, [sync.dirty, sync.connected, plan, role]);
  useEffect(() => {
    const onVis = async () => {
      if (document.visibilityState !== "visible" || !syncRef.current.connected) return;
      try {
        const { owner, repo } = repoOf(); const l = await gh.latestCommit(owner, repo, "trip.json.enc", cfgRef.current.token || undefined);
        if (l.sha && l.sha !== syncRef.current.commit) { if (syncRef.current.dirty) setSyncState((s) => ({ ...s, stale: true })); else await onLoad(); } // 내 변경이 없으면 바로 최신으로 바꾼다
        else if (can(roleRef.current, "viewProposals")) await refreshProposals();
      } catch {}
    };
    document.addEventListener("visibilitychange", onVis); return () => document.removeEventListener("visibilitychange", onVis);
  }, [cfg.repo, cfg.token]);
  useEffect(() => { if (!notice) return; const t = setTimeout(() => setNotice(null), 6000); return () => clearTimeout(t); }, [notice]);
  const pendingCount = proposals.list.filter((x) => x.status === "pending").length;

  // 뒤로 가기·앞으로 가기: 주소에 적힌 화면으로 간다(앱을 벗어나지 않는다)
  useEffect(() => {
    try { history.replaceState(null, "", location.pathname + location.search + navToHash(navRef.current)); } catch {}
    const onPop = () => {
      const p = hashToNav(location.hash); if (!p) return;
      const cur = navRef.current; scrollMem[screenKey(cur)] = scrollNow();
      const next = applyNav(cur, { detail: null, ...p, ...(p.detail && !getPlaceRef.current(p.detail) ? { detail: null } : {}) });
      navRef.current = next; setNavState(next); saveNav(localStorage, next);
    };
    window.addEventListener("popstate", onPop); return () => window.removeEventListener("popstate", onPop);
  }, []);
  // 화면이 바뀌면 그 화면에서 보던 목록 위치로 돌아간다(목록이 늦게 채워질 수 있어 몇 번 시도한다)
  const sk = screenKey(nav);
  useEffect(() => {
    const want = scrollMem[sk];
    const els = () => [document.querySelector(".main"), document.querySelector(".two .list")];
    if (!want || (!want.main && !want.list)) { const [m, l] = els(); if (m) m.scrollTop = 0; if (l) l.scrollTop = 0; return; } // 처음 온 화면은 맨 위에서 시작한다
    let stop = false; const cancel = () => { stop = true; };
    const apply = () => {
      if (stop) return;
      const [m, l] = els(); if (m && want.main) m.scrollTop = want.main; if (l && want.list) l.scrollTop = want.list;
      if ((!want.main || (m && Math.abs(m.scrollTop - want.main) < 2)) && (!want.list || (l && Math.abs(l.scrollTop - want.list) < 2))) stop = true; // 닿았으면 그만둔다
    };
    apply(); const timers = [120, 500, 1400].map((ms) => setTimeout(apply, ms));
    // 사용자가 직접 움직이기 시작하면 더는 되돌리지 않는다
    const evs = ["touchstart", "wheel", "keydown", "mousedown"]; evs.forEach((e) => window.addEventListener(e, cancel, { passive: true }));
    return () => { timers.forEach(clearTimeout); evs.forEach((e) => window.removeEventListener(e, cancel)); };
  }, [sk]);
  // 여행지가 바뀌어 보던 도시가 없어졌으면 비운다
  useEffect(() => { const c = navRef.current.explore.city; if (c && !plan.trip.cities.includes(c)) go({ explore: { city: null } }); }, [plan.trip.cities.join(",")]);
  const drift = itineraryDrift(plan);
  const tripLine = (() => {
    const t0 = plan.trip, days = tripDays(t0), md = (d) => `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`;
    const names = t0.cities.map((id) => { const c = cityById(id); return c ? destName(c) : id; });
    return { dates: t0.start && t0.end ? `${md(t0.start)}~${md(t0.end)} · ${days}일` : null, cities: names.length ? `${names[0]}${names.length > 1 ? ` 외 ${names.length - 1}곳` : ""}` : null, picks: plan.selection.length };
  })();
  const showTripbar = !!(tripLine.dates || tripLine.cities || tripLine.picks > 0);
  // 위쪽 줄(여행 요약, 하위 탭)의 높이를 알려 지도·목록 화면이 남은 높이를 정확히 쓰게 한다
  useEffect(() => { const el = document.getElementById("app"); if (el) el.style.setProperty("--bars-h", `${(showTripbar ? 40 : 0) + (tab === "explore" || tab === "plan" ? 48 : 0)}px`); }, [showTripbar, tab]);
  const SUBTABS = { explore: [["summary", "도시 요약"], ["explore", "장소 고르기"]], plan: [["arrange", "배치·숙박"], ["itinerary", "일정표"]] };
  const titles = { input: "입력", explore: exploreTab === "summary" ? "요약" : "탐색·추천", plan: planTab === "arrange" ? "선택·배치" : "일정표", share: "공유", settings: "설정" };
  return html`
    <header class="top"><h1>${titles[tab]}</h1>
      ${sync.connected ? html`<button class=${"chip " + (sync.dirty ? "warn" : sync.stale ? "warn" : "ok")} title="버전" onClick=${() => { setTab("settings"); }}>${sync.commit ? sync.commit.slice(0, 7) : "—"}${sync.dirty ? " · 저장 필요" : sync.stale ? " · 오래됨" : " · 최신"}${role === "sub" ? " · 서브" : role === "viewer" ? " · 열람" : ""}${role === "main" && pendingCount ? ` · 제안 ${pendingCount}` : ""}</button>` : html`<span class="version" title="데이터 갱신일">데이터 ${data.attribution.generated}</span>`}
    </header>
    ${showTripbar && html`<div class="tripbar" aria-label="지금 여행">
      ${tripLine.dates ? html`<button onClick=${() => go({ tab: "input", inputStep: 1, detail: null })} title="기간 바꾸기">📅 ${tripLine.dates}</button>` : html`<button onClick=${() => go({ tab: "input", inputStep: 1, detail: null })}>📅 기간 정하기</button>`}
      <button onClick=${() => go({ tab: "input", inputStep: 2, detail: null })} title="여행지 바꾸기">📍 ${tripLine.cities || "여행지 고르기"}</button>
      <button onClick=${() => go({ tab: "plan", planTab: "arrange", detail: null })} title="고른 장소 보기">✓ 고른 장소 ${tripLine.picks}곳</button>
    </div>`}
    ${SUBTABS[tab] && html`<div class="subtabs" role="tablist">${SUBTABS[tab].map(([k, label]) => { const on = (tab === "explore" ? exploreTab : planTab) === k; return html`<button role="tab" aria-selected=${on} class=${on ? "on" : ""} onClick=${() => (tab === "explore" ? setExploreTab(k) : setPlanTab(k))}>${label}${tab === "plan" && k === "itinerary" && (drift.missing.length + drift.removed.length) > 0 ? " •" : ""}</button>`; })}</div>`}
    <main class="main">
      ${tab === "input" && html`<${S1Input} trip=${plan.trip} setTrip=${setTrip} cities=${data.cities} airports=${data.airports} categories=${data.categories} regions=${data.regions || []} role=${canEdit ? "main" : "viewer"} ui=${{ step: nav.inputStep, ...nav.input }} setUi=${({ step, ...rest }) => go({ ...(step ? { inputStep: step } : {}), ...(Object.keys(rest).length ? { input: rest } : {}) })} onDone=${() => go({ tab: "explore", exploreTab: "summary", detail: null })} />`}
      ${tab === "explore" && exploreTab === "summary" && html`<${S2Summary} trip=${plan.trip} cities=${data.cities} categories=${data.categories} prof=${prof} selection=${plan.selection} getPlace=${getPlace} onReselect=${() => go({ tab: "input", inputStep: 4, detail: null })} onExplore=${(cid) => go({ exploreTab: "explore", explore: { city: cid } })} />`}
      ${tab === "explore" && exploreTab === "explore" && html`<${S3Explore} trip=${plan.trip} cities=${data.cities} categories=${data.categories} tier1=${data.tier1} loader=${loaderWithCache} selection=${plan.selection} onToggleSelect=${toggleSelect} onOpenDetail=${openDetail} selectedId=${detailId} prof=${prof} nights=${nights} ui=${nav.explore} setUi=${(patch) => go({ explore: patch })} role=${role} />`}
      ${tab === "plan" && planTab === "arrange" && html`<${S4Arrange} plan=${plan} cities=${data.cities} byId=${{ get: getPlace }} prof=${prof} nights=${nights} onAssign=${assignPlace} onMove=${(d, a, b) => setPlan((p) => moveInDay(p, d, a, b))} onSetLodging=${(cid, patch) => setPlan((p) => setLodging(p, cid, patch))} onAddCustom=${(c) => setPlan((p) => addCustomPlace(p, c))} onOpenDetail=${openDetail} onGenerate=${() => runGenerate()} role=${role} />`}
      ${tab === "plan" && planTab === "itinerary" && html`<${S5Itinerary} plan=${plan} result=${plan.itinerary} getPlace=${getPlace} cities=${data.cities} busy=${genBusy} onGenerate=${() => runGenerate()} onRegenerateDay=${(d) => runGenerate(d)} onSetDwell=${setDwell} onSetFixed=${(id, v) => setPlan((pl) => ({ ...pl, fixed: { ...(pl.fixed || {}), [id]: v } }))} onToggleLock=${(id) => setPlan((pl) => ({ ...pl, locks: { ...(pl.locks || {}), [id]: !(pl.locks || {})[id] } }))} onOpenDetail=${openDetail} onMoveToDay=${(id, d) => { assignPlace(id, d); if (canEdit) setTimeout(() => runGenerate(), 0); }} onCost=${() => setCostOpen(true)} role=${role} drift=${drift} />`}
    ${costOpen && plan.itinerary && html`<${CostPanel} cost=${estimateCost({ itinerary: plan.itinerary, getPlace, cityOf: cityById, trip: plan.trip, lodging: plan.lodging, faresByCity: Object.fromEntries([...travelCache.entries()].map(([k, v]) => [k, v.tidx?.fares || []])) })} onClose=${() => setCostOpen(false)} />`}
      ${tab === "share" && html`<${S7Share} plan=${plan} getPlace=${getPlace} cities=${data.cities} cfg=${cfg} onImport=${(p) => setPlan({ ...p })} role=${role} account=${sync.account} proposals=${proposals} onRefreshProposals=${() => refreshProposals()} onDecide=${onDecide} onProposeMemo=${() => propose("memo")} />`}
      ${tab === "settings" && html`<${S8Settings} data=${data} cfg=${cfg} setCfg=${setCfg} syncState=${{ ...sync, role }} onCheck=${onCheck} onInit=${onInit} onLoad=${() => onLoad()} onSave=${onSave} onDisconnect=${onDisconnect} onSetSubs=${onSetSubs} hasMine=${hasMine} onRestoreMine=${onRestoreMine} onDropMine=${onDropMine} />`}
    </main>
    ${detail && html`<${S6Detail} place=${detail} categories=${data.categories} loader=${loader} e5Index=${data.e5Index} onClose=${() => setDetailId(null)} selected=${plan.selection.includes(detail.id)} onToggleSelect=${role === "viewer" ? null : () => toggleSelect(detail.id)} cityPlaces=${cityPlacesOf(detail.city)} prof=${prof} reservation=${plan.reservations[detail.id]} onSetReservation=${canEdit ? (v) => setPlan((p) => ({ ...p, reservations: { ...p.reservations, [detail.id]: v } })) : null} onOpenDetail=${openDetail} role=${role} cityName=${((c) => (c ? c.n?.es || c.n?.local || c.n?.en || "" : ""))(cityById(detail.city))} notes=${(plan.notes || []).filter((n) => n.placeId === detail.id)} onProposeMemo=${role === "sub" ? () => propose("memo", placeTarget(detail.id)) : null} />`}
    ${conflict && html`<div class="sheet" role="dialog" aria-label="저장 충돌"><h2>저장 충돌</h2><p>다른 기기에서 먼저 저장했습니다${conflict.date ? ` (${new Date(conflict.date).toLocaleString("ko-KR")})` : ""}. 어떻게 할까요?</p>
      <div class="row"><button class="btn" onClick=${async () => { const mine = planRef.current; try { await onLoad(); localStorage.setItem(MINE_KEY, JSON.stringify(mine)); setHasMine(true); setNotice("최신 계획을 불러왔습니다. 내 변경은 설정 화면에서 다시 적용할 수 있습니다."); } catch {} setConflict(null); }}>최신 불러오기 (내 변경은 기기에 보존)</button>
      <button class="btn secondary" onClick=${async () => { if (confirm("정말 내 변경으로 덮어쓸까요? 상대의 변경이 사라집니다.")) { try { await doSave(true); } catch {} setConflict(null); } }}>덮어쓰기</button></div></div>`}
    ${proposalDraft && html`<${ProposalSheet} draft=${proposalDraft} dates=${dateList(plan.trip)} describe=${(d) => describeProposal({ ...d, memo: d.memo || "" }, (id) => { const pl = getPlace(id); return pl ? placeName(pl) : null; }, dayOfPlace)} onSubmit=${submitProposal} onClose=${() => setProposalDraft(null)} />`}
    ${notice && html`<div class="toast" role="status" onClick=${() => setNotice(null)}>${notice}</div>`}
    <nav class="tabs" aria-label="주 탐색">${TABS.map(([k, label, ico]) => html`<button class=${tab === k ? "on" : ""} onClick=${() => setTab(k)} aria-current=${tab === k ? "page" : undefined}><span class="ico" aria-hidden="true">${ico}</span>${label}</button>`)}</nav>`;
}
