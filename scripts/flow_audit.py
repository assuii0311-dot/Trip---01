#!/usr/bin/env python3
"""화면 흐름 점검(D-036). 계획을 세울 때처럼 화면을 앞뒤로 오가며 무엇이 남고 무엇이 처음으로 돌아가는지 잰다.
고치기 전후를 같은 방법으로 비교하려고 예전 화면(상단 전환 칩)과 새 화면(하위 탭)을 모두 다룬다.
실행: <venv>/bin/python -I scripts/flow_audit.py <앱 주소> [가로x세로, 기본 820x1180] [프록시 주소]
출력: 상황별 결과(JSON). 기다릴 때는 page.wait_for_timeout을 쓴다.
"""
import json
import sys

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def main():
    url = sys.argv[1]
    w, h = (int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "820x1180").split("x"))
    proxy = {"server": sys.argv[3]} if len(sys.argv) > 3 else None
    out = {}

    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True, proxy=proxy)
        pg = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, locale="ko-KR").new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        def wait(ms=500):
            pg.wait_for_timeout(ms)

        def tab(name):
            pg.click(f"nav.tabs button:has-text('{name}')"); wait(700)

        def step_on():
            loc = pg.locator(".steps .on")
            return loc.inner_text() if loc.count() else None

        def title():
            return pg.locator("header.top h1").inner_text()

        def sub(new_label, old_chip):
            """하위 화면 전환: 새 화면은 하위 탭, 예전 화면은 상단 칩"""
            loc = pg.locator(f".subtabs button:has-text('{new_label}')")
            (loc.first if loc.count() else pg.locator(f"header.top button.chip:has-text('{old_chip}')").first).click(); wait(600)

        def scroll_get():
            return pg.evaluate("(() => { const m = document.querySelector('.main'), l = document.querySelector('.two .list'); return Math.round(Math.max(m ? m.scrollTop : 0, l ? l.scrollTop : 0)); })()")

        def scroll_set(y):
            pg.evaluate("(y) => { const m = document.querySelector('.main'), l = document.querySelector('.two .list'); if (l && l.scrollHeight > l.clientHeight) l.scrollTop = y; else if (m) m.scrollTop = y; }", y); wait(300)

        def search_value(placeholder):
            loc = pg.locator(f"input[placeholder{placeholder}]")
            return loc.input_value() if loc.count() else None

        def explore_state():
            sel = pg.locator(".toolbar select")
            seg = pg.locator(".toolbar .seg button.on")
            return {"도시": sel.first.evaluate("e => e.options[e.selectedIndex].text") if sel.count() else None, "목록": seg.first.inner_text() if seg.count() else None,
                    "검색어": search_value("='장소 이름 검색'"), "범주 필터": pg.locator(".toolbar.chips button.on").count()}

        try:
            pg.goto(url, wait_until="networkidle", timeout=90000); pg.wait_for_selector(".steps", timeout=60000)
            # ---- 입력
            d = pg.locator("input[type=date]"); d.nth(0).fill("2027-05-01"); d.nth(1).fill("2027-05-10")
            pg.click("text=다음 ▶"); pg.wait_for_selector(".destlist .card.dest", timeout=20000)
            for q in ("madrid", "sevilla", "granada"):
                pg.fill("input[placeholder*='여행지 검색']", q); wait(400); pg.locator(".destlist .card.dest .pick").first.click()
            pg.fill("input[placeholder*='여행지 검색']", ""); wait(300)
            pg.locator(".steps > *").nth(2).click(); wait(400)
            out["a1 단계 표시를 눌러 3단계로"] = step_on()
            if not (step_on() or "").startswith("2"):
                pg.click("button:has-text('◀ 이전')"); wait(300)
            pg.wait_for_selector(".destlist", timeout=5000)
            scroll_set(3000); y0 = scroll_get()  # 필터를 걸기 전의 긴 목록에서 위치를 잰다
            pg.click(".stepnav .btn:has-text('다음')"); pg.wait_for_selector(".airport", timeout=5000); pg.click("button:has-text('◀ 이전')"); pg.wait_for_selector(".destlist", timeout=5000); wait(1600)
            y_back = scroll_get()
            pg.click(".seg button:has-text('섬')"); wait(300); pg.fill("input[placeholder*='여행지 검색']", "ma"); wait(400)
            pg.click(".stepnav .btn:has-text('다음')"); pg.wait_for_selector(".airport", timeout=5000); pg.click("button:has-text('◀ 이전')"); pg.wait_for_selector(".destlist", timeout=5000); wait(600)
            out["a2 3단계에 다녀온 뒤 여행지 화면"] = {"검색어": search_value("*='여행지 검색'"), "섬 필터": pg.locator(".seg button.on:has-text('섬')").count() == 1, "목록 위치": f"{y0} → {y_back}"}
            tab("설정"); tab("입력")
            out["a3 여행지를 고르다 다른 탭에 다녀오면"] = {"단계": step_on(), "검색어": search_value("*='여행지 검색'")}
            out["a3 필터 지우기 버튼"] = pg.locator("button:has-text('필터 지우기')").count() > 0
            if (step_on() or "").startswith("1"):
                pg.click("text=다음 ▶"); pg.wait_for_selector(".destlist .card.dest", timeout=20000)
            pg.fill("input[placeholder*='여행지 검색']", ""); pg.click(".seg button:has-text('전체')"); wait(300)
            tastes = pg.locator(".tastes button.taste")
            if tastes.count():  # 입력 3단계(D-039): 취향을 여행지 화면에서 고른다
                tastes.nth(0).click(); tastes.nth(2).click()
                pg.click(".stepnav .btn:has-text('다음')"); pg.wait_for_selector(".airport", timeout=5000); pg.click("text=장소 고르러 가기")
            else:  # 예전 4단계
                pg.click(".stepnav .btn:has-text('다음')"); pg.wait_for_selector(".airport", timeout=5000); pg.click("text=다음 ▶"); pg.wait_for_selector(".cats", timeout=5000)
                cats = pg.locator(".catcard"); cats.nth(0).click(); cats.nth(2).click(); pg.click("text=탐색으로 ▶")
            pg.wait_for_selector(".card", timeout=30000); wait(800)
            tab("입력")
            out["a4 입력을 끝낸 뒤 입력 탭에 오면"] = step_on()
            out["입력 단계 수"] = pg.locator(".steps > *").count()
            tab("탐색")
            bar = pg.locator(".tripbar")
            out["d4 위쪽의 여행 요약"] = bar.inner_text().replace("\n", " | ") if bar.count() else "없음(" + pg.locator("header.top").inner_text().replace("\n", " | ") + ")"
            if bar.count():
                bar.locator("button").nth(1).click(); wait(500); out["a4 요약 줄의 여행지를 누르면"] = f"{title()} {step_on()}"; tab("탐색")
            # ---- 탐색
            out["b6 요약과 탐색을 오가는 방법"] = "하위 탭: " + " / ".join(pg.locator(".subtabs button").all_inner_texts()) if pg.locator(".subtabs").count() else "상단 칩: " + " ".join(pg.locator("header.top button.chip").all_inner_texts()[:1])
            ex = ".card .btn.explore" if pg.locator(".card .btn.explore").count() else ".card .btn"  # 도시 카드의 "장소 고르기"
            pg.locator(ex).nth(1).click(); pg.wait_for_selector(".toolbar .seg", timeout=20000); wait(2500)  # 두 번째 도시
            pg.click("button:has-text('전체 후보')"); pg.wait_for_selector(".card", timeout=30000); wait(1200)
            pg.locator(".toolbar.chips button").nth(2).click(); wait(500); pg.fill("input[placeholder='장소 이름 검색']", "museo"); wait(800); scroll_set(500); y0 = scroll_get()
            before = explore_state()
            pg.locator(".card").nth(2).click(); pg.wait_for_selector(".sheet", timeout=10000); wait(800)
            out["d3 상세가 열려 있을 때 아래쪽 탭"] = pg.evaluate("(() => { const b = [...document.querySelectorAll('nav.tabs button')].find((x) => x.textContent.includes('일정')); const r = b.getBoundingClientRect(); return b.contains(document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)) ? '누를 수 있음' : '상세에 가려 누를 수 없음'; })()")
            first = pg.locator(".sheet h2").inner_text()
            alt = pg.locator(".sheet a[href='#']")
            if alt.count():
                alt.first.click(); wait(800)
                if pg.locator(".subtabs").count():  # 새 화면: 뒤로 가기로 처음 보던 장소에 돌아가는지
                    pg.go_back(); wait(800)
                    back_title = pg.locator(".sheet h2").inner_text() if pg.locator(".sheet").count() else None
                    out["b2 상세 → 대안 장소 → 돌아가기"] = "뒤로 가기로 처음 보던 장소에 돌아감" if back_title == first else f"돌아가지 않음({back_title})"
                else:  # 예전 화면: 뒤로 가기는 앱을 벗어나므로 닫기만 본다
                    pg.click(".sheet .close"); wait(400)
                    out["b2 상세 → 대안 장소 → 돌아가기"] = "닫으면 목록으로 나감(처음 보던 장소는 다시 찾아야 함)" if not pg.locator(".sheet").count() else "상세가 남아 있음"
            if pg.locator(".sheet").count():
                pg.click(".sheet .close"); wait(500)
            if pg.locator("input[placeholder='장소 이름 검색']").count():
                out["b1 상세를 닫은 뒤"] = {**explore_state(), "목록 위치": f"{y0} → {scroll_get()}"}
            picks = pg.locator(".card button[aria-label='선택']")
            if picks.count() >= 2:
                picks.nth(0).click(); picks.nth(1).click(); wait(400)
            out["b5 탐색 화면에서 고른 장소 수"] = (pg.locator(".tripbar").inner_text().split("\n")[-1] if pg.locator(".tripbar").count() else "표시 없음")
            out["c5 지도의 고른 장소 표시"] = pg.locator(".maplegend").inner_text().replace("\n", " · ") if pg.locator(".maplegend").count() else "구분 없음"
            if pg.locator(".toolbar select").count():
                pg.locator(".toolbar select").first.select_option(index=2); wait(2500)
                out["b3 도시를 바꾼 뒤"] = {**explore_state(), "필터 지우기 버튼": pg.locator("button:has-text('필터 지우기')").count() > 0}
                pg.locator(".toolbar select").first.select_option(index=1); wait(2000)
            scroll_set(400); y1 = scroll_get(); before = explore_state()
            tab("일정"); tab("탐색"); wait(1800)
            after = explore_state()
            out["b4 탐색하다 일정 탭에 다녀오면"] = {"화면": title(), **{k: (f"{before[k]} → {after[k]}" if before[k] != after[k] else f"{after[k]} (그대로)") for k in before}, "목록 위치": f"{y1} → {scroll_get()}"}
            sub("도시 요약", "요약"); pg.wait_for_selector(".card", timeout=10000)
            out["b5 요약 화면의 고른 장소"] = pg.locator(".picks").first.inner_text()[:60] if pg.locator(".picks").count() else "표시 없음"
            for i in range(pg.locator(ex).count()):
                pg.locator(ex).nth(i).click(); pg.wait_for_selector(".toolbar .seg", timeout=20000); wait(1500)
                pg.locator(".toolbar .seg button:has-text('추천')").click(); wait(1800)
                pk = pg.locator(".card button[aria-label='선택']")
                for j in range(min(6, pk.count())):
                    if pk.nth(j).inner_text().strip() == "+":
                        pk.nth(j).click()
                sub("도시 요약", "요약"); pg.wait_for_selector(".card", timeout=10000)
            # ---- 일정
            tab("일정"); pg.wait_for_selector("select[aria-label='날짜']", timeout=10000)
            pg.click(".toolbar .seg button:has-text('숙박')"); wait(400); tab("탐색"); tab("일정")
            out["c4 숙박을 보다가 다른 탭에 다녀오면"] = pg.locator(".toolbar .seg button.on").first.inner_text()
            if pg.locator("button:has-text('일정 생성')").count() == 0:
                pg.click(".toolbar .seg button:has-text('장소 배치')"); wait(300)
            pg.click("button:has-text('일정 생성')"); pg.wait_for_selector("text=이 날 재생성", timeout=120000); wait(800)
            pg.locator(".toolbar button.chip").nth(2).click(); wait(400); day = pg.locator(".toolbar button.chip.on").inner_text()
            pg.locator(".card .title").first.click(); pg.wait_for_selector(".sheet", timeout=10000); wait(500); pg.click(".sheet .close"); wait(400)
            out["c1 일정표에서 상세를 열고 닫으면"] = f"{day} → {pg.locator('.toolbar button.chip.on').inner_text()}"
            sub("배치", "배치"); sub("일정표", "일정표")
            out["c2 배치와 일정표를 오가면"] = f"{day} → {pg.locator('.toolbar button.chip.on').inner_text()}"
            pg.locator(".toolbar button.chip").nth(2).click(); wait(300)
            tab("탐색"); wait(1000)
            if not pg.locator(".toolbar .seg").count():
                pg.locator(ex).first.click(); pg.wait_for_selector(".toolbar .seg", timeout=20000); wait(1500)
            pg.locator(".toolbar .seg button:has-text('추천')").click(); wait(1800)
            pk = pg.locator(".card button[aria-label='선택']")
            for j in range(pk.count()):
                if pk.nth(j).inner_text().strip() == "+":
                    pk.nth(j).click(); break
            tab("일정"); wait(800)
            out["c3 일정표를 보다 다른 탭에 다녀오면"] = {"화면": title(), "날짜": f"{day} → " + (pg.locator(".toolbar button.chip.on").inner_text() if pg.locator(".toolbar button.chip.on").count() else "?")}
            out["c5 장소를 더 고른 뒤 일정표"] = pg.locator(".driftbar").inner_text().replace("\n", " ")[:90] if pg.locator(".driftbar").count() else "안내 없음(직접 '전체 재생성'을 눌러야 함)"
            # ---- 앱 전체
            out["d5 주소"] = pg.url.replace(url, "/")
            tab("탐색"); tab("설정"); tab("일정"); wait(300)
            try:
                pg.go_back(wait_until="commit", timeout=8000); wait(800)
                out["d1 뒤로 가기"] = ("앱 안의 직전 화면: " + title()) if pg.url.startswith(url) and pg.locator("header.top h1").count() else "앱을 벗어남"
            except Exception as e:  # noqa: BLE001
                out["d1 뒤로 가기"] = "오류: " + str(e)[:60]
            if not pg.url.startswith(url):
                pg.goto(url, wait_until="networkidle"); pg.wait_for_selector("nav.tabs", timeout=60000)
            tab("일정"); wait(400)
            pg.reload(wait_until="networkidle"); pg.wait_for_selector("nav.tabs", timeout=60000); wait(800)
            out["d2 새로 고침 뒤"] = {"화면": title() + (" " + step_on() if step_on() else ""), "고른 장소": (pg.locator(".tripbar").inner_text().split("\n")[-1] if pg.locator(".tripbar").count() else "(일정 탭에서 확인)")}
        finally:
            out["화면 오류"] = errors
            print(json.dumps(out, ensure_ascii=False, indent=1))
            b.close()


if __name__ == "__main__":
    main()
