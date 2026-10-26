#!/usr/bin/env python3
"""2단계 PoC D 단계: 검수 표본을 구글맵에서 한 번씩 이름 검색해 1차 판정을 채운다 (D-018).

- 주소는 robots.txt가 허용하는 /maps?q= 형식만 쓴다. 장소당 1회, 요청 간 5초 이상.
- 결과 패널에서 명칭, 분류, 플러스 코드(위치 부호), 영업 상태를 읽고, 플러스 코드를 좌표로 풀어 우리 좌표와의 거리를 잰다.
- 구글 콘텐츠는 저장하지 않고 판정(O, X, ?)과 근거 요약만 기록한다. ?와 X 항목은 화면을 저장해 사용자 확인에 쓴다.

실행: python poc/review_gmaps.py <표본 JSON> <판정 JSON 출력> <화면 디렉터리> [--limit N]
"""
import difflib
import json
import math
import pathlib
import re
import sys
import time
import unicodedata
from urllib.parse import quote_plus

from openlocationcode import openlocationcode as olc
from playwright.sync_api import sync_playwright

EXE = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
PAUSE = 5.0
CAT_GROUP = {
    "식당": ["restaurant", "bar", "cafe", "coffee", "pub", "tapas", "pizza", "burger", "kebab", "sushi", "bakery", "diner", "grill", "bistro", "brasserie", "food", "cafeteria", "ice cream", "market"],
    "숙박": ["hotel", "hostel", "hostal", "guest house", "inn", "lodging", "campground", "camping", "apartment", "bed & breakfast", "motel", "resort", "pension", "holiday"],
    "자연": ["park", "beach", "mountain", "peak", "garden", "nature", "forest", "lake", "river", "hiking", "trail", "scenic", "viewpoint", "cave", "waterfall", "reserve", "hill"],
    "볼거리": ["museum", "church", "cathedral", "chapel", "monument", "castle", "palace", "historical", "landmark", "tourist", "art", "gallery", "theater", "theatre", "plaza", "square", "bridge", "tower", "ruins", "archaeological", "hermitage", "monastery", "basilica", "sculpture", "statue", "fountain", "cultural", "library", "city hall", "town hall", "market", "lighthouse", "stadium", "zoo", "aquarium", "attraction", "place of worship", "religious", "shrine", "mill", "winery"],
}


SYN = {"parque": "park", "parc": "park", "iglesia": "church", "esglesia": "church", "eliza": "church", "playa": "beach", "platja": "beach",
       "museo": "museum", "museu": "museum", "castillo": "castle", "castell": "castle", "puente": "bridge", "pont": "bridge", "plaza": "square",
       "placa": "square", "mercado": "market", "mercat": "market", "catedral": "cathedral", "ermita": "hermitage", "monasterio": "monastery",
       "palacio": "palace", "palau": "palace", "torre": "tower", "jardin": "garden", "jardi": "garden", "monumento": "monument", "fuente": "fountain",
       "font": "fountain", "faro": "lighthouse", "estacion": "station", "estacio": "station", "ayuntamiento": "town hall", "ajuntament": "town hall",
       "restaurante": "restaurant", "cafeteria": "cafe", "hostal": "hostel", "pension": "guesthouse", "camping": "campground", "montana": "mountain",
       "muntanya": "mountain", "turo": "hill", "cueva": "cave", "cova": "cave", "molino": "mill", "moli": "mill", "santa": "st", "san": "st", "sant": "st"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"[^a-z0-9ñ ]+", " ", s)
    s = re.sub(r"\b(el|la|los|las|de|del|the|of|y|e|i|a|en|d|l|des|dels)\b", " ", s)
    words = [SYN.get(w, w) for w in s.split()]
    return " ".join(words).strip()


def sim(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b or a in b or b in a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def hav(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    dlat, dlon = (lat2 - lat1) * p, (lon2 - lon1) * p
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dlon / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def cat_group(cat):
    c = (cat or "").lower()
    for g, words in CAT_GROUP.items():
        if any(w in c for w in words):
            return g
    return None


def lookup(pg, query):
    url = f"https://www.google.com/maps?q={quote_plus(query)}&hl=en"
    pg.goto(url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)
    if "consent" in pg.url:
        for sel in ("button:has-text('Accept all')", "button:has-text('Reject all')"):
            try:
                pg.locator(sel).first.click(timeout=3000)
                break
            except Exception:
                pass
        time.sleep(4)

    def txt(sel):
        try:
            return pg.locator(sel).first.inner_text(timeout=2500).strip()
        except Exception:
            return None
    h1 = txt("h1")
    category = txt("button[jsaction*='category']")
    if not category:
        try:
            head = pg.locator("div[role='main']").first.inner_text(timeout=3000)[:400]
            m = re.search(r"\b(\d-star hotel|hotel|hostel|hostal|guest house|campground|apartment|inn|motel|resort|bed & breakfast|restaurant|bar|cafe|park|beach|church|museum)\b", head, re.I)
            category = m.group(1) if m else None
        except Exception:
            category = None
    res = {"query": query, "name": h1, "category": category, "plus": txt("[data-item-id='oloc']"),
           "status": txt("span:has-text('Open'), span:has-text('Closed'), span:has-text('closed')")}
    if h1 and h1.lower() in ("results", "google maps") or (h1 and "results" in h1.lower()):
        res["name"] = None  # 목록 화면: 단일 결과 아님
        res["multiple"] = True
    try:
        res["rating_count"] = pg.locator("span[aria-label*='reviews' i]").first.get_attribute("aria-label", timeout=2000)
    except Exception:
        res["rating_count"] = None
    return res


def decode_plus(plus, ref_lat, ref_lon):
    if not plus:
        return None
    m = re.search(r"([23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,3})", plus.upper())  # 앞에 아이콘 문자가 붙어 있어 search
    if not m:
        return None
    try:
        full = olc.recoverNearest(m.group(1), ref_lat, ref_lon)
        d = olc.decode(full)
        return (d.latitudeCenter, d.longitudeCenter)
    except Exception:
        return None


def judge(place, city_name, res):
    ours = (place["osm"] and place["osm"]["name"]) or (place["wd"] and (place["wd"]["label_es"] or place["wd"]["label_en"])) or (place["wv"] and place["wv"]["name"])
    j = {"명칭": "?", "좌표": "?", "분류": "?", "영업시간": "해당 없음", "근거": []}
    if not res.get("name"):
        j["근거"].append("구글맵에 단일 결과 없음" + (" (목록 화면)" if res.get("multiple") else ""))
        return j
    s = sim(ours, res["name"])
    pt = decode_plus(res.get("plus"), place["lat"], place["lon"])
    dist = hav(place["lat"], place["lon"], pt[0], pt[1]) if pt else None
    j["구글 명칭"] = res["name"]
    j["구글 분류"] = res.get("category")
    j["거리 m"] = round(dist) if dist is not None else None
    j["유사도"] = round(s, 2)
    if s >= 0.6:
        j["명칭"] = "O"
    elif s < 0.4 and dist is not None and dist > 500:
        j["명칭"] = "X"; j["근거"].append("다른 장소가 검색됨")
    else:
        j["근거"].append("명칭 유사도 낮음")
    if dist is None:
        j["근거"].append("위치 부호 없음")
    elif dist <= 150:
        j["좌표"] = "O"
    elif dist <= 500:
        j["근거"].append(f"거리 {round(dist)}m")
    else:
        j["좌표"] = "X" if j["명칭"] == "O" else "?"
        j["근거"].append(f"거리 {round(dist)}m")
    g = cat_group(res.get("category"))
    if g is None:
        j["근거"].append("분류 미확인")
    elif g == place["group"] or (place["group"] == "자연" and g == "볼거리") or (place["group"] == "볼거리" and g == "자연"):
        j["분류"] = "O"
    else:
        j["분류"] = "X"; j["근거"].append(f"구글 분류 {res.get('category')}")
    ours_hours = (place["osm"] and place["osm"].get("opening_hours")) or (place["wv"] and place["wv"].get("has_hours"))
    if ours_hours:
        j["영업시간"] = "?"
        j["근거"].append("영업시간은 사용자 확인 필요" + (f" (구글 상태: {res['status'][:40]})" if res.get("status") else ""))
    return j


def main():
    sample, out, shots = json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2], pathlib.Path(sys.argv[3])
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    shots.mkdir(parents=True, exist_ok=True)
    results = {"places": [], "cities": [], "p17": {}}
    n = 0
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=EXE)
        ctx = b.new_context(viewport={"width": 1280, "height": 900}, locale="en-US", user_agent=UA)
        pg = ctx.new_page()
        for ci, city in enumerate(sample["cities"], 1):
            cres = lookup(pg, f"{city['name_es']}, Spain")
            results["cities"].append({"city": city["name_es"], "stratum": city["stratum"], "구글 명칭": cres.get("name"), "구글 분류": cres.get("category"),
                                      "위키 en": city["wiki"]["enwiki"], "위키 ko": city["wiki"]["kowiki"]})
            time.sleep(PAUSE)
            for pi, place in enumerate(city["places"], 1):
                if limit and n >= limit:
                    break
                n += 1
                ours = (place["osm"] and place["osm"]["name"]) or (place["wd"] and (place["wd"]["label_es"] or place["wd"]["label_en"])) or (place["wv"] and place["wv"]["name"])
                res = lookup(pg, f"{ours}, {city['name_es']}")
                j = judge(place, city["name_es"], res)
                pid = f"{ci}-{pi}"
                if "?" in (j["명칭"], j["좌표"], j["분류"]) or "X" in (j["명칭"], j["좌표"], j["분류"]) or j["영업시간"] == "?":
                    pg.screenshot(path=str(shots / f"{pid}.png"))
                    j["화면"] = f"{pid}.png"
                results["places"].append({"id": pid, "city": city["name_es"], "stratum": city["stratum"], "ours": ours, "group": place["group"], "status": place["status"], **j})
                print(f"  {pid} {ours[:40]:40} 명칭 {j['명칭']} 좌표 {j['좌표']} 분류 {j['분류']} 시간 {j['영업시간']} | {j.get('구글 명칭','')[:30]} {j.get('거리 m','')}m", flush=True)
                time.sleep(PAUSE)
            if limit and n >= limit:
                break
        if not limit:
            for city, d in sample["p17"].items():
                rows = []
                for tag, lst in (("상위", d["top"]), ("하위", d["bottom"])):
                    for r in lst:
                        res = lookup(pg, f"{r['name']}, {city}")
                        rows.append({"구분": tag, "장소": r["name"], "en": r["en"], "es": r["es"], "비중": r["share"], "구글 분류": res.get("category"), "리뷰 수": res.get("rating_count")})
                        print(f"  P-17 {city} {tag} {r['name'][:35]:35} → {res.get('category')} {res.get('rating_count')}", flush=True)
                        time.sleep(PAUSE)
                results["p17"][city] = rows
        b.close()
    json.dump(results, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  완료: 장소 {len(results['places'])}, 도시 {len(results['cities'])}, P-17 도시 {len(results['p17'])}")


if __name__ == "__main__":
    main()
