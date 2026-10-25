#!/usr/bin/env python3
"""앱 흐름 점검(와이어프레임 검증 항목). 이 환경의 Chromium으로 로컬 사이트를 열어 S1 → S3 → S6 흐름과 콘솔 오류를 확인한다.
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
          # S1: 기간, 도시 검색, 인원 → 다음
          dates = page.locator("input[type=date]"); dates.nth(0).fill("2027-05-01"); dates.nth(1).fill("2027-05-10")
          page.fill("input[placeholder*='도시 이름']", "madrid"); page.wait_for_selector(".chips button.chip", timeout=5000)
          res["steps"]["city_hits"] = [x.strip()[:40] for x in page.locator(".chips button.chip").all_inner_texts()][:4]; page.locator(".chips button.chip").first.click()
          res["steps"]["city_chip"] = page.locator(".chip.on").first.inner_text()
          page.click("text=다음 ▶"); page.wait_for_selector(".seg", timeout=5000); res["steps"]["s1_step2"] = True
          page.click("text=다음 ▶"); page.wait_for_selector(".cats", timeout=5000)
          cats = page.locator(".catcard"); res["steps"]["categories"] = cats.count(); cats.nth(2).click(); cats.nth(0).click()
          page.screenshot(path=str(shots / "s1_tastes.png"))
          page.click("text=탐색으로 ▶"); page.wait_for_selector(".card", timeout=30000); time.sleep(2)
          res["steps"]["cards"] = page.locator(".card").count(); res["steps"]["note"] = page.locator(".note").first.inner_text()[:120]
          res["steps"]["map_canvas"] = page.locator(".map canvas").count()
          page.screenshot(path=str(shots / "s3.png"))
          # 범주 필터와 검색
          page.locator(".toolbar.chips button").nth(2).click(); time.sleep(0.5); res["steps"]["cards_filtered"] = page.locator(".card").count(); page.locator(".toolbar.chips button").nth(2).click()
          page.fill("input[placeholder='장소 이름 검색']", "prado"); time.sleep(0.5); res["steps"]["cards_prado"] = page.locator(".card").count()
          res["steps"]["first_title"] = page.locator(".card .title").first.inner_text()
          page.locator(".card").first.click(); page.wait_for_selector(".sheet", timeout=10000); time.sleep(1.5)
          res["steps"]["detail_title"] = page.locator(".sheet h2").inner_text(); res["steps"]["detail_text"] = page.locator(".sheet").inner_text()[:400]
          page.screenshot(path=str(shots / "s6.png"))
          page.click(".sheet .close"); page.click("nav.tabs button:has-text('설정')"); page.wait_for_selector("text=출처 표기", timeout=5000); page.screenshot(path=str(shots / "s8.png"))
          res["steps"]["tabs"] = page.locator("nav.tabs button").count()
      finally:
        try: page.screenshot(path=str(shots / "last.png"))
        except Exception: pass
        b.close()
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
