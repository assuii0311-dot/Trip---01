#!/usr/bin/env python3
"""E1 보조: OSM 스페인 추출본에서 행정 경계(admin_level 4, 6, 8) 폴리곤을 뽑아 저장한다 (E1 4절 8항 도시 귀속용).

출력: JSONL 한 줄에 {osm_id, admin_level, name, name:es, wikidata, ref:ine, wkb}. wkb는 멀티폴리곤 WKB의 16진수 문자열.
실행: python -I pipeline/e1/osm_boundaries.py <spain.osm.pbf> <출력 JSONL>
"""
import json
import re
import sys
import time

import osmium

LEVELS = {"4", "6", "8"}


def hull_wkb(points):
    """점 목록(lon, lat)의 볼록 껍질을 멀티폴리곤 WKB 16진수로. 점이 3개 미만이거나 넓이가 없으면 None."""
    from shapely import wkb
    from shapely.geometry import MultiPoint, MultiPolygon
    if len(points) < 3:
        return None
    hull = MultiPoint(points).convex_hull
    if hull.geom_type != "Polygon" or hull.area == 0:
        return None
    return wkb.dumps(MultiPolygon([hull]), hex=True).upper()


def is_spanish_ine(code):
    """스페인 지자체의 INE 코드인가(5자리 또는 OSM에 흔한 11자리). 추출본에는 국경 너머 포르투갈 교구(6자리 코드)와 프랑스 코뮌의 잘린 경계도 들어 있다."""
    return bool(code) and re.fullmatch(r"\d{5}(\d{6})?", str(code)) is not None


def add_unassembled(pbf, out):
    """경계선이 추출본에서 잘려 다각형으로 조립되지 않은 지자체(admin_level 8)를 경계선 점들의 볼록 껍질로 보탠다(T-049 세우타).
    근사값이다. 레코드에 approx를 적는다. 스페인 지자체(INE 코드)만 보태고, 같은 Wikidata 항목의 지자체 경계가 이미 있으면 보태지 않는다."""
    have_ids, have_qids = set(), set()
    with open(out, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            have_ids.add(r["osm_id"])
            if r["admin_level"] == "8" and r.get("wikidata"):
                have_qids.add(r["wikidata"])
    missing = {}  # 관계 ID → (태그, 멤버 길 ID 목록)
    for o in osmium.FileProcessor(pbf, osmium.osm.RELATION).with_filter(osmium.filter.KeyFilter("boundary")):
        t = o.tags
        if t.get("boundary") != "administrative" or t.get("admin_level") != "8" or ("r" + str(o.id)) in have_ids or (t.get("wikidata") and t.get("wikidata") in have_qids):
            continue
        if not is_spanish_ine(t.get("ref:ine") or t.get("ine:municipio")):
            continue  # 스페인 지자체만 보탠다
        missing[o.id] = ({"name": t.get("name"), "name:es": t.get("name:es"), "wikidata": t.get("wikidata"), "ref:ine": t.get("ref:ine") or t.get("ine:municipio")}, [m.ref for m in o.members if m.type == "w"])
    if not missing:
        return 0
    want = {w for _, ways in missing.values() for w in ways}
    pts = {}
    for o in osmium.FileProcessor(pbf, osmium.osm.NODE | osmium.osm.WAY).with_locations():
        if o.is_way() and o.id in want:
            pts[o.id] = [(nd.lon, nd.lat) for nd in o.nodes if nd.location.valid()]
    add = 0
    with open(out, "a", encoding="utf-8") as f:
        for rid in sorted(missing):
            tags, ways = missing[rid]
            w = hull_wkb([p for wid in ways for p in pts.get(wid, [])])
            if not w:
                continue
            f.write(json.dumps({"osm_id": "r" + str(rid), "admin_level": "8", "name": tags["name"], "name_es": tags["name:es"], "wikidata": tags["wikidata"], "ine": tags["ref:ine"], "wkb": w, "approx": "convex_hull"}, ensure_ascii=False) + "\n")
            add += 1
            print(f"    r{rid} {tags['name']} ({tags['wikidata']})", flush=True)
    return add


def main():
    pbf, out = sys.argv[1], sys.argv[2]
    fab = osmium.geom.WKBFactory()
    t0 = time.time()
    n = kept = bad = 0
    with open(out, "w", encoding="utf-8") as f:
        fp = osmium.FileProcessor(pbf).with_areas().with_filter(osmium.filter.KeyFilter("boundary"))
        for o in fp:
            if not o.is_area():
                continue
            n += 1
            t = o.tags
            if t.get("boundary") != "administrative" or t.get("admin_level") not in LEVELS:
                continue
            try:
                wkb = fab.create_multipolygon(o)
            except Exception as e:  # 잘못 닫힌 경계 등
                bad += 1
                continue
            rec = {"osm_id": ("r" if o.from_way() is False else "w") + str(o.orig_id()), "admin_level": t.get("admin_level"), "name": t.get("name"), "name_es": t.get("name:es"), "wikidata": t.get("wikidata"), "ine": t.get("ref:ine") or t.get("ine:municipio"), "wkb": wkb}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            kept += 1
            if kept % 500 == 0:
                print(f"  {kept}건 ({time.time() - t0:.0f}초)", flush=True)
    print(f"  완료: 영역 {n}건 중 행정 경계 {kept}건 저장, 변환 실패 {bad}건, {time.time() - t0:.0f}초", flush=True)
    add = add_unassembled(pbf, out)
    print(f"  다각형으로 조립되지 않은 지자체 경계 {add}건을 볼록 껍질로 보탬, {time.time() - t0:.0f}초", flush=True)


if __name__ == "__main__":
    main()
