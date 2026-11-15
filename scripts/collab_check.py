#!/usr/bin/env python3
"""공동 편집 흐름 점검(E7 4절 2항·3항·5항·6항, D-034). 실제 GitHub 대신 이 스크립트 안의 모의 GitHub API를 브라우저에 붙인다.
메인(mina)·서브(minsu)·공유자 세 브라우저로 초기화 → 서브 등록 → 제안 → 승인·거절 → 충돌 → 내 변경 보존을 차례로 확인한다.
기다릴 때는 time.sleep이 아니라 page.wait_for_timeout을 쓴다(sleep 동안에는 모의 API가 요청에 답하지 못한다).
실행: <venv>/bin/python -I scripts/collab_check.py <앱 주소> <스크린샷 디렉터리>
"""
import base64
import json
import pathlib
import re
import sys
from urllib.parse import parse_qs, unquote, urlparse

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
REPO, KEY = "o/trip-test", "correct horse battery staple"
TOKENS = {"tok-main": "mina", "tok-sub": "minsu"}
PLACES = ["Q160112", "Q171517"]  # 마드리드의 1등급 장소 둘(프라도 미술관, 마드리드 왕궁)
CORS = {"access-control-allow-origin": "*", "access-control-expose-headers": "etag, x-ratelimit-limit, x-ratelimit-remaining", "x-ratelimit-limit": "60", "x-ratelimit-remaining": "59", "content-type": "application/json"}


class FakeGitHub:
    """contents·commits·user만 흉내 낸다. PUT은 토큰이 있어야 하고 blob SHA가 다르면 409를 준다."""

    def __init__(self):
        self.files, self.commits, self.n, self.log = {}, {}, 0, []

    def put(self, path, content):
        self.n += 1
        self.files[path] = {"content": content, "sha": f"blob{self.n}"}; self.commits[path] = f"{self.n:04x}abc{self.n:033x}"  # 앞 7자가 저장마다 다르다
        return self.files[path]["sha"], self.commits[path]

    def handle(self, route, who):
        req = route.request; u = urlparse(req.url); path = unquote(u.path); auth = (req.headers.get("authorization") or "").replace("Bearer ", "")
        self.log.append((who, req.method, path))
        def out(status, data):
            route.fulfill(status=status, headers=CORS, body=json.dumps(data))
        if path == "/user":
            return out(200, {"login": TOKENS[auth]}) if auth in TOKENS else out(401, {"message": "Bad credentials"})
        m = re.match(r"^/repos/([^/]+/[^/]+)(/.*)?$", path)
        if not m or m.group(1) != REPO:
            return out(404, {"message": "Not Found"})
        rest = m.group(2) or ""
        if rest == "":
            return out(200, {"default_branch": "main", "private": False})
        if rest == "/commits":
            sha = self.commits.get(parse_qs(u.query).get("path", [""])[0])
            return out(200, [{"sha": sha, "commit": {"committer": {"date": "2026-11-15T03:00:00Z"}}}] if sha else [])
        fp = rest[len("/contents/"):] if rest.startswith("/contents/") else None
        if fp is None:
            return out(404, {"message": "Not Found"})
        if req.method == "GET":
            f = self.files.get(fp)
            if f:
                return out(200, {"content": base64.b64encode(f["content"].encode()).decode(), "encoding": "base64", "sha": f["sha"]})
            kids = sorted(k for k in self.files if k.startswith(fp + "/"))
            return out(200, [{"name": k.split("/")[-1], "path": k, "sha": self.files[k]["sha"], "type": "file"} for k in kids]) if kids else out(404, {"message": "Not Found"})
        if req.method == "PUT":
            if auth not in TOKENS:
                return out(401, {"message": "Requires authentication"})
            body = json.loads(req.post_data); f = self.files.get(fp)
            if f and body.get("sha") != f["sha"]:
                return out(409, {"message": "sha mismatch"})
            sha, commit = self.put(fp, base64.b64decode(body["content"]).decode())
            return out(200 if f else 201, {"content": {"sha": sha}, "commit": {"sha": commit}})
        return out(405, {"message": "Method Not Allowed"})

    def count(self, who, method=None):
        return sum(1 for w, m, _ in self.log if w == who and (method is None or m == method))


def open_app(b, gh, who, url, storage, res):
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR")
    ctx.add_init_script("(() => { if (sessionStorage.getItem('seeded')) return; sessionStorage.setItem('seeded', '1'); const s = %s; for (const k in s) localStorage.setItem(k, JSON.stringify(s[k])); })();" % json.dumps(storage))
    ctx.route("https://api.github.com/**", lambda route: gh.handle(route, who))
    pg = ctx.new_page()
    pg.on("console", lambda m: res["console_errors"].append(f"{who}: {m.text}") if m.type == "error" and "the server responded with a status of 40" not in m.text else None)
    pg.on("pageerror", lambda e: res["console_errors"].append(f"{who} pageerror: {e}"))
    pg.on("dialog", lambda d: d.accept())
    pg.goto(url, wait_until="networkidle", timeout=60000); pg.wait_for_selector("nav.tabs", timeout=30000)
    return ctx, pg


def tab(pg, name):
    pg.click(f"nav.tabs button:has-text('{name}')"); pg.wait_for_timeout(300)


def toast(pg, wait=6000):
    try:
        pg.wait_for_selector(".toast", timeout=wait); return pg.locator(".toast").inner_text()
    except Exception:
        return None


def settings_text(pg, label):
    tab(pg, "설정"); return pg.locator(f"dl.kv dt:has-text('{label}') + dd").first.inner_text().replace("\n", " ")


def main():
    url, shots = sys.argv[1], pathlib.Path(sys.argv[2]); shots.mkdir(parents=True, exist_ok=True)
    res = {"console_errors": []}; gh = FakeGitHub()
    plan = {"trip": {"start": "2027-05-01", "end": "2027-05-03", "cities": ["Q2807"], "airportOut": None, "airportIn": None, "timeOut": "", "timeIn": "", "people": 2, "budget": "mid", "dayStart": "09:00", "dayEnd": "22:00", "meals": ["normal"], "tastes": ["museum"], "foreignBalance": "balance"},
            "selection": PLACES, "custom": {}, "days": {"2027-05-01": [PLACES[0]], "2027-05-02": [PLACES[1]]}, "lodging": {}, "reservations": {}, "version": 1}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)
        try:
            # --- 메인: 초기화, 서브 등록
            mctx, mp = open_app(b, gh, "main", url, {"trip01.plan.v1": plan, "trip01.sync.v1": {"repo": REPO, "key": KEY, "token": "tok-main"}}, res)
            m = res["main"] = {}
            m["boot_notice"] = toast(mp)  # 빈 저장소: 초기화가 필요하다는 안내
            tab(mp, "설정"); mp.click("button:has-text('초기화(첫 저장)')"); mp.wait_for_selector("text=초기화와 첫 저장 완료", timeout=30000)
            m["role"] = settings_text(mp, "역할"); m["files_after_init"] = sorted(gh.files)
            m["plaintext_leak"] = any(PLACES[0] in f["content"] or "mina" in f["content"] for k, f in gh.files.items())  # 저장소 파일에 장소 ID·계정이 평문으로 보이면 안 된다
            mp.fill("input[aria-label='서브 수립자 계정']", "minsu"); mp.click("button:has-text('추가')"); mp.wait_for_selector("text=저장됨:", timeout=30000)
            m["planners"] = settings_text(mp, "수립자"); mp.screenshot(path=str(shots / "main_settings.png"))
            trip_after_roles = dict(gh.files["trip.json.enc"]); commit_after_roles = gh.commits["trip.json.enc"]

            # --- 서브: 열면 자동으로 읽고, 편집은 제안으로 바뀐다
            sctx, sp = open_app(b, gh, "sub", url, {"trip01.sync.v1": {"repo": REPO, "key": KEY, "token": "tok-sub"}}, res)
            s = res["sub"] = {}
            s["boot_notice"] = toast(sp); s["role"] = settings_text(sp, "역할"); s["header"] = sp.locator("header.top .chip").last.inner_text()
            tab(sp, "일정"); sp.wait_for_selector("select[aria-label='날짜']", timeout=10000)
            sp.locator("select[aria-label='날짜']").first.select_option("2027-05-03"); sp.wait_for_selector(".sheet.proposal", timeout=5000)
            s["proposal_text"] = sp.locator(".sheet.proposal .what").inner_text(); sp.fill(".sheet.proposal textarea", "마지막 날이 한가하다")
            sp.screenshot(path=str(shots / "sub_proposal.png")); sp.click(".sheet.proposal button:has-text('제안 보내기')")
            sp.wait_for_selector(".toast:has-text('제안을 보냈습니다')", timeout=10000); s["sent_notice"] = sp.locator(".toast").inner_text()
            s["select_value_after"] = sp.locator("select[aria-label='날짜']").first.input_value()  # 계획은 그대로여야 한다
            s["edit_controls_hidden"] = {"일정 생성": sp.locator("button:has-text('일정 생성')").count(), "순서 버튼": sp.locator("button[aria-label='위로']").count(), "직접 추가": sp.locator("text=직접 추가").count()}  # 서브에게는 본문 편집 요소가 없다
            tab(sp, "공유"); sp.click("button:has-text('메모 제안 쓰기')"); sp.wait_for_selector(".sheet.proposal", timeout=5000)
            sp.fill(".sheet.proposal textarea", "숙소는 역 근처가 좋겠다"); sp.click(".sheet.proposal button:has-text('제안 보내기')"); sp.wait_for_timeout(1500)
            sp.click("section.proposals button:has-text('새로 고침')"); sp.wait_for_timeout(1000)
            s["my_proposals"] = [x.replace("\n", " | ")[:90] for x in sp.locator(".card.proposal").all_inner_texts()]; s["decide_buttons"] = sp.locator(".card.proposal button").count()
            s["trip_file_unchanged"] = gh.files["trip.json.enc"] == trip_after_roles and gh.commits["trip.json.enc"] == commit_after_roles  # 제안은 본문 파일을 바꾸지 않는다(R-23)
            s["proposal_files"] = len([k for k in gh.files if k.startswith("proposals/")]); sp.screenshot(path=str(shots / "sub_share.png"))

            # --- 공유자: 공유 링크로 열어 Key만 입력
            vctx, vp = open_app(b, gh, "viewer", url + "?repo=" + REPO, {}, res)
            v = res["viewer"] = {}
            v["boot_notice"] = toast(vp); v["repo_prefilled"] = vp.locator("input[placeholder*='trip-2027']").input_value()
            vp.locator("input[type=password]").first.fill(KEY); vp.click("button:has-text('불러오기')"); vp.wait_for_selector("text=불러옴:", timeout=30000)
            v["role"] = settings_text(vp, "역할"); v["save_disabled"] = vp.locator("button.btn:text-is('저장')").is_disabled()
            tab(vp, "일정"); vp.wait_for_selector("select[aria-label='날짜']", timeout=10000); v["date_select_disabled"] = vp.locator("select[aria-label='날짜']").first.is_disabled(); v["edit_controls"] = vp.locator("button:has-text('일정 생성'), button[aria-label='위로'], button[aria-label='선택']").count()
            v["guard"] = vp.evaluate("(() => { const el = document.querySelector(\"select[aria-label='날짜']\"); el.disabled = false; el.value = '2027-05-03'; el.dispatchEvent(new Event('change', { bubbles: true })); return true; })()"); v["blocked_notice"] = toast(vp)  # 잠금을 억지로 풀어도 반영되지 않는다
            tab(vp, "공유"); v["proposals_note"] = vp.locator("section.section").first.inner_text().replace("\n", " ")[:70]
            before = gh.count("viewer"); vp.reload(wait_until="networkidle"); vp.wait_for_selector("nav.tabs", timeout=30000); v["reload_notice"] = toast(vp)
            v["api_calls_on_reopen"] = gh.count("viewer") - before; v["put_calls"] = gh.count("viewer", "PUT"); vp.screenshot(path=str(shots / "viewer.png"))

            # --- 메인: 화면으로 돌아오면 제안이 보이고, 승인하면 본문에 반영된다
            mp.reload(wait_until="networkidle"); mp.wait_for_selector("nav.tabs", timeout=30000); m["reload_notice"] = toast(mp); mp.wait_for_timeout(1500)
            m["header_with_proposals"] = mp.locator("header.top .chip").last.inner_text()
            tab(mp, "공유"); mp.wait_for_selector(".card.proposal", timeout=10000); m["proposals"] = [x.replace("\n", " | ")[:80] for x in mp.locator(".card.proposal").all_inner_texts()]
            mp.screenshot(path=str(shots / "main_share.png"))
            mp.locator(".card.proposal:has-text('이동') button:has-text('승인')").click(); mp.wait_for_selector("text=승인해 계획에 반영했습니다", timeout=30000)
            mp.locator(".card.proposal.pending:has-text('숙소') button:has-text('거절')").click(); mp.wait_for_selector("text=거절했습니다", timeout=30000)
            m["statuses"] = sorted(x.split("\n")[0][:30] + " → " + ("승인" if "승인:" in x else "거절" if "거절:" in x else "대기") for x in mp.locator(".card.proposal").all_inner_texts())
            m["trip_commit_changed"] = gh.commits["trip.json.enc"] != commit_after_roles; m["proposal_files_kept"] = len([k for k in gh.files if k.startswith("proposals/")])
            tab(mp, "일정"); mp.wait_for_selector("select[aria-label='날짜']", timeout=10000); m["first_place_day_after_approve"] = mp.locator("select[aria-label='날짜']").first.input_value()

            # --- 충돌: 다른 기기가 먼저 저장한 상황을 만들고(본문 커밋만 바꾼다) 메인이 편집 후 저장
            gh.put("trip.json.enc", gh.files["trip.json.enc"]["content"])
            mp.locator("select[aria-label='날짜']").nth(1).select_option("2027-05-03"); mp.wait_for_timeout(300)
            tab(mp, "설정"); mp.click("button.btn:text-is('저장')"); mp.wait_for_selector("div[aria-label='저장 충돌']", timeout=30000); m["conflict_dialog"] = True
            mp.screenshot(path=str(shots / "main_conflict.png")); mp.click("button:has-text('최신 불러오기')"); mp.wait_for_selector(".toast:has-text('최신 계획을 불러왔습니다')", timeout=30000); m["conflict_notice"] = mp.locator(".toast").inner_text()
            tab(mp, "설정"); m["mine_card"] = mp.locator("text=보존된 내 변경").count()
            mp.click("button:has-text('다시 적용')"); mp.wait_for_timeout(500); mp.click("button.btn:text-is('저장')"); mp.wait_for_selector("text=저장됨:", timeout=30000); m["saved_after_restore"] = True
            # --- 저장 안 된 내 변경은 다시 열어도 남는다
            tab(mp, "일정"); mp.wait_for_selector("select[aria-label='날짜']", timeout=10000); mp.locator("select[aria-label='날짜']").first.select_option("2027-05-02"); mp.wait_for_timeout(400)
            mp.reload(wait_until="networkidle"); mp.wait_for_selector("nav.tabs", timeout=30000); m["reopen_with_draft_notice"] = toast(mp)
            tab(mp, "일정"); mp.wait_for_selector("select[aria-label='날짜']", timeout=10000); m["draft_kept_value"] = mp.locator("select[aria-label='날짜']").first.input_value(); m["header_dirty"] = mp.locator("header.top .chip").last.inner_text()

            # --- 서브: 화면에 다시 오면 처리 결과가 보인다
            tab(sp, "공유"); sp.click("section.proposals button:has-text('새로 고침')"); sp.wait_for_selector(".card.proposal.approved", timeout=10000)
            s["statuses_after_decision"] = sorted(("승인" if "승인:" in x else "거절" if "거절:" in x else "대기") for x in sp.locator(".card.proposal").all_inner_texts())
            res["github"] = {"puts_by": {w: gh.count(w, "PUT") for w in ("main", "sub", "viewer")}, "files": sorted(gh.files)}
            for c in (mctx, sctx, vctx):
                c.close()
        finally:
            b.close()
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
