// 앱 틀: 상단 바, 하단 탭 5개, 화면 전환, 여행 데이터(plan) 상태와 E7 동기화. docs/03-screen-flow.md
import { useEffect, useRef, useState } from "../lib.js";
import { html, Empty } from "./components/ui.js";
import { S1Input } from "./screens/s1_input.js";
import { S2Summary } from "./screens/s2_summary.js";
import { S3Explore } from "./screens/s3_explore.js";
import { S4Arrange } from "./screens/s4_arrange.js";
import { S6Detail } from "./screens/s6_detail.js";
import { S8Settings } from "./screens/s8_settings.js";
import { profile, cityNights } from "../engines/e2.js";
import { tripDays } from "../state/store.js";
import { loadPlan, savePlan, toggleSelect as planToggle, assignDay, moveInDay, addCustomPlace, setLodging } from "../state/plan.js";
import { makeGitHub } from "../engines/e7/github.js";
import { makeSync, parseRepo } from "../engines/e7/sync.js";

const TABS = [["input", "입력", "📝"], ["explore", "탐색", "🧭"], ["plan", "일정", "📅"], ["share", "공유", "🤝"], ["settings", "설정", "⚙️"]];
const CFG_KEY = "trip01.sync.v1";
const DAY_CAPACITY = 4; // E4 (e) 하루 수용 3~4곳
const AUTOSAVE_MS = 120000; // E7 (g) 유휴 2분

export function App({ data, loader }) {
  const [tab, setTab] = useState("input");
  const [plan, setPlanState] = useState(() => loadPlan(localStorage));
  const [detailId, setDetailId] = useState(null);
  const [exploreTab, setExploreTab] = useState("explore");
  const [exploreCity, setExploreCity] = useState(null);
  const [cfg, setCfgState] = useState(() => { try { return JSON.parse(localStorage.getItem(CFG_KEY) || "{}"); } catch { return {}; } });
  const [sync, setSyncState] = useState({ connected: false, dirty: false });
  const [conflict, setConflict] = useState(null);
  const syncRef = useRef(sync); syncRef.current = sync;
  const planRef = useRef(plan); planRef.current = plan;
  const gh = useRef(makeGitHub()).current; const syncer = useRef(makeSync(gh)).current;

  const setCfg = (c) => { setCfgState(c); try { localStorage.setItem(CFG_KEY, JSON.stringify(c)); } catch {} };
  const setPlan = (next) => { const p = typeof next === "function" ? next(planRef.current) : next; setPlanState(p); savePlan(localStorage, p); if (syncRef.current.connected) setSyncState((s) => ({ ...s, dirty: true })); };
  const setTrip = (t) => setPlan((p) => ({ ...p, trip: t }));
  const toggleSelect = (id) => setPlan((p) => planToggle(p, id));
  const byId = new Map(data.tier1.map((p) => [p.id, p]));
  const getPlace = (id) => byId.get(id) || data.tier2cache.get(id) || plan.custom[id];
  const prof = profile(plan.trip, data.categories, DAY_CAPACITY);
  const nightsTotal = Math.max(0, tripDays(plan.trip) - 1);
  const recCounts = Object.fromEntries(plan.trip.cities.map((id) => [id, (data.cities.find((c) => c.id === id)?.places?.tier1) || 1]));
  const nights = cityNights(recCounts, nightsTotal, DAY_CAPACITY);
  const role = cfg.token ? "메인 수립자" : sync.connected ? "공유자(열람)" : "로컬(미연결)";
  const detail = detailId ? getPlace(detailId) : null;
  const openDetail = (id) => setDetailId(id);
  const loaderWithCache = { ...loader, tier2: async (c) => { const rows = await loader.tier2(c); rows.forEach((p) => data.tier2cache.set(p.id, p)); return rows; } };
  const cityPlacesOf = (cityId) => data.tier1.filter((p) => p.city === cityId);

  // --- E7 ---
  const repoOf = () => { const r = parseRepo(cfg.repo); if (!r) throw new Error("저장소 주소를 확인하세요."); return r; };
  const onCheck = async () => { const { owner, repo } = repoOf(); const r = await gh.repo(owner, repo, cfg.token || undefined); setSyncState((s) => ({ ...s, rate: r.rate })); return `연결됨: ${owner}/${repo} (기본 브랜치 ${r.data.default_branch}, ${r.data.private ? "비공개" : "공개"})`; };
  const onInit = async () => {
    const { owner, repo } = repoOf();
    let account = null; try { account = (await gh.user(cfg.token)).data.login; } catch {}
    const r = await syncer.init({ owner, repo, token: cfg.token, passphrase: cfg.key, account });
    const body = { ...r.body, plan: planRef.current };
    const s = await syncer.save({ owner, repo, token: cfg.token, key: r.key, body, baseCommit: r.commit, fileSha: r.sha, message: "저장: 초기 계획" });
    setSyncState({ connected: true, dirty: false, key: r.key, meta: r.meta, commit: s.commit, sha: s.sha, date: new Date().toISOString(), role: "main", account, stale: false });
    return "초기화와 첫 저장 완료";
  };
  const onLoad = async () => {
    const { owner, repo } = repoOf();
    const r = await syncer.load({ owner, repo, token: cfg.token || undefined, passphrase: cfg.key, cachedKey: syncRef.current.key, cachedMeta: syncRef.current.meta });
    if (r.notModified) return "변경 없음(최신)";
    if (r.body.plan) { setPlanState(r.body.plan); savePlan(localStorage, r.body.plan); }
    setSyncState({ connected: true, dirty: false, key: r.key, meta: r.meta, commit: r.commit, sha: r.sha, date: r.date, etag: r.etag, role: cfg.token ? "main" : "viewer", account: r.body.roles?.main, stale: false });
    return `불러옴: ${r.commit.slice(0, 7)}`;
  };
  const doSave = async (force = false) => {
    const { owner, repo } = repoOf(); const s0 = syncRef.current;
    const body = { roles: { main: s0.account || null, sub: [] }, plan: planRef.current };
    const r = await syncer.save({ owner, repo, token: cfg.token, key: s0.key, body, baseCommit: force ? null : s0.commit, fileSha: force ? (await gh.getFile(owner, repo, "trip.json.enc", { token: cfg.token })).sha : s0.sha, message: "저장" });
    if (r.conflict) { setConflict({ latest: r.latest, date: r.date }); throw new Error("다른 기기에서 먼저 저장했습니다. 처리 방법을 고르세요."); }
    setSyncState((s) => ({ ...s, dirty: false, commit: r.commit, sha: r.sha, date: new Date().toISOString(), stale: false }));
    return `저장됨: ${r.commit.slice(0, 7)}`;
  };
  const onSave = () => doSave(false);
  const onDisconnect = () => setSyncState({ connected: false, dirty: false });
  // 자동 저장(유휴 2분)과 화면 복귀 시 최신 확인
  useEffect(() => {
    if (!sync.connected || !sync.dirty || !cfg.token) return;
    const t = setTimeout(() => { doSave(false).catch(() => {}); }, AUTOSAVE_MS);
    return () => clearTimeout(t);
  }, [sync.dirty, sync.connected, plan]);
  useEffect(() => {
    const onVis = async () => { if (document.visibilityState !== "visible" || !syncRef.current.connected) return; try { const { owner, repo } = repoOf(); const l = await gh.latestCommit(owner, repo, "trip.json.enc", cfg.token || undefined); if (l.sha && l.sha !== syncRef.current.commit) setSyncState((s) => ({ ...s, stale: true })); } catch {} };
    document.addEventListener("visibilitychange", onVis); return () => document.removeEventListener("visibilitychange", onVis);
  }, [cfg.repo, cfg.token]);

  const titles = { input: "입력", explore: exploreTab === "summary" ? "요약" : "탐색·추천", plan: "선택·배치", share: "공유", settings: "설정" };
  return html`
    <header class="top"><h1>${titles[tab]}</h1>
      ${tab === "explore" && html`<button class="chip" onClick=${() => setExploreTab(exploreTab === "summary" ? "explore" : "summary")}>${exploreTab === "summary" ? "탐색 ▶" : "◀ 요약"}</button>`}
      ${sync.connected ? html`<button class=${"chip " + (sync.dirty ? "warn" : sync.stale ? "warn" : "ok")} title="버전" onClick=${() => { setTab("settings"); }}>${sync.commit ? sync.commit.slice(0, 7) : "—"}${sync.dirty ? " · 저장 필요" : sync.stale ? " · 오래됨" : " · 최신"}</button>` : html`<span class="version" title="데이터 갱신일">데이터 ${data.attribution.generated}</span>`}
    </header>
    <main class="main">
      ${tab === "input" && html`<${S1Input} trip=${plan.trip} setTrip=${setTrip} cities=${data.cities} airports=${data.airports} categories=${data.categories} role=${cfg.token || !sync.connected ? "main" : "viewer"} onDone=${() => { setExploreTab("summary"); setTab("explore"); }} />`}
      ${tab === "explore" && exploreTab === "summary" && html`<${S2Summary} trip=${plan.trip} cities=${data.cities} categories=${data.categories} prof=${prof} onReselect=${() => setTab("input")} onExplore=${(cid) => { setExploreCity(cid); setExploreTab("explore"); }} />`}
      ${tab === "explore" && exploreTab === "explore" && html`<${S3Explore} key=${exploreCity || "x"} trip=${plan.trip} cities=${data.cities} categories=${data.categories} tier1=${data.tier1} loader=${loaderWithCache} selection=${plan.selection} onToggleSelect=${toggleSelect} onOpenDetail=${openDetail} selectedId=${detailId} prof=${prof} nights=${nights} initialCity=${exploreCity} />`}
      ${tab === "plan" && html`<${S4Arrange} plan=${plan} cities=${data.cities} byId=${{ get: getPlace }} prof=${prof} nights=${nights} onAssign=${(id, d) => setPlan((p) => assignDay(p, id, d))} onMove=${(d, a, b) => setPlan((p) => moveInDay(p, d, a, b))} onSetLodging=${(cid, patch) => setPlan((p) => setLodging(p, cid, patch))} onAddCustom=${(c) => setPlan((p) => addCustomPlace(p, c))} onOpenDetail=${openDetail} onGenerate=${() => alert("일정 생성(E4)은 묶음 5에서 제공됩니다.")} />`}
      ${tab === "share" && html`<${Empty}>내보내기·My Maps(묶음 6), 제안·승인(묶음 9)은 다음 묶음에서 제공됩니다.</${Empty}>`}
      ${tab === "settings" && html`<${S8Settings} data=${data} cfg=${cfg} setCfg=${setCfg} syncState=${{ ...sync, role }} onCheck=${onCheck} onInit=${onInit} onLoad=${onLoad} onSave=${onSave} onDisconnect=${onDisconnect} />`}
    </main>
    ${detail && html`<${S6Detail} place=${detail} categories=${data.categories} loader=${loader} onClose=${() => setDetailId(null)} selected=${plan.selection.includes(detail.id)} onToggleSelect=${() => toggleSelect(detail.id)} cityPlaces=${cityPlacesOf(detail.city)} prof=${prof} reservation=${plan.reservations[detail.id]} onSetReservation=${(v) => setPlan((p) => ({ ...p, reservations: { ...p.reservations, [detail.id]: v } }))} onOpenDetail=${openDetail} />`}
    ${conflict && html`<div class="sheet" role="dialog" aria-label="저장 충돌"><h2>저장 충돌</h2><p>다른 기기에서 먼저 저장했습니다${conflict.date ? ` (${new Date(conflict.date).toLocaleString("ko-KR")})` : ""}. 어떻게 할까요?</p>
      <div class="row"><button class="btn" onClick=${async () => { const mine = planRef.current; try { await onLoad(); localStorage.setItem("trip01.plan.mine.v1", JSON.stringify(mine)); } catch {} setConflict(null); }}>최신 불러오기 (내 변경은 기기에 보존)</button>
      <button class="btn secondary" onClick=${async () => { if (confirm("정말 내 변경으로 덮어쓸까요? 상대의 변경이 사라집니다.")) { try { await doSave(true); } catch {} setConflict(null); } }}>덮어쓰기</button></div></div>`}
    <nav class="tabs" aria-label="주 탐색">${TABS.map(([k, label, ico]) => html`<button class=${tab === k ? "on" : ""} onClick=${() => { setTab(k); setDetailId(null); }} aria-current=${tab === k ? "page" : undefined}><span class="ico" aria-hidden="true">${ico}</span>${label}</button>`)}</nav>`;
}
