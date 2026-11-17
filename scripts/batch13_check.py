#!/usr/bin/env python3
"""묶음 13 브라우저 점검: 다음 단계 버튼, 자동 배정, 집어서 넣기, 끌어다 놓기, 여행지 빼기(고른 장소 함께), 모두 지우기, 범주 설명.
실행: python -I scripts/batch13_check.py <앱 주소> <스크린샷 디렉터리> [가로x세로]
"""
import json
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium"  # 환경이 제공하는 크로미움의 고정 경로(판 번호가 바뀌어도 같다)


def main():
    url, shots = sys.argv[1], pathlib.Path(sys.argv[2]); shots.mkdir(parents=True, exist_ok=True)
    w, h = (int(v) for v in (sys.argv[3] if len(sys.argv) > 3 else "1180x820").split("x"))
    res = {"console_errors": [], "dialogs": []}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)
        page = b.new_context(viewport={"width": w, "height": h}, locale="ko-KR", has_touch=True).new_page()
        page.on("console", lambda m: res["console_errors"].append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: res["console_errors"].append(f"pageerror: {e}"))
        page.on("dialog", lambda d: (res["dialogs"].append(d.message), d.accept()))
        plan = lambda: page.evaluate("JSON.parse(localStorage.getItem('trip01.plan.v1'))")
        page.goto(url, wait_until="networkidle", timeout=60000); page.wait_for_selector(".steps", timeout=30000)
        d = page.locator("input[type=date]"); d.nth(0).fill("2027-05-01"); d.nth(1).fill("2027-05-10")
        page.click("text=다음 ▶"); page.wait_for_selector(".destlist .card.dest", timeout=10000)
        page.click("summary:has-text('범주 설명 보기')"); res["category_help_first"] = page.locator(".tastehelp .note").first.inner_text()[:120]
        for name in ("madrid", "mallorca"):
            page.fill("input[placeholder*='여행지 검색']", name); time.sleep(0.4); page.locator(".destlist .card.dest .pick").first.click(); time.sleep(0.2)
        page.fill("input[placeholder*='여행지 검색']", "")
        page.click(".stepnav .btn:has-text('다음')"); page.wait_for_selector(".airport", timeout=5000)
        page.locator("input[placeholder*='공항 검색']").first.fill("madrid"); page.wait_for_selector(".airport .chips button.chip", timeout=5000); page.locator(".airport .chips button.chip").first.click()
        page.click("text=장소 고르러 가기"); page.wait_for_selector("button.addall", timeout=30000); time.sleep(1)
        for i in range(page.locator("button.addall").count()):
            page.locator("button.addall").nth(i).click(); time.sleep(0.4)
        pl = plan(); res["cities"] = pl["trip"]["cities"]; res["picked_after_addall"] = len(pl["selection"])
        res["summary_next_button"] = page.locator(".stepnav .tonext").inner_text().replace("\n", " ")
        page.screenshot(path=str(shots / "b13_1_summary.png"))
        # 장소 고르기의 아래 줄
        page.locator("button.explore").first.click(); page.wait_for_selector(".listnav .tonext", timeout=15000); res["explore_bar"] = page.locator(".listnav").inner_text().replace("\n", " | ")
        page.click(".listnav .tonext"); page.wait_for_selector(".arr .arr-city", timeout=15000)
        res["arrange_cities"] = [x.replace("\n", " ")[:40] for x in page.locator(".arr-cityhead h2").all_inner_texts()]
        res["place_rows"] = page.locator(".mini.place").count(); res["row_height_px"] = page.locator(".mini.place").first.bounding_box()["height"]
        # 자동 배정(첫 여행지)
        page.locator("button.autoassign").first.click(); time.sleep(0.5)
        pl = plan(); days = pl["days"]; res["auto_assign"] = {"dates_used": sum(1 for v in days.values() if v), "max_per_day": max(len(v) for v in days.values()), "assigned": sum(len(v) for v in days.values())}
        res["notice_after_auto"] = (page.locator(".notice, .toast").first.inner_text()[:120] if page.locator(".notice, .toast").count() else None)
        page.screenshot(path=str(shots / "b13_2_arrange.png"))
        # 집어서 넣기: 미배치 장소 하나를 누르고 날짜를 누른다
        free = page.locator(".mini.place:has(.daytag:not(.on))").first; name = free.locator(".nm").inner_text(); free.click(); time.sleep(0.2)
        res["held_rows"] = page.locator(".mini.place.held").count()
        box = page.locator(".daybox[data-drop]:not(.none)").nth(1); date = box.get_attribute("data-drop"); before = len(plan()["days"].get(date, [])); box.locator(".dayhead").click(); time.sleep(0.3)
        res["tap_assign"] = {"date": date, "before": before, "after": len(plan()["days"].get(date, [])), "held_after": page.locator(".mini.place.held").count()}
        # 끌어다 놓기: 손잡이를 잡아 다른 날짜 상자에 놓는다
        time.sleep(1.0)  # 알림이 뜨고 사라지며 화면이 밀리는 동안에는 좌표를 재지 않는다
        src = page.locator(".mini.place:has(.daytag:not(.on)) .grip").first; src.scroll_into_view_if_needed(); sb = src.bounding_box(); tgt = page.locator(".daybox[data-drop]:not(.none)").nth(0); date2 = tgt.get_attribute("data-drop"); tb = tgt.locator(".dayhead").bounding_box(); before2 = len(plan()["days"].get(date2, []))
        page.mouse.move(sb["x"] + sb["width"] / 2, sb["y"] + sb["height"] / 2); page.mouse.down(); page.mouse.move(tb["x"] + 40, tb["y"] + 10, steps=8); time.sleep(0.3)
        res["drag_target_element"] = page.evaluate("([x, y]) => { const el = document.elementFromPoint(x, y); const t = el && el.closest('[data-drop]'); return [el ? el.className : null, t ? t.getAttribute('data-drop') : null]; }", [tb["x"] + 40, tb["y"] + 10])
        res["drag_ghost_visible"] = page.locator(".dragghost").count(); res["drag_over_highlight"] = page.locator(".daybox.over").count(); page.screenshot(path=str(shots / "b13_3_dragging.png")); page.mouse.up(); time.sleep(0.3)
        res["drag_assign"] = {"date": date2, "before": before2, "after": len(plan()["days"].get(date2, []))}
        # 여행지 빼기(도시 요약): 그 여행지에서 고른 장소도 함께 빠진다
        page.click("nav.tabs button:has-text('탐색')"); page.click(".subtabs button:has-text('도시 요약')"); page.wait_for_selector(".removedest", timeout=10000)
        before_sel = len(plan()["selection"]); page.locator(".card:has-text('마요르카') .removedest").first.click(); time.sleep(1.5)
        pl = plan(); res["remove_destination"] = {"cities": pl["trip"]["cities"], "picked_before": before_sel, "picked_after": len(pl["selection"]), "dialog": res["dialogs"][-1] if res["dialogs"] else None}
        tier1 = page.evaluate("""async () => { const r = await fetch('data/places_tier1.json.gz'); const ds = new DecompressionStream('gzip'); const t = await new Response(r.body.pipeThrough(ds)).json(); return Object.fromEntries(t.map((p) => [p.id, p.city])); }""")
        cities = page.evaluate("""async () => { const r = await fetch('data/cities.json.gz'); const ds = new DecompressionStream('gzip'); const t = await new Response(r.body.pipeThrough(ds)).json(); const m = t.find((c) => c.id === 'Q8828'); return m ? m.members : []; }""")
        res["mallorca_places_left"] = sum(1 for i in pl["selection"] if tier1.get(i) in set(cities))
        res["orphan_notice"] = page.locator(".clearorphan").count()
        # 모두 지우기
        page.click(".stepnav .clearall"); time.sleep(0.5); pl = plan(); res["clear_all"] = {"picked": len(pl["selection"]), "assigned": sum(len(v) for v in pl["days"].values()), "dialog": res["dialogs"][-1]}
        page.screenshot(path=str(shots / "b13_4_cleared.png"))
        b.close()
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
