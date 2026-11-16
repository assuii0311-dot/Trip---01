#!/usr/bin/env python3
"""앱 흐름 점검(와이어프레임 검증 항목). 이 환경의 Chromium으로 로컬 사이트를 열어 S1(기본 정보 → 여행지 → 공항·형태 → 취향) → S8 흐름과 섬 여행지 흐름, 콘솔 오류를 확인한다.
실행: <venv>/bin/python -I scripts/flow_check.py <주소> <스크린샷 디렉터리>
"""
import json
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def main():
    url, shots = sys.argv[1], pathlib.Path(sys.argv[2]); shots.mkdir(parents=True, exist_ok=True)
    res = {"console_errors": [], "steps": {}}
    with sync_playwright() as p:
      b = p.chromium.launch(executable_path=CHROME, headless=True)
      try:
          ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR")
          page = ctx.new_page()
          page.on("console", lambda m: res["console_errors"].append(m.text) if m.type == "error" else None)
          page.on("pageerror", lambda e: res["console_errors"].append(f"pageerror: {e}"))
          t = time.time(); page.goto(url, wait_until="networkidle", timeout=60000)
          try:
              page.wait_for_selector(".steps", timeout=30000)
          except Exception:
              res["boot_html"] = page.inner_html("#app")[:600]; print(json.dumps(res, ensure_ascii=False, indent=1)); b.close(); return
          res["steps"]["boot_s"] = round(time.time() - t, 2)
          page.screenshot(path=str(shots / "s1.png"))
          # S1 ①: 나라(고정)·기간·인원 → 다음
          dates = page.locator("input[type=date]"); dates.nth(0).fill("2027-05-01"); dates.nth(1).fill("2027-05-10")
          page.click("text=다음 ▶"); page.wait_for_selector(".destlist .card.dest", timeout=10000)
          # S1 ②: 여행지 카드(D-030). 목록 수, 섬 필터, 취향 필터, 검색 → 선택
          res["steps"]["dest_cards"] = page.locator(".destlist .card.dest").count()
          res["steps"]["dest_first"] = page.locator(".destlist .card.dest").first.inner_text().replace("\n", " | ")[:260]
          res["steps"]["dest_ko_summaries"] = page.locator(".destlist .card.dest .lead.ko").count()  # E5 한국어 소개(D-032)
          page.click(".seg button:has-text('섬')"); time.sleep(0.3); res["steps"]["dest_islands"] = page.locator(".destlist .card.dest").count(); page.click(".seg button:has-text('전체')")
          # 인기와 취향 추천을 따로 본다(D-049): 취향을 골라도 순서는 인기순 그대로, 취향 추천은 10곳, "취향 추천만"과 "취향순"으로 따로 본다
          res["steps"]["dest_popular"] = page.locator(".destlist .card.dest .chip.pop").count()
          res["steps"]["categories"] = page.locator(".tastes button.taste").count()
          page.locator(".tastes button.taste:has-text('해변')").click(); time.sleep(0.3); res["steps"]["dest_first_with_beach_taste"] = page.locator(".destlist .card.dest").first.inner_text().split("\n")[0][:30]
          res["steps"]["dest_recommended"] = page.locator(".destlist .card.dest .chip.rec").count()
          res["steps"]["dest_rec_why"] = page.locator(".destlist .card.dest .recwhy").first.inner_text()[:70]
          page.click("button.reconly"); time.sleep(0.3); res["steps"]["dest_beach"] = page.locator(".destlist .card.dest").count(); page.click("button.reconly")
          page.click(".sortseg button:has-text('취향순')"); time.sleep(0.3); res["steps"]["dest_first_taste_sort"] = page.locator(".destlist .card.dest").first.inner_text().split("\n")[0][:30]; page.click(".sortseg button:has-text('인기순')")
          page.click("button.poponly"); time.sleep(0.3); res["steps"]["dest_poponly"] = page.locator(".destlist .card.dest").count(); page.click("button.poponly"); page.locator(".tastes button.taste:has-text('해변')").click()
          tastes = page.locator(".tastes button.taste"); tastes.nth(2).click(); tastes.nth(0).click()
          page.fill("input[placeholder*='여행지 검색']", "madrid"); time.sleep(0.4)
          res["steps"]["city_hits"] = [x.strip().split("\n")[0][:40] for x in page.locator(".destlist .card.dest .title").all_inner_texts()][:4]
          page.locator(".destlist .card.dest .pick").first.click(); time.sleep(0.2)
          res["steps"]["city_chip"] = page.locator(".picked .chip.on").first.inner_text()
          page.screenshot(path=str(shots / "s1_dest.png"))
          page.click(".stepnav .btn:has-text('다음')"); page.wait_for_selector(".airport", timeout=5000); res["steps"]["s1_step3"] = True
          # S1 ③ 공항(D-029): 검색 → 첫 제안 선택, 여행 형태
          page.locator("input[placeholder*='공항 검색']").first.fill("madrid"); page.wait_for_selector(".airport .chips button.chip", timeout=5000)
          res["steps"]["airport_hits"] = [x.strip()[:70] for x in page.locator(".airport .chips button.chip").all_inner_texts()][:3]; page.locator(".airport .chips button.chip").first.click()
          res["steps"]["airport_in"] = page.locator(".airport .chip.on").first.inner_text()
          page.screenshot(path=str(shots / "s1_tastes.png"))
          page.click("text=장소 고르러 가기"); page.wait_for_selector(".card", timeout=30000); time.sleep(1)
          res["steps"]["summary_cards"] = page.locator(".card").count(); res["steps"]["summary_profile"] = page.locator(".section p").first.inner_text()[:80]
          page.screenshot(path=str(shots / "s2.png"))
          page.wait_for_selector(".recprev .recrow", timeout=20000); res["steps"]["summary_rec_preview"] = page.locator(".recprev .recrow").count(); res["steps"]["summary_addall"] = page.locator("button.addall").first.inner_text()
          page.locator(".card .btn.explore").first.click(); page.wait_for_selector(".toolbar .seg", timeout=10000); time.sleep(2)
          res["steps"]["rec_cards"] = page.locator(".card").count(); res["steps"]["rec_first"] = page.locator(".card .title").first.inner_text() if page.locator(".card").count() else None
          res["steps"]["rec_note"] = page.locator("p.note").first.inner_text()[:100]
          res["steps"]["rec_bundles"] = page.locator("h3.bundlehead").all_inner_texts()
          page.screenshot(path=str(shots / "s3_rec.png"))
          page.click("text=대안 ▸"); page.wait_for_selector(".sheet", timeout=10000); res["steps"]["alt_rows"] = page.locator(".sheet .row").count(); page.click(".sheet .close")
          page.click("button:has-text('전체 후보')"); page.wait_for_selector(".card", timeout=30000); time.sleep(1)
          res["steps"]["cards"] = page.locator(".card").count(); res["steps"]["note"] = page.locator(".note").first.inner_text()[:120]
          res["steps"]["map_canvas"] = page.locator(".map canvas").count()
          page.screenshot(path=str(shots / "s3.png"))
          # 범주 필터와 검색
          page.locator(".toolbar.chips button").nth(2).click(); time.sleep(0.5); res["steps"]["cards_filtered"] = page.locator(".card").count(); page.locator(".toolbar.chips button").nth(2).click()
          page.fill("input[placeholder='장소 이름 검색']", "prado"); time.sleep(0.5); res["steps"]["cards_prado"] = page.locator(".card").count()
          res["steps"]["first_title"] = page.locator(".card .title").first.inner_text()
          page.locator(".card").first.click(); page.wait_for_selector(".sheet", timeout=10000); time.sleep(1.5)
          res["steps"]["detail_title"] = page.locator(".sheet h2").inner_text(); res["steps"]["detail_text"] = page.locator(".sheet").inner_text()[:400]
          res["steps"]["detail_gmaps"] = [f"{a.inner_text()} → {a.get_attribute('href')[42:]}" for a in page.locator(".sheet a[href*='maps/search']").all()]  # 이름+도시 검색, 좌표(D-035)
          res["steps"]["detail_desc_heading"] = page.locator(".sheet .desc-h").inner_text().replace("\n", " ")  # 설명이 아직 없는 장소는 "생성 전"
          page.screenshot(path=str(shots / "s6.png"))
          page.click(".sheet .btn:has-text('선택')"); time.sleep(0.3); page.click(".sheet .close")
          # S4: 선택한 장소를 1일에 배치, 숙박 탭
          page.click("nav.tabs button:has-text('일정')"); page.wait_for_selector(".arr .mini.place", timeout=10000)
          page.locator(".mini.place").first.click(); page.locator(".daybox[data-drop]:not(.none) .dayhead").first.click(); time.sleep(0.3)  # 장소를 집고 1일을 누른다(묶음 13)
          res["steps"]["day1_items"] = page.locator(".daybox[data-drop]:not(.none)").first.locator(".mini").count()
          page.click(".toolbar .seg button:has-text('숙박')"); page.wait_for_selector("input[type=number]", timeout=5000); res["steps"]["lodging_zones"] = page.locator(".chips button.chip").count()
          page.screenshot(path=str(shots / "s4.png"))
          page.click("button:has-text('장소 배치')"); page.click("button:has-text('일정 생성')"); page.wait_for_selector("text=이 날 재생성", timeout=60000); time.sleep(1)
          res["steps"]["itin_days"] = page.locator(".toolbar .chip").count(); res["steps"]["itin_items"] = page.locator(".card .title").count(); res["steps"]["itin_note"] = page.locator("p.note").first.inner_text()[:120]
          page.screenshot(path=str(shots / "s5.png"))
          page.click("button:has-text('비용 €')"); page.wait_for_selector(".sheet", timeout=10000); res["steps"]["cost_total"] = page.locator(".sheet p").first.inner_text()[:60]; page.screenshot(path=str(shots / "s5_cost.png")); page.click(".sheet .close")
          page.click("nav.tabs button:has-text('공유')"); page.wait_for_selector("text=구글맵 일괄 저장", timeout=5000)
          res["steps"]["share_links"] = page.locator("a[href*='maps/dir']").count(); res["steps"]["share_limit"] = page.locator("p.note").first.inner_text()[:100]
          page.screenshot(path=str(shots / "s7.png"))
          page.click("nav.tabs button:has-text('설정')"); page.wait_for_selector("text=출처 표기", timeout=5000)
          page.fill("input[placeholder*='trip-2027']", "assuii0311-dot/Trip---01"); page.click("button:has-text('연결 확인')"); page.wait_for_selector("text=연결됨:", timeout=30000)
          res["steps"]["gh_check"] = page.locator("p.note:has-text('연결됨')").inner_text()[:80]
          page.screenshot(path=str(shots / "s8.png"))
          res["steps"]["tabs"] = page.locator("nav.tabs button").count()
          # --- 섬 여행지 흐름(D-030): 마요르카섬 선택 → 요약 → 추천·전체 후보 → 장소 선택 → 숙박 구역 → 일정 생성
          ctx2 = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR"); pg = ctx2.new_page(); isl = {}
          isl["missing_files_404"] = 0  # 이동 시간 파일이 없는 지자체의 404는 세기만 한다(직선 추정으로 대체되는 정상 동작)
          def on_console(m):
              if m.type != "error": return
              if "404" in m.text: isl["missing_files_404"] += 1
              else: res["console_errors"].append("island: " + m.text)
          pg.on("console", on_console)
          pg.on("pageerror", lambda e: res["console_errors"].append(f"island pageerror: {e}"))
          pg.goto(url, wait_until="networkidle", timeout=60000); pg.wait_for_selector(".steps", timeout=30000)
          d2 = pg.locator("input[type=date]"); d2.nth(0).fill("2027-06-01"); d2.nth(1).fill("2027-06-05"); pg.click("text=다음 ▶"); pg.wait_for_selector(".destlist .card.dest", timeout=10000)
          pg.fill("input[placeholder*='여행지 검색']", "mallorca"); time.sleep(0.4); isl["card"] = pg.locator(".destlist .card.dest").first.inner_text().replace("\n", " | ")[:300]
          pg.locator(".destlist .card.dest .pick").first.click(); pg.screenshot(path=str(shots / "island_s1.png"))
          pg.click(".stepnav .btn:has-text('다음')"); pg.wait_for_selector(".airport", timeout=5000)
          pg.locator("input[placeholder*='공항 검색']").first.focus(); pg.wait_for_selector(".airport .chips button.chip", timeout=5000); isl["airport_first"] = pg.locator(".airport .chips button.chip").first.inner_text().split("\n")[0]
          pg.click("text=장소 고르러 가기"); pg.wait_for_selector(".card", timeout=30000); time.sleep(1)
          isl["summary"] = pg.locator(".card").first.inner_text().replace("\n", " | ")[:260]; pg.screenshot(path=str(shots / "island_s2.png"))
          pg.locator(".card .btn.explore").first.click(); pg.wait_for_selector(".toolbar .seg", timeout=10000); time.sleep(3)
          isl["rec_cards"] = pg.locator(".card").count(); isl["rec_note"] = pg.locator("p.note").first.inner_text()[:110]
          picks = pg.locator(".card button[aria-label='선택']"); [picks.nth(i).click() for i in range(min(5, picks.count()))]
          pg.click("button:has-text('전체 후보')"); pg.wait_for_selector(".card", timeout=30000); time.sleep(1.5); isl["all_note"] = pg.locator(".note").first.inner_text()[:110]; pg.screenshot(path=str(shots / "island_s3.png"))
          pg.click("nav.tabs button:has-text('일정')"); pg.wait_for_selector(".arr .mini.place", timeout=10000); isl["arrange_groups"] = pg.locator(".arr-cityhead h2").all_inner_texts()[:3]
          pg.click(".toolbar .seg button:has-text('숙박')"); pg.wait_for_selector("input[type=number]", timeout=5000); isl["lodging_zones"] = [x[:30] for x in pg.locator(".chips button.chip").all_inner_texts()][:3]
          pg.click("button:has-text('장소 배치')"); pg.click("button:has-text('일정 생성')"); pg.wait_for_selector("text=이 날 재생성", timeout=60000); time.sleep(1)
          isl["itin_note"] = pg.locator("p.note").first.inner_text()[:120]; isl["itin_items"] = pg.locator(".card .title").count(); pg.screenshot(path=str(shots / "island_s5.png"))
          res["island"] = isl; ctx2.close()
          # --- 장소 한국어 설명과 듣기(E5 4절 9항, D-033): 코르도바 → 전체 후보 → 생성 이름으로 검색 → 상세 → 듣기
          # 헤드리스 브라우저에는 음성이 없으므로 가짜 음성 합성기를 넣어 화면 연결만 확인한다(실제 소리는 기기에서 확인)
          ctx3 = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR"); e5 = {}
          ctx3.add_init_script("(() => { const log = []; const synth = { getVoices: () => [{ lang: 'ko-KR', localService: true, name: 'fake-ko' }], speak: (u) => log.push(u.text), cancel: () => log.push('<cancel>') };"
                               " Object.defineProperty(window, 'speechSynthesis', { value: synth, configurable: true }); window.SpeechSynthesisUtterance = function (t) { this.text = t; }; window.__speechLog = log; })();")
          pd = ctx3.new_page()
          pd.on("console", lambda m: res["console_errors"].append("e5: " + m.text) if m.type == "error" and "404" not in m.text else None)
          pd.on("pageerror", lambda e: res["console_errors"].append(f"e5 pageerror: {e}"))
          pd.goto(url, wait_until="networkidle", timeout=60000); pd.wait_for_selector(".steps", timeout=30000)
          d3 = pd.locator("input[type=date]"); d3.nth(0).fill("2027-04-01"); d3.nth(1).fill("2027-04-04"); pd.click("text=다음 ▶"); pd.wait_for_selector(".destlist .card.dest", timeout=10000)
          pd.fill("input[placeholder*='여행지 검색']", "cordoba"); time.sleep(0.4); e5["dest"] = pd.locator(".destlist .card.dest .title").first.inner_text().split("\n")[0][:30]
          pd.locator(".destlist .card.dest .pick").first.click(); pd.click(".stepnav .btn:has-text('다음')"); pd.wait_for_selector(".airport", timeout=5000)
          pd.click("text=장소 고르러 가기"); pd.wait_for_selector(".card", timeout=30000); time.sleep(1)
          pd.locator(".card .btn.explore").first.click(); pd.wait_for_selector(".toolbar .seg", timeout=10000); time.sleep(1.5)
          pd.click("button:has-text('전체 후보')"); pd.wait_for_selector(".card", timeout=30000); time.sleep(1)
          pd.fill("input[placeholder='장소 이름 검색']", "칼리프"); time.sleep(0.5); e5["search_hits"] = pd.locator(".card").count()
          pd.locator(".card").first.click(); pd.wait_for_selector(".sheet .desc-ko", timeout=10000)
          e5["title"] = pd.locator(".sheet h2").inner_text().replace("\n", " "); e5["heading"] = pd.locator(".sheet .desc-h").inner_text().replace("\n", " | ")
          e5["summary"] = pd.locator(".sheet .desc-ko > p").first.inner_text()[:80]
          pd.locator(".sheet .desc-ko summary").click(); e5["detail_paragraphs"] = pd.locator(".sheet .desc-ko details p").count()
          e5["source_links"] = pd.locator(".sheet .desc-ko .note a").count(); pd.locator(".sheet .desc-ko").scroll_into_view_if_needed(); pd.screenshot(path=str(shots / "s6_ko.png"))
          pd.click(".sheet .speak"); time.sleep(0.2); e5["speak_button_after_click"] = pd.locator(".sheet .speak").inner_text()
          log = pd.evaluate("window.__speechLog"); spoken = [x for x in log if x != "<cancel>"]
          e5["spoken_chunks"] = len(spoken); e5["spoken_first"] = spoken[:2]; e5["spoken_has_latin_parens"] = any("(" in x and any("a" <= ch.lower() <= "z" for ch in x[x.index("("):]) for x in spoken)
          pd.click(".sheet .speak"); time.sleep(0.2); e5["speak_button_after_stop"] = pd.locator(".sheet .speak").inner_text(); e5["cancel_calls"] = pd.evaluate("window.__speechLog").count("<cancel>")
          res["e5_place"] = e5; ctx3.close()
      finally:
        try: page.screenshot(path=str(shots / "last.png"))
        except Exception: pass
        b.close()
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
