#!/usr/bin/env python3
"""E1 보조: OSM 스페인 추출본에서 행정 경계(admin_level 4, 6, 8) 폴리곤을 뽑아 저장한다 (E1 4절 8항 도시 귀속용).

출력: JSONL 한 줄에 {osm_id, admin_level, name, name:es, wikidata, ref:ine, wkb}. wkb는 멀티폴리곤 WKB의 16진수 문자열.
실행: python -I pipeline/e1/osm_boundaries.py <spain.osm.pbf> <출력 JSONL>
"""
import json
import sys
import time

import osmium

LEVELS = {"4", "6", "8"}


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


if __name__ == "__main__":
    main()
