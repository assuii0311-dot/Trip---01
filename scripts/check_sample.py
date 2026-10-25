#!/usr/bin/env python3
"""E1 품질 점검(E1 6절): D 단계 검수 표본(poc/results/review_judgments.json)의 장소가 새 기준 데이터에 있는지, 명칭·좌표가 검수 결과와 맞는지 본다. 외부 호출 없음.
실행: python -I scripts/check_sample.py <data 디렉터리>
"""
import gzip
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(x))


def main():
    d = pathlib.Path(sys.argv[1])
    sample = json.load(open(ROOT / "poc/results/review_sample.json", encoding="utf-8"))
    places = json.load(gzip.open(d / "places_tier1.json.gz", "rt", encoding="utf-8"))
    by_osm, by_qid = {}, {}
    for p in places:
        by_qid[p["id"]] = p
        for o in p["src"]["osm"]:
            by_osm[o] = p
    # 2등급도 읽는다(표본 도시의 파일만)
    cities = {c["qid"] for c in sample["cities"]}
    rows = []
    for c in sample["cities"]:
        for r in c["places"]:
            key = r["key"]; q = (r.get("wd") or {}).get("qid") if isinstance(r.get("wd"), dict) else None
            rows.append((c["name_es"], key, q, float(r["lat"]) if r.get("lat") else None, float(r["lon"]) if r.get("lon") else None, r.get("group")))
    t2 = {}
    for c in sample["cities"]:
        f = d / "places_tier2" / f"{c['qid']}.json.gz"
        if f.exists():
            for p in json.load(gzip.open(f, "rt", encoding="utf-8")):
                for o in p["src"]["osm"]:
                    t2[o] = p
                t2[p["id"]] = p
    found = within = 0; miss = []
    for city, key, q, lat, lon, grp in rows:
        p = by_osm.get(key) or (by_qid.get(q) if q else None) or t2.get(key) or (t2.get(q) if q else None)
        if not p:
            miss.append((city, key, grp)); continue
        found += 1
        if lat is not None and hav(lat, lon, p["lat"], p["lon"]) <= 150:
            within += 1
    print(f"  표본 {len(rows)}곳 중 기준 데이터에 있음 {found}곳, 표본 좌표와 150m 안 {within}곳")
    print(f"  없음: {miss[:12]}")


if __name__ == "__main__":
    main()
