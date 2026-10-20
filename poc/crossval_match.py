#!/usr/bin/env python3
"""2단계 PoC C 단계: Wikidata, 영문 Wikivoyage 목록, OSM 장소를 교차 매칭하고 일치, 불일치, 단일 출처를 센다.

매칭 규칙
- 1차: Wikidata ID(QID)가 같으면 매칭.
- 2차: QID가 없거나 상대에 없으면 좌표 150m 이내 후보 중 정규화한 명칭 유사도(difflib) 0.6 이상인 것과 매칭.
- 판정: 키로 매칭됐는데 좌표가 500m 넘게 떨어지거나 명칭 유사도가 0.4 미만이면 불일치, 둘 이상 출처가 맞으면 일치, 나머지는 단일 출처.
부수 산출: 숙박 밀도(Wikivoyage 도시 중심 3km 안 OSM 숙박 수), 가이드 미수록 OSM 장소(P-17), 예약 문구 결합(P-09).

실행: python -I poc/crossval_match.py <데이터 디렉터리 루트> <요약 JSON 출력>
"""
import collections
import difflib
import json
import math
import pathlib
import re
import statistics
import sys
import time
import unicodedata

CELL = 0.005          # 격자 크기(도). 약 500m
R_MATCH = 150.0       # 2차 매칭 반경(m)
R_CONFLICT = 500.0    # 키 매칭 불일치 기준(m)
SIM_MATCH, SIM_CONFLICT = 0.6, 0.4
ACCOM = {"hotel", "hostel", "guest_house", "apartment", "motel", "chalet", "camp_site", "alpine_hut", "caravan_site"}
GUIDE_KEYS = {"tourism", "historic", "natural", "leisure"}
FOOD = {"restaurant", "cafe", "bar", "pub", "fast_food", "ice_cream", "food_court", "biergarten", "marketplace"}


def norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"\b(el|la|los|las|de|del|the|of|y|e|i|a|en)\b", " ", s)
    return re.sub(r"[^a-z0-9ñ ]+", " ", s).strip()


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


def parse_point(s):
    m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", s or "")
    return (float(m.group(2)), float(m.group(1))) if m else None


class Grid:
    def __init__(self):
        self.cells = collections.defaultdict(list)

    def add(self, lat, lon, item):
        self.cells[(int(lat // CELL), int(lon // CELL))].append(item)

    def near(self, lat, lon):
        ci, cj = int(lat // CELL), int(lon // CELL)
        for i in (ci - 1, ci, ci + 1):
            for j in (cj - 1, cj, cj + 1):
                yield from self.cells.get((i, j), ())


def best_name_match(cands, lat, lon, names, radius=R_MATCH):
    best = None
    for o in cands:
        d = hav(lat, lon, o["lat"], o["lon"])
        if d > radius:
            continue
        s = max(sim(n, o.get("name")) for n in names) if any(names) else 0.0
        if s >= SIM_MATCH and (best is None or s > best[1] or (s == best[1] and d < best[2])):
            best = (o, s, d)
    return best


def main():
    root, out = pathlib.Path(sys.argv[1]), sys.argv[2]
    t0 = time.time()
    # Wikidata
    wd = {}
    for f in (root / "wikidata").glob("*.jsonl"):
        if f.name == "sitelinks.jsonl":
            continue
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            q = r["qid"]
            if q in wd:
                cur = wd[q]
                cur["cls"].add(r["cls"])
                for k in ("coord", "label_es", "label_en", "label_ko", "sitelinks"):
                    if not cur.get(k) and r.get(k):
                        cur[k] = r[k]
            else:
                r["cls"] = {r["cls"]}
                wd[q] = r
    for r in wd.values():
        r["pt"] = parse_point(r.get("coord"))
    # OSM
    osm, grid, osm_by_q = [], Grid(), collections.defaultdict(list)
    for line in open(root / "osm" / "out" / "pois.jsonl", encoding="utf-8"):
        o = json.loads(line)
        osm.append(o)
        grid.add(o["lat"], o["lon"], o)
        if o.get("wikidata"):
            for q in o["wikidata"].split(";"):
                q = q.strip()
                if q.startswith("Q"):
                    osm_by_q[q].append(o)
    # Wikivoyage
    wv = [json.loads(l) for l in open(root / "wikivoyage_en" / "out" / "listings.jsonl", encoding="utf-8")]
    for x in wv:
        try:
            x["pt"] = (float(x["lat"]), float(x["long"])) if x.get("lat") and x.get("long") else None
        except ValueError:
            x["pt"] = None
    print(f"  로드: Wikidata {len(wd)}, OSM {len(osm)}, Wikivoyage 목록 {len(wv)} ({round(time.time()-t0)}초)")

    # --- Wikidata <-> OSM ---
    wd_osm = {}          # qid -> (osm, how, dist, sim)
    dists_key, sims_key = [], []
    for q, r in wd.items():
        cands = osm_by_q.get(q)
        if cands:
            o = cands[0]
            d = hav(r["pt"][0], r["pt"][1], o["lat"], o["lon"]) if r["pt"] else None
            s = max(sim(r.get("label_es"), o.get("name")), sim(r.get("label_en"), o.get("name"))) if (r.get("label_es") or r.get("label_en")) else None
            wd_osm[q] = (o, "key", d, s)
            if d is not None:
                dists_key.append(d)
            if s is not None:
                sims_key.append(s)
        elif r["pt"] and (r.get("label_es") or r.get("label_en")):
            b = best_name_match(grid.near(*r["pt"]), r["pt"][0], r["pt"][1], [r.get("label_es"), r.get("label_en")])
            if b:
                wd_osm[q] = (b[0], "geo+name", b[2], b[1])
    n_key = sum(1 for v in wd_osm.values() if v[1] == "key")
    n_geo = len(wd_osm) - n_key
    print(f"  Wikidata→OSM: 키 매칭 {n_key}, 좌표+명칭 매칭 {n_geo} ({round(time.time()-t0)}초)")

    # --- Wikivoyage <-> Wikidata / OSM ---
    wv_wd = sum(1 for x in wv if x.get("wikidata") in wd)
    wv_osm, wv_dists = {}, []
    for i, x in enumerate(wv):
        q = x.get("wikidata")
        if q and osm_by_q.get(q):
            o = osm_by_q[q][0]
            d = hav(x["pt"][0], x["pt"][1], o["lat"], o["lon"]) if x["pt"] else None
            wv_osm[i] = (o, "key", d)
            if d is not None:
                wv_dists.append(d)
        elif x["pt"] and x.get("name"):
            b = best_name_match(grid.near(*x["pt"]), x["pt"][0], x["pt"][1], [x["name"]])
            if b:
                wv_osm[i] = (b[0], "geo+name", b[2])
    wv_osm_key = sum(1 for v in wv_osm.values() if v[1] == "key")
    # Wikivoyage 목록 중 QID 없는 것 → Wikidata 좌표+명칭 매칭
    wd_grid = Grid()
    for q, r in wd.items():
        if r["pt"]:
            wd_grid.add(r["pt"][0], r["pt"][1], {"lat": r["pt"][0], "lon": r["pt"][1], "name": r.get("label_es") or r.get("label_en"), "qid": q,
                                                  "name2": r.get("label_en")})
    wv_wd_geo = 0
    for x in wv:
        if (not x.get("wikidata") or x["wikidata"] not in wd) and x["pt"] and x.get("name"):
            b = best_name_match(wd_grid.near(*x["pt"]), x["pt"][0], x["pt"][1], [x["name"]])
            if b:
                wv_wd_geo += 1
                x["wd_geo"] = b[0]["qid"]
    print(f"  Wikivoyage→Wikidata: 키 {wv_wd}, 좌표+명칭 {wv_wd_geo}. Wikivoyage→OSM: 키 {wv_osm_key}, 좌표+명칭 {len(wv_osm)-wv_osm_key} ({round(time.time()-t0)}초)")

    # --- 상태 판정 (Wikidata 항목 기준) ---
    wv_q = collections.Counter(x.get("wikidata") or x.get("wd_geo") for x in wv)
    status = collections.Counter()
    status_tour = collections.Counter()
    conflicts = collections.Counter()
    for q, r in wd.items():
        srcs = 1
        conflict = False
        m = wd_osm.get(q)
        if m:
            srcs += 1
            if m[1] == "key" and ((m[2] is not None and m[2] > R_CONFLICT) or (m[3] is not None and m[3] < SIM_CONFLICT)):
                conflict = True
                conflicts["coord>500m" if (m[2] is not None and m[2] > R_CONFLICT) else "name<0.4"] += 1
        if wv_q.get(q):
            srcs += 1
        st = "불일치" if conflict else ("일치" if srcs >= 2 else "단일 출처")
        status[st] += 1
        if not (r["cls"] <= {"Q2074737", "Q515", "Q3957", "Q532", "P1435"}) or "P1435" in r["cls"] and len(r["cls"]) == 1:
            status_tour[st] += 1
    osm_matched_ids = {v[0]["id"] for v in wd_osm.values()} | {v[0]["id"] for v in wv_osm.values()}
    osm_single = sum(1 for o in osm if o["id"] not in osm_matched_ids)
    wv_single = sum(1 for i, x in enumerate(wv) if i not in wv_osm and not (x.get("wikidata") in wd or x.get("wd_geo")))

    # --- P-17: 가이드 미수록 OSM 장소 ---
    wv_osm_ids = {v[0]["id"] for v in wv_osm.values()}
    guide_missing = collections.Counter()
    guide_total = collections.Counter()
    for o in osm:
        k = o["key"]
        if k in GUIDE_KEYS or (k == "amenity" and o["value"] in FOOD):
            cat = f'{k}={o["value"]}'
            guide_total[cat] += 1
            if o["id"] not in wv_osm_ids:
                guide_missing[cat] += 1
    gm_top = [(c, guide_total[c], guide_missing[c]) for c, _ in guide_total.most_common(15)]

    # --- P-04: Wikivoyage 도시 중심 3km 안 OSM 숙박 수 ---
    by_page = collections.defaultdict(list)
    for x in wv:
        if x["pt"]:
            by_page[x["page"]].append(x["pt"])
    accom_grid = Grid()
    n_accom = 0
    for o in osm:
        if o["key"] == "tourism" and o["value"] in ACCOM:
            accom_grid.add(o["lat"], o["lon"], o)
            n_accom += 1
    city_accom = {}
    for page, pts in by_page.items():
        if len(pts) < 3:
            continue
        clat = statistics.median(p[0] for p in pts)
        clon = statistics.median(p[1] for p in pts)
        cnt = 0
        for i in range(-6, 7):
            for j in range(-6, 7):
                for o in accom_grid.cells.get((int(clat // CELL) + i, int(clon // CELL) + j), ()):
                    if hav(clat, clon, o["lat"], o["lon"]) <= 3000:
                        cnt += 1
        city_accom[page] = cnt
    wv_sleep = collections.Counter(x["page"] for x in wv if x["type"] == "sleep")
    ca = sorted(city_accom.values())

    # --- P-09: 예약 신호 결합 ---
    booking_wv = sum(1 for x in wv if x.get("booking_text"))
    reservation_osm = sum(1 for o in osm if o.get("reservation"))

    def pct(a, b):
        return round(100 * a / b, 1) if b else None

    summary = {
        "computed_at": time.strftime("%Y-%m-%d %H:%M"), "seconds": round(time.time() - t0),
        "sizes": {"wikidata": len(wd), "osm": len(osm), "wikivoyage_listings": len(wv)},
        "wikidata_osm": {"key": n_key, "geo_name": n_geo, "total": len(wd_osm), "pct_of_wikidata": pct(len(wd_osm), len(wd)),
                         "key_dist_m": {"median": round(statistics.median(dists_key)) if dists_key else None,
                                        "pct_gt_200m": pct(sum(1 for d in dists_key if d > 200), len(dists_key)),
                                        "pct_gt_1km": pct(sum(1 for d in dists_key if d > 1000), len(dists_key))},
                         "key_name_sim": {"median": round(statistics.median(sims_key), 2) if sims_key else None,
                                          "pct_lt_0_4": pct(sum(1 for s in sims_key if s < SIM_CONFLICT), len(sims_key))}},
        "wikivoyage": {"to_wikidata_key": wv_wd, "to_wikidata_geo_name": wv_wd_geo, "to_osm_key": wv_osm_key, "to_osm_geo_name": len(wv_osm) - wv_osm_key,
                       "to_osm_total_pct": pct(len(wv_osm), len(wv)), "key_dist_median_m": round(statistics.median(wv_dists)) if wv_dists else None,
                       "key_dist_pct_gt_200m": pct(sum(1 for d in wv_dists if d > 200), len(wv_dists)), "single": wv_single},
        "status_wikidata": dict(status), "status_wikidata_tourism_classes": dict(status_tour), "conflict_reasons": dict(conflicts),
        "osm_single_source": osm_single, "osm_single_pct": pct(osm_single, len(osm)),
        "p17_guide_missing": {"total_candidates": sum(guide_total.values()), "missing": sum(guide_missing.values()), "top": gm_top},
        "p04_accommodation": {"osm_accommodation": n_accom, "cities_measured": len(city_accom),
                              "cities_with_ge_10_within_3km": sum(1 for v in ca if v >= 10), "cities_with_0": sum(1 for v in ca if v == 0),
                              "median": ca[len(ca) // 2] if ca else None, "wv_pages_with_sleep": len(wv_sleep)},
        "p09_booking": {"wikivoyage_booking_text": booking_wv, "osm_reservation_tag": reservation_osm},
    }
    json.dump(summary, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: summary[k] for k in ("wikidata_osm", "wikivoyage", "status_wikidata", "status_wikidata_tourism_classes", "conflict_reasons", "osm_single_pct", "p04_accommodation", "p09_booking")}, ensure_ascii=False, indent=1))
    print("  P-17 상위:", gm_top[:8])


if __name__ == "__main__":
    main()
