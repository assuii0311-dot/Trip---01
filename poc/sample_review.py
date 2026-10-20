#!/usr/bin/env python3
"""2단계 PoC D 단계: 품질 검수 표본을 뽑고 검수표(Markdown)를 만든다.

- 층: 대도시(인구 10만 이상), 중소 관광 도시(10만 미만, Wikivoyage 도시 문서와 목록 5건 이상),
  데이터 빈약 소도시(2만 미만, Wikivoyage 문서 없거나 목록 5건 미만, 중심 3km 안 OSM 장소 10건 이상)
- 고정 난수(seed)로 층마다 도시 2곳, 도시마다 장소 6곳(볼거리 2, 식당 2, 숙박 1, 자연 1. 부족하면 다른 유형으로 채움)
- 장소마다 출처별 명칭, 좌표와 구글맵 링크, 분류, 영업시간, 가격, 설명 출처, 교차검증 상태, 조회수를 싣는다.
- 대도시 2곳은 스페인어 조회 비중 상위 10곳과 하위 10곳도 싣는다(P-17 타당성 검수용).

실행: python -I poc/sample_review.py <데이터 루트> <표본 JSON 출력> <검수표 Markdown 출력>
"""
import collections
import json
import pathlib
import random
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from crossval_match import Grid, CELL, best_name_match, hav, parse_point, sim  # noqa: E402

SEED = 20261020
RADIUS_CITY = 3000.0
FOOD = {"restaurant", "cafe", "bar", "pub", "fast_food", "ice_cream", "food_court", "biergarten", "marketplace"}
ACCOM = {"hotel", "hostel", "guest_house", "apartment", "motel", "chalet", "camp_site", "alpine_hut", "caravan_site"}
WD_CLASS_NAME = {"Q570116": "관광 명소", "Q33506": "박물관", "Q207694": "미술관", "Q16970": "교회 건물", "Q2977": "대성당", "Q44613": "수도원",
                 "Q23413": "성", "Q16560": "궁전", "Q4989906": "기념물", "Q839954": "고고 유적", "Q15243209": "역사 지구", "Q22698": "공원",
                 "Q1107656": "정원", "Q46169": "국립공원", "Q179049": "자연 보호구역", "Q40080": "해변", "Q8502": "산", "Q35509": "동굴",
                 "Q23397": "호수", "Q174782": "광장", "Q330284": "시장", "Q24354": "극장", "Q483110": "경기장", "Q43501": "동물원",
                 "Q39715": "등대", "Q12280": "다리", "Q1248784": "공항", "Q55488": "철도역", "Q11315": "쇼핑몰", "Q11707": "식당",
                 "P1435": "문화유산 지정", "Q2074737": "지자체", "Q515": "도시", "Q3957": "소도시", "Q532": "마을"}
NATURAL_CLS = {"Q22698", "Q1107656", "Q46169", "Q179049", "Q40080", "Q8502", "Q35509", "Q23397"}
MUNI_CLS = {"Q2074737", "Q515", "Q3957", "Q532"}


SIGHT_TOURISM = {"attraction", "museum", "viewpoint", "artwork", "gallery", "theme_park", "zoo", "aquarium", "yes"}
SIGHT_AMENITY = {"place_of_worship", "theatre", "arts_centre", "marketplace", "fountain", "cinema", "library", "townhall"}


def group_of(cand):
    """볼거리, 식당, 숙박, 자연, 상점, 기타 중 하나. 기타는 표본에서 제외한다."""
    o, w, v = cand.get("osm"), cand.get("wd"), cand.get("wv")
    if o:
        if o["key"] == "amenity" and o["value"] in FOOD:
            return "식당"
        if o["key"] == "tourism" and o["value"] in ACCOM:
            return "숙박"
        if o["key"] in ("natural",) or (o["key"] == "leisure" and o["value"] in ("park", "garden", "nature_reserve", "beach_resort")):
            return "자연"
        if o["key"] == "shop":
            return "상점"
        if o["key"] == "historic" or (o["key"] == "tourism" and o["value"] in SIGHT_TOURISM) or (o["key"] == "amenity" and o["value"] in SIGHT_AMENITY) or w or v:
            return "볼거리"
        return "기타"
    if v:
        return {"eat": "식당", "drink": "식당", "sleep": "숙박", "buy": "상점"}.get(v["type"], "볼거리")
    if w:
        return "자연" if w["cls"] & NATURAL_CLS else "볼거리"
    return "볼거리"


def gmaps(lat, lon):
    return f"https://www.google.com/maps/search/?api=1&query={lat:.5f},{lon:.5f}"


def main():
    root, out_json, out_md = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    rnd = random.Random(SEED)
    # --- 로드 ---
    wd = {}
    for f in (root / "wikidata").glob("*.jsonl"):
        if f.name == "sitelinks.jsonl":
            continue
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            q = r["qid"]
            if q in wd:
                wd[q]["cls"].add(r["cls"])
                for k in ("coord", "label_es", "label_en", "label_ko", "pop", "sitelinks"):
                    if not wd[q].get(k) and r.get(k):
                        wd[q][k] = r[k]
            else:
                r["cls"] = {r["cls"]}
                wd[q] = r
    links = {json.loads(l)["qid"]: json.loads(l) for l in open(root / "wikidata" / "sitelinks.jsonl", encoding="utf-8")}
    for q, r in wd.items():
        r["pt"] = parse_point(r.get("coord"))
        lk = links.get(q, {})
        for k in ("label_es", "label_en", "label_ko"):
            if not r.get(k) and lk.get(k):
                r[k] = lk[k]
    views = {json.loads(l)["qid"]: json.loads(l) for l in open(root / "pageviews" / "views.jsonl", encoding="utf-8")}
    osm, ogrid, osm_by_q = [], Grid(), collections.defaultdict(list)
    for line in open(root / "osm" / "out" / "pois.jsonl", encoding="utf-8"):
        o = json.loads(line)
        osm.append(o)
        ogrid.add(o["lat"], o["lon"], o)
        if o.get("wikidata"):
            for q in o["wikidata"].split(";"):
                if q.strip().startswith("Q"):
                    osm_by_q[q.strip()].append(o)
    wgrid = Grid()
    for q, r in wd.items():
        if r["pt"] and not (r["cls"] & MUNI_CLS):
            wgrid.add(r["pt"][0], r["pt"][1], {"lat": r["pt"][0], "lon": r["pt"][1], "name": r.get("label_es") or r.get("label_en"), "qid": q})
    pages = {json.loads(l)["title"]: json.loads(l) for l in open(root / "wikivoyage_en" / "out" / "pages.jsonl", encoding="utf-8")}
    wv_by_page = collections.defaultdict(list)
    for line in open(root / "wikivoyage_en" / "out" / "listings.jsonl", encoding="utf-8"):
        x = json.loads(line)
        try:
            x["pt"] = (float(x["lat"]), float(x["long"])) if x.get("lat") and x.get("long") else None
        except ValueError:
            x["pt"] = None
        wv_by_page[x["page"]].append(x)

    def near(grid, lat, lon, radius):
        cells = int(radius / 550) + 1
        ci, cj = int(lat // CELL), int(lon // CELL)
        for i in range(ci - cells, ci + cells + 1):
            for j in range(cj - cells, cj + cells + 1):
                for it in grid.cells.get((i, j), ()):
                    if hav(lat, lon, it["lat"], it["lon"]) <= radius:
                        yield it

    # --- 층 ---
    munis = {q: r for q, r in wd.items() if "Q2074737" in r["cls"] and r["pt"]}
    strata = collections.defaultdict(list)
    for q, r in munis.items():
        pop = float(r["pop"]) if r.get("pop") else None
        t = links.get(q, {}).get("wv_en")
        n_list = sum(pages[t]["listings"].values()) if t and t in pages else 0
        if pop is not None and pop >= 100000:
            strata["대도시"].append(q)
        elif t and t in pages and pages[t]["kind"] == "city" and n_list >= 5 and (pop is None or pop < 100000):
            strata["중소 관광 도시"].append(q)
        elif pop is not None and pop < 20000 and (not t or n_list < 5):
            strata["데이터 빈약 소도시"].append(q)
    print(f"  층별 지자체: " + ", ".join(f"{k} {len(v)}" for k, v in strata.items()))
    chosen = {}
    for name in ("대도시", "중소 관광 도시", "데이터 빈약 소도시"):
        pool = sorted(strata[name])
        rnd.shuffle(pool)
        picked = []
        for q in pool:
            r = munis[q]
            n_osm = sum(1 for _ in near(ogrid, r["pt"][0], r["pt"][1], RADIUS_CITY))
            if name == "데이터 빈약 소도시" and n_osm < 10:
                continue
            picked.append(q)
            if len(picked) == 2:
                break
        chosen[name] = picked
        print(f"  {name}: " + ", ".join(munis[q].get("label_es") or q for q in picked))

    # --- 도시별 후보와 표본 ---
    sample = []
    p17 = {}
    for stratum, qs in chosen.items():
        for cq in qs:
            city = munis[cq]
            clat, clon = city["pt"]
            t = links.get(cq, {}).get("wv_en")
            cands = {}
            # OSM 기반 후보
            for o in near(ogrid, clat, clon, RADIUS_CITY):
                c = {"osm": o, "lat": o["lat"], "lon": o["lon"]}
                qid = next((q.strip() for q in (o.get("wikidata") or "").split(";") if q.strip() in wd), None)
                if qid:
                    c["wd"] = wd[qid]; c["qid"] = qid; c["wd_how"] = "key"
                else:
                    b = best_name_match(near(wgrid, o["lat"], o["lon"], 150), o["lat"], o["lon"], [o.get("name")])
                    if b:
                        c["wd"] = wd[b[0]["qid"]]; c["qid"] = b[0]["qid"]; c["wd_how"] = "geo+name"
                cands[o["id"]] = c
            # Wikidata만 있는 후보
            osm_qids = {c.get("qid") for c in cands.values() if c.get("qid")}
            for w in near(wgrid, clat, clon, RADIUS_CITY):
                if w["qid"] not in osm_qids:
                    r = wd[w["qid"]]
                    cands["wd:" + w["qid"]] = {"wd": r, "qid": w["qid"], "lat": r["pt"][0], "lon": r["pt"][1]}
            # Wikivoyage 목록 연결
            for x in wv_by_page.get(t, []) if t else []:
                attached = False
                if x.get("wikidata"):
                    for c in cands.values():
                        if c.get("qid") == x["wikidata"]:
                            c["wv"] = x; attached = True; break
                if not attached and x["pt"]:
                    pool = [c for c in cands.values() if hav(x["pt"][0], x["pt"][1], c["lat"], c["lon"]) <= 150]
                    best = None
                    for c in pool:
                        names = [c["osm"].get("name") if c.get("osm") else None, c["wd"].get("label_es") if c.get("wd") else None, c["wd"].get("label_en") if c.get("wd") else None]
                        s = max(sim(x["name"], n) for n in names if n) if any(names) else 0
                        if s >= 0.6 and (best is None or s > best[1]):
                            best = (c, s)
                    if best:
                        best[0]["wv"] = x; attached = True
                if not attached:
                    key = "wv:" + x["name"]
                    cands[key] = {"wv": x, "lat": x["pt"][0] if x["pt"] else clat, "lon": x["pt"][1] if x["pt"] else clon, "no_coord": x["pt"] is None}
            # 상태와 유형
            for c in cands.values():
                srcs = sum(1 for k in ("osm", "wd", "wv") if c.get(k))
                conflict = False
                if c.get("osm") and c.get("wd") and c.get("wd_how") == "key" and c["wd"]["pt"]:
                    d = hav(c["lat"], c["lon"], c["wd"]["pt"][0], c["wd"]["pt"][1])
                    s = max(sim(c["wd"].get("label_es"), c["osm"].get("name")), sim(c["wd"].get("label_en"), c["osm"].get("name")))
                    if d > 500 or (s < 0.4 and (c["wd"].get("label_es") or c["wd"].get("label_en"))):
                        conflict = True
                c["status"] = "불일치" if conflict else ("일치" if srcs >= 2 else "단일 출처")
                c["group"] = group_of(c)
            by_group = collections.defaultdict(list)
            for k, c in cands.items():
                by_group[c["group"]].append((k, c))
            def has_name(c):
                return bool((c.get("osm") and c["osm"].get("name")) or (c.get("wd") and (c["wd"].get("label_es") or c["wd"].get("label_en"))) or (c.get("wv") and c["wv"].get("name")))

            def pick(g, n):
                pool = [kc for kc in sorted(by_group[g], key=lambda kc: kc[0]) if has_name(kc[1])]
                multi = [kc for kc in pool if kc[1]["status"] != "단일 출처"]
                single = [kc for kc in pool if kc[1]["status"] == "단일 출처"]
                rnd.shuffle(multi); rnd.shuffle(single)
                want_multi = min(len(multi), (n + 1) // 2)
                out = multi[:want_multi] + single[:n - want_multi]
                if len(out) < n:
                    out += multi[want_multi:want_multi + (n - len(out))]
                return out

            quota = [("볼거리", 2), ("식당", 2), ("숙박", 1), ("자연", 1)]
            picked = []
            for g, n in quota:
                picked += pick(g, n)
            if len(picked) < 6:
                rest = [kc for g in ("볼거리", "식당", "상점", "자연", "숙박") for kc in sorted(by_group[g], key=lambda kc: kc[0]) if kc not in picked and has_name(kc[1])]
                rnd.shuffle(rest)
                picked += rest[:6 - len(picked)]
            n_by_group = {g: len(v) for g, v in by_group.items()}
            city_rec = {"stratum": stratum, "qid": cq, "name_es": city.get("label_es"), "name_en": city.get("label_en"), "name_ko": city.get("label_ko"),
                        "pop": city.get("pop"), "lat": clat, "lon": clon, "gmaps": gmaps(clat, clon), "wv_page": t,
                        "understand_len": pages[t]["understand_len"] if t and t in pages else 0,
                        "wiki": {k: links.get(cq, {}).get(k) for k in ("enwiki", "eswiki", "kowiki")},
                        "views": views.get(cq), "candidates": len(cands), "candidates_by_group": n_by_group, "places": []}
            for k, c in picked[:6]:
                o, w, v = c.get("osm"), c.get("wd"), c.get("wv")
                lk = links.get(c.get("qid"), {}) if c.get("qid") else {}
                vw = views.get(c.get("qid")) if c.get("qid") else None
                city_rec["places"].append({
                    "key": k, "group": c["group"], "status": c["status"], "lat": c["lat"], "lon": c["lon"], "gmaps": gmaps(c["lat"], c["lon"]),
                    "no_coord": c.get("no_coord", False),
                    "osm": {"name": o.get("name"), "name_en": o.get("name:en"), "cat": f'{o["key"]}={o["value"]}', "opening_hours": o.get("opening_hours"),
                            "fee": o.get("fee"), "charge": o.get("charge"), "website": o.get("website"), "wikidata": o.get("wikidata")} if o else None,
                    "wd": {"qid": c.get("qid"), "label_es": w.get("label_es"), "label_en": w.get("label_en"), "label_ko": w.get("label_ko"),
                           "cls": [WD_CLASS_NAME.get(x, x) for x in sorted(w["cls"])], "how": c.get("wd_how"),
                           "enwiki": lk.get("enwiki"), "eswiki": lk.get("eswiki"), "kowiki": lk.get("kowiki"), "desc_en": lk.get("desc_en"), "desc_ko": lk.get("desc_ko")} if w else None,
                    "wv": {"name": v.get("name"), "type": v.get("type"), "has_hours": v.get("has_hours"), "has_price": v.get("has_price"),
                           "content_len": v.get("content_len"), "booking_text": v.get("booking_text")} if v else None,
                    "views": vw,
                })
            sample.append(city_rec)
    # --- P-17: 조회수 있는 장소(합계 500 이상)가 가장 많은 대도시 2곳 ---
    def viewed_rows(cq):
        clat, clon = munis[cq]["pt"]
        rows = []
        for w in near(wgrid, clat, clon, RADIUS_CITY):
            vw = views.get(w["qid"])
            if vw and vw["en"] + vw["es"] >= 500:
                r = wd[w["qid"]]
                rows.append({"name": r.get("label_es") or r.get("label_en"), "en": vw["en"], "es": vw["es"], "share": round(vw["es"] / (vw["en"] + vw["es"]), 2),
                             "group": "자연" if r["cls"] & NATURAL_CLS else "볼거리", "gmaps": gmaps(r["pt"][0], r["pt"][1])})
        return rows
    ranked = sorted(strata["대도시"], key=lambda q: -len(viewed_rows(q)))[:2]
    for cq in ranked:
        rows = sorted(viewed_rows(cq), key=lambda r: -r["share"])
        p17[munis[cq].get("label_es") or cq] = {"n": len(rows), "top": rows[:10], "bottom": rows[-10:][::-1]}
    print(f"  P-17 대상 대도시: " + ", ".join(f"{munis[q].get('label_es')}({len(viewed_rows(q))}곳)" for q in ranked))
    json.dump({"seed": SEED, "radius_m": RADIUS_CITY, "cities": sample, "p17": p17}, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # --- 검수표 Markdown ---
    def mark(x):
        return "있음" if x else "없음"
    L = []
    L.append("# 2단계 D 단계 품질 검수표\n")
    L.append("- 작성일: 2026-10-20. 고정 난수(seed 20261020)로 층마다 도시 2곳, 도시마다 장소 6곳을 뽑았다. 도시 중심 3km 안의 후보에서 뽑았다.")
    L.append("- 검수 방법: 각 장소의 구글맵 링크를 열어 확인하고 검수 항목에 O(맞음), X(틀림), ?(모름)를 적는다. 틀린 경우 비고에 무엇이 틀렸는지 한 줄 적는다.")
    L.append("- 검수 항목: 명칭(현지어 표기가 실제 명칭인가), 좌표(지도 위치가 그 장소인가), 분류(유형이 맞는가), 영업시간(있으면 맞는가), 설명 출처(링크된 문서가 그 장소인가), 상태(교차검증 판정이 맞는가).")
    L.append("- 결과 기록: 검수가 끝나면 이 파일을 그대로 수정하거나 답장으로 주시면 `docs/02-review-results.md`에 정리한다.\n")
    n_city = 0
    for c in sample:
        n_city += 1
        L.append(f"## {n_city}. [{c['stratum']}] {c['name_es'] or c['qid']}")
        L.append(f"- 명칭: es {c['name_es']} / en {c['name_en']} / ko {c['name_ko'] or '없음'}. 인구 {int(float(c['pop'])) if c.get('pop') else '미상'}명. [구글맵]({c['gmaps']})")
        L.append(f"- 지역 요약 출처: 영문 Wikivoyage 문서 {c['wv_page'] or '없음'} (개요 절 {c['understand_len']}자), 위키백과 en {mark(c['wiki']['enwiki'])} / es {mark(c['wiki']['eswiki'])} / ko {mark(c['wiki']['kowiki'])}" + (f" ({c['wiki']['kowiki']})" if c['wiki']['kowiki'] else ""))
        v = c.get("views")
        if v:
            L.append(f"- 2025년 9월 조회수: en {v['en']:,} / es {v['es']:,} / ko {v['ko']:,}")
        L.append(f"- 3km 안 후보 {c['candidates']}건 (유형별 {c['candidates_by_group']})")
        L.append("- 도시 검수: 요약 출처가 이 도시를 설명하는가 [  ]  비고: \n")
        for i, p in enumerate(c["places"], 1):
            o, w, x = p["osm"], p["wd"], p["wv"]
            title = (o and o["name"]) or (w and (w["label_es"] or w["label_en"])) or (x and x["name"]) or "(이름 없음)"
            L.append(f"### {n_city}-{i}. {title}  ·  {p['group']}  ·  {p['status']}")
            L.append(f"- 좌표: {p['lat']:.5f}, {p['lon']:.5f} [구글맵]({p['gmaps']})" + (" (Wikivoyage 좌표 없음, 도시 중심)" if p["no_coord"] else ""))
            if o:
                L.append(f"- OSM: 명칭 {o['name'] or '없음'}" + (f" / en {o['name_en']}" if o['name_en'] else "") + f", 분류 {o['cat']}, 영업시간 {o['opening_hours'] or '없음'}, 요금 {o['fee'] or o['charge'] or '없음'}" + (f", 웹 {o['website']}" if o['website'] else ""))
            else:
                L.append("- OSM: 없음")
            if w:
                L.append(f"- Wikidata {w['qid']} ({w['how'] or '좌표 매칭'}): es {w['label_es'] or '없음'} / en {w['label_en'] or '없음'} / ko {w['label_ko'] or '없음'}, 분류 {', '.join(w['cls'])}, 위키백과 en {mark(w['enwiki'])} es {mark(w['eswiki'])} ko {mark(w['kowiki'])}" + (f", 설명(en) {w['desc_en']}" if w['desc_en'] else ""))
            else:
                L.append("- Wikidata: 없음")
            if x:
                L.append(f"- Wikivoyage: {x['name']} ({x['type']}), 설명 {x['content_len']}자, 영업시간 {mark(x['has_hours'])}, 가격 {mark(x['has_price'])}, 예약 문구 {mark(x['booking_text'])}")
            else:
                L.append("- Wikivoyage: 없음")
            vw = p.get("views")
            if vw:
                L.append(f"- 조회수(9월): en {vw['en']:,} / es {vw['es']:,} / ko {vw['ko']:,}")
            L.append("- 검수: 명칭 [  ] 좌표 [  ] 분류 [  ] 영업시간 [  ] 설명 출처 [  ] 상태 [  ]  비고: \n")
    L.append("## P-17 현지 관심도 대리 지표 검수 (조회수 있는 장소가 가장 많은 대도시 2곳)\n")
    L.append("스페인어 조회 비중(es/(en+es))이 높은 장소가 '현지인이 더 찾는 곳'으로 보이는지, 낮은 장소가 '해외 관광객 중심'으로 보이는지 판단해 주세요. 한 달(2025년 9월) 조회수이며 합계 500 이상인 장소만 넣었다.\n")
    for city, d in p17.items():
        L.append(f"### {city} (대상 {d['n']}곳)")
        L.append("| 구분 | 장소 | 유형 | en | es | es 비중 | 지도 |\n|---|---|---|---|---|---|---|")
        for r in d["top"]:
            L.append(f"| 상위 | {r['name']} | {r['group']} | {r['en']:,} | {r['es']:,} | {r['share']} | [열기]({r['gmaps']}) |")
        for r in d["bottom"]:
            L.append(f"| 하위 | {r['name']} | {r['group']} | {r['en']:,} | {r['es']:,} | {r['share']} | [열기]({r['gmaps']}) |")
        L.append("\n- 판단: 상위는 현지 선호로 보이는가 [  ] 하위는 해외 관심으로 보이는가 [  ]  비고: \n")
    pathlib.Path(out_md).write_text("\n".join(L), encoding="utf-8")
    print(f"  표본 도시 {len(sample)}곳, 장소 {sum(len(c['places']) for c in sample)}곳, 검수표 {out_md}")


if __name__ == "__main__":
    main()
