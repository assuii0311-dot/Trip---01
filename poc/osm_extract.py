#!/usr/bin/env python3
"""2단계 PoC B 단계: OSM 추출본(pbf)에서 여행 관련 장소를 뽑고 필드 커버리지를 센다.

- 노드와 웨이만 처리한다. 웨이의 좌표는 구성 노드 좌표의 평균이다. 멀티폴리곤 릴레이션은 PoC에서 제외한다.
- 대상 키: tourism, historic, natural, leisure, amenity, shop, place, aeroway, railway, public_transport
- 이름이 있거나 tourism, historic 키가 있는 객체만 기록한다.
- 출력: pois.jsonl(장소), summary.json(요약). 원본은 저장하지 않는다.

실행: python -I poc/osm_extract.py <파일.pbf> <출력 디렉터리>
"""
import collections
import json
import pathlib
import sys
import time

import osmium

KEYS = ["tourism", "historic", "natural", "leisure", "amenity", "shop", "place", "aeroway", "railway", "public_transport"]
FIELDS = ["name", "name:es", "name:en", "name:ko", "name:ca", "name:eu", "name:gl", "wikidata", "wikipedia", "opening_hours",
          "fee", "charge", "reservation", "website", "phone", "cuisine", "description", "addr:city", "addr:postcode", "population", "image"]
AMENITY_TRAVEL = {"restaurant", "cafe", "bar", "pub", "fast_food", "ice_cream", "food_court", "biergarten", "marketplace", "theatre",
                  "cinema", "arts_centre", "place_of_worship", "fountain", "nightclub", "library", "townhall", "university", "casino",
                  "bus_station", "ferry_terminal", "taxi"}
NATURAL_TRAVEL = {"beach", "peak", "cave_entrance", "waterfall", "bay", "spring", "hot_spring", "cliff", "volcano", "dune", "glacier",
                  "cape", "arch", "rock", "sinkhole", "geyser", "lake", "water", "wetland", "reef", "island"}
LEISURE_TRAVEL = {"park", "garden", "nature_reserve", "stadium", "marina", "water_park", "beach_resort", "golf_course", "amusement_arcade",
                  "miniature_golf", "swimming_pool", "sports_centre", "ice_rink", "track", "bird_hide", "picnic_table", "slipway"}
SHOP_TRAVEL = {"bakery", "pastry", "confectionery", "chocolate", "wine", "alcohol", "deli", "cheese", "seafood", "tea", "coffee",
               "books", "gift", "souvenir", "craft", "art", "antiques", "department_store", "mall", "clothes", "boutique", "fashion",
               "shoes", "jewelry", "perfumery", "cosmetics", "ceramics", "music", "toys", "second_hand", "greengrocer", "market",
               "ice_cream", "tobacco", "leather", "fabric", "frozen_food", "spices", "nuts", "pasta", "farm"}
PLACE_KEEP = {"city", "town", "village", "hamlet", "suburb", "quarter", "neighbourhood", "island", "islet", "borough"}
RAIL_KEEP = {"station", "halt", "tram_stop"}
PT_KEEP = {"station"}
AERO_KEEP = {"aerodrome", "terminal"}


def keep(pk, pv, tags):
    named = "name" in tags
    if pk in ("tourism", "historic"):
        return True
    if pk == "natural":
        return pv in NATURAL_TRAVEL and named
    if pk == "leisure":
        return pv in LEISURE_TRAVEL and (named or pv == "nature_reserve")
    if pk == "amenity":
        return pv in AMENITY_TRAVEL and named
    if pk == "shop":
        return pv in SHOP_TRAVEL and named
    if pk == "place":
        return pv in PLACE_KEEP and named
    if pk == "railway":
        return pv in RAIL_KEEP and named
    if pk == "public_transport":
        return pv in PT_KEEP and named
    if pk == "aeroway":
        return pv in AERO_KEEP and named
    return False


def primary(tags):
    for k in KEYS:
        if k in tags:
            return k, tags[k]
    return None, None


def main():
    path, outdir = sys.argv[1], pathlib.Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    fp = osmium.FileProcessor(path, osmium.osm.NODE | osmium.osm.WAY).with_locations().with_filter(osmium.filter.KeyFilter(*KEYS))
    n_seen, n_kept = 0, 0
    by_cat = collections.Counter()
    cov = collections.defaultdict(collections.Counter)   # primary key -> field -> count
    cov_all = collections.Counter()
    name_lang = collections.Counter()
    with open(outdir / "pois.jsonl", "w", encoding="utf-8") as out:
        for o in fp:
            n_seen += 1
            tags = {t.k: t.v for t in o.tags}
            pk, pv = primary(tags)
            if pk is None or not keep(pk, pv, tags):
                continue
            if o.is_node():
                if not o.location.valid():
                    continue
                lat, lon, otype = o.location.lat, o.location.lon, "n"
            else:
                locs = [n.location for n in o.nodes if n.location.valid()]
                if not locs:
                    continue
                lat = sum(l.lat for l in locs) / len(locs)
                lon = sum(l.lon for l in locs) / len(locs)
                otype = "w"
            n_kept += 1
            by_cat[f"{pk}={pv}"] += 1
            for f in FIELDS:
                if f in tags and tags[f]:
                    cov[pk][f] += 1
                    cov_all[f] += 1
            for k in tags:
                if k.startswith("name:"):
                    name_lang[k] += 1
            rec = {"id": f"{otype}{o.id}", "lat": round(lat, 6), "lon": round(lon, 6), "key": pk, "value": pv}
            for f in FIELDS:
                if f in tags:
                    rec[f] = tags[f][:200]
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    by_key = collections.Counter()
    for k, v in by_cat.items():
        by_key[k.split("=")[0]] += v
    summary = {
        "file": pathlib.Path(path).name, "parsed_at": time.strftime("%Y-%m-%d %H:%M"), "seconds": round(time.time() - t0),
        "objects_with_target_keys": n_seen, "kept": n_kept, "by_key": dict(by_key),
        "top_categories": by_cat.most_common(60),
        "field_coverage_pct_all": {f: round(100 * cov_all[f] / n_kept, 1) for f in FIELDS} if n_kept else {},
        "field_coverage_pct_by_key": {k: {f: round(100 * cov[k][f] / by_key[k], 1) for f in FIELDS} for k in by_key},
        "name_lang_tags": name_lang.most_common(15),
    }
    json.dump(summary, open(outdir / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  대상 키 보유 객체 {n_seen}건 중 {n_kept}건 기록 ({round(time.time()-t0)}초)")
    print(f"  키별: {dict(by_key)}")
    c = summary["field_coverage_pct_all"]
    print(f"  전체 커버리지: name {c['name']}% name:en {c['name:en']}% name:ko {c['name:ko']}% wikidata {c['wikidata']}% opening_hours {c['opening_hours']}% fee {c['fee']}% reservation {c['reservation']}% website {c['website']}%")


if __name__ == "__main__":
    main()
