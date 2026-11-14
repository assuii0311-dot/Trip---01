#!/usr/bin/env python3
"""E1 보조: OSM 스페인 추출본에서 섬(place=island) 폴리곤을 뽑아 저장한다 (E1 4절 14항 섬 단위 여행지용).

출력: JSONL 한 줄에 {osm_id, name, name_es, name_en, wikidata, wkb}. wkb는 멀티폴리곤 WKB의 16진수 문자열.
이름이 없는 섬과 폴리곤으로 닫히지 않는 섬은 제외한다. 어느 지자체가 어느 섬에 있는지는 build가 판정한다.
실행: python -I pipeline/e1/osm_islands.py <spain.osm.pbf> <출력 JSONL>
"""
import json
import sys
import time

import osmium


def main():
    pbf, out = sys.argv[1], sys.argv[2]
    fab = osmium.geom.WKBFactory()
    t0 = time.time()
    n = kept = bad = 0
    rows = []
    fp = osmium.FileProcessor(pbf).with_areas().with_filter(osmium.filter.KeyFilter("place"))
    for o in fp:
        if not o.is_area():
            continue
        t = o.tags
        if t.get("place") != "island" or not t.get("name"):
            continue
        n += 1
        try:
            wkb = fab.create_multipolygon(o)
        except Exception:  # 잘못 닫힌 해안선 등
            bad += 1
            continue
        rows.append({"osm_id": ("r" if o.from_way() is False else "w") + str(o.orig_id()), "name": t.get("name"), "name_es": t.get("name:es"), "name_en": t.get("name:en"), "wikidata": t.get("wikidata"), "wkb": wkb})
        kept += 1
    rows.sort(key=lambda r: r["osm_id"])  # 같은 입력에 같은 출력
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  완료: 이름 있는 섬 {n}건 중 {kept}건 저장, 변환 실패 {bad}건, {time.time() - t0:.0f}초", flush=True)


if __name__ == "__main__":
    main()
