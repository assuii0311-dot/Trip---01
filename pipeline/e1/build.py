"""E1 파이프라인 실행. 소스 읽기 → 매칭 → 통합 → 귀속 → 등급 → 정적 파일 생성 (docs/engines/E1-data-pipeline.md 3절).

실행: python -I -m pipeline.e1.build <데이터 루트> <출력 디렉터리(data/)> [--labels <labels.jsonl>] [--boundaries <boundaries.jsonl>] [--views <views.jsonl>] [--bbox S,W,N,E]
데이터 루트 아래: wikidata/, osm/out/pois.jsonl, e1/wv_en, e1/wv_es
"""
import argparse
import collections
import gzip
import hashlib
import json
import pathlib
import statistics
import sys
import time

from . import config as C
from . import sources
from .geo import Boundaries, Nearest, assign_admin, assign_city
from .match import Grid, build_groups, hav
from .merge import place_from_group, parse_price

ROOT = pathlib.Path(__file__).resolve().parents[2]


def dump_gz(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with gzip.open(path, "wb", compresslevel=9) as f:
        f.write(raw)
    return len(raw), path.stat().st_size


def in_bbox(lat, lon, bbox):
    return bbox is None or (bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root"); ap.add_argument("out")
    ap.add_argument("--labels"); ap.add_argument("--boundaries"); ap.add_argument("--views"); ap.add_argument("--bbox")
    ap.add_argument("--gtfs-catalog", default=str(ROOT / "poc/results/gtfs_catalog.json"))
    a = ap.parse_args()
    root, out = pathlib.Path(a.root), pathlib.Path(a.out)
    bbox = [float(x) for x in a.bbox.split(",")] if a.bbox else None
    t0 = time.time()
    log = lambda m: print(f"  [{time.time() - t0:6.0f}s] {m}", flush=True)

    wd = sources.load_wikidata(root / "wikidata", a.labels)
    log(f"Wikidata {len(wd):,}건")
    osm_places, settlements, districts, transit, airports = sources.load_osm(root / "osm/out/pois.jsonl")
    log(f"OSM 장소 {len(osm_places):,}, 정착지 {len(settlements):,}, 구역 {len(districts):,}, 교통 {len(transit):,}, 공항 {len(airports):,}")
    pages_en, list_en = sources.load_wikivoyage(root / "e1/wv_en", "en")
    pages_es, list_es = sources.load_wikivoyage(root / "e1/wv_es", "es")
    log(f"Wikivoyage en 문서 {len(pages_en)} 목록 {len(list_en):,}, es 문서 {len(pages_es)} 목록 {len(list_es):,}")
    views = sources.load_pageviews(a.views)
    if bbox:
        wd = {q: it for q, it in wd.items() if it["coord"] and in_bbox(it["coord"][0], it["coord"][1], bbox)}
        osm_places = [o for o in osm_places if in_bbox(o["lat"], o["lon"], bbox)]
        districts = [o for o in districts if in_bbox(o["lat"], o["lon"], bbox)]
        list_en = [w for w in list_en if w.get("lat") is not None and in_bbox(w["lat"], w["lon"], bbox) or (w.get("wikidata") in wd)]
        list_es = [w for w in list_es if w.get("lat") is not None and in_bbox(w["lat"], w["lon"], bbox) or (w.get("wikidata") in wd)]
        log(f"bbox 적용: Wikidata {len(wd):,}, OSM {len(osm_places):,}, wv {len(list_en) + len(list_es):,}")

    # 지자체(도시) 기준: Wikidata 스페인 지자체 클래스
    munis = {q: it for q, it in wd.items() if "Q2074737" in it["classes"] and it["coord"]} if not bbox else {q: it for q, it in sources.load_wikidata(root / "wikidata", a.labels).items() if "Q2074737" in it["classes"] and it["coord"]}
    nearest = Nearest([{"qid": q, "lat": it["coord"][0], "lon": it["coord"][1]} for q, it in munis.items()])
    boundaries = Boundaries(a.boundaries) if a.boundaries and pathlib.Path(a.boundaries).exists() else None
    log(f"지자체 {len(munis):,}건, 행정 경계 {boundaries.count if boundaries else 0}건")
    qid_by_name = {}
    for q, it in munis.items():
        for l in ("es", "ca", "eu", "gl", "en"):
            if it["labels"].get(l):
                qid_by_name.setdefault(it["labels"][l], q)
    qid_by_ine = {}

    groups, mstats = build_groups(wd, osm_places, list_en + list_es)
    log(f"매칭 그룹 {len(groups):,}건 {mstats}")
    places, dropped = [], collections.Counter()
    for g in groups.values():
        p = place_from_group(g, views)
        if not p:
            dropped["no_place"] += 1; continue
        city, how = assign_city(boundaries, nearest, p["lat"], p["lon"], qid_by_ine, qid_by_name)
        p["city"] = city
        dropped[f"city_{how}"] += 1
        places.append(p)
    log(f"장소 {len(places):,}건 (제외·귀속 통계 {dict(dropped)})")

    # 도시 레코드
    wv_city_by_qid = {}
    for it in wd.values() if not bbox else munis.values():
        pass
    page_en = {p["title"]: p for p in pages_en}
    wv_qid_to_page = {}
    for q, it in munis.items():
        if it.get("wv_en") and it["wv_en"] in page_en:
            wv_qid_to_page[q] = it["wv_en"]
    # Wikivoyage 문서 → 지자체: 도시 문서 제목이 라벨과 같은 경우도 연결
    for p in pages_en:
        if p["title"] in qid_by_name and qid_by_name[p["title"]] not in wv_qid_to_page:
            wv_qid_to_page[qid_by_name[p["title"]]] = p["title"]
    # 지구 문서(Madrid/Retiro 등)는 상위 도시 문서로 묶는다
    parent_en = {p["title"]: p.get("parent") for p in pages_en}
    def root_page(t):
        seen = set()
        while t in parent_en and parent_en[t] and parent_en[t] not in seen and page_en.get(t, {}).get("kind") == "district":
            seen.add(t); t = parent_en[t]
        return t
    pages_of = collections.defaultdict(set)
    for p in pages_en:
        pages_of[root_page(p["title"])].add(p["title"])
    wv_rows_by_qid = {q: [w for w in list_en if w["page"] in pages_of.get(title, {title})] for q, title in wv_qid_to_page.items()}
    by_city = collections.defaultdict(list)
    for p in places:
        if p["city"]:
            by_city[p["city"]].append(p)
    # 구역(숙박 밀도): 구역 노드에 숙박 장소를 최근접 1.5km로 배정
    dgrid = Grid(cell=0.02)
    for d in districts:
        d["lodging"] = 0; d["city"] = None
        dgrid.add(d["lat"], d["lon"], d)
    for p in places:
        if "lodging" in p["cat"]:
            bd, bdist = None, C.DISTRICT_RADIUS_M
            for d in dgrid.near(p["lat"], p["lon"]):
                dd = hav(p["lat"], p["lon"], d["lat"], d["lon"])
                if dd < bdist:
                    bd, bdist = d, dd
            if bd:
                bd["lodging"] += 1
    for d in districts:
        d["city"], _ = assign_city(boundaries, nearest, d["lat"], d["lon"], qid_by_ine, qid_by_name)
    dist_by_city = collections.defaultdict(list)
    for d in districts:
        if d["city"]:
            dist_by_city[d["city"]].append(d)
    # 가격대 분포: Wikivoyage 문서별 sleep/eat
    price_profile = {}
    for q, title in wv_qid_to_page.items():
        rows = wv_rows_by_qid[q]
        prof = {}
        for t in ("sleep", "eat"):
            vals = [parse_price(w["price"])[0] for w in rows if w["type"] == t and w.get("price")]
            vals = sorted(v for v in vals if v)
            tiers = collections.Counter(w["tier"] for w in rows if w["type"] == t and w.get("tier"))
            if vals or tiers:
                prof[t] = {"n": sum(1 for w in rows if w["type"] == t), "median": vals[len(vals) // 2] if vals else None, "q": [vals[len(vals) // 4], vals[3 * len(vals) // 4]] if len(vals) >= 4 else None, "tiers": dict(tiers)}
        if prof:
            price_profile[q] = prof
    gtfs = []
    try:
        gtfs = json.load(open(a.gtfs_catalog, encoding="utf-8"))
    except Exception:
        pass
    feed_rows = [{"mdb": r["mdb_id"], "provider": r["provider"], "routes": r["routes"], "stops": r["stops"], "types": r.get("route_types"), "fare": bool(r.get("fare_attributes")), "valid_to": r.get("max_date"), "license": r.get("catalog_license"), "_text": f"{r.get('provider', '')} {r.get('name', '')} {r.get('municipality', '')}".lower()} for r in gtfs if r.get("http") == 200 and r.get("routes")]
    FEED_CITY_WORDS = {"Q2807": ["madrid"], "Q1492": ["barcelona", "tmb", "amb"], "Q8818": ["valencia"], "Q8851": ["málaga", "malaga"], "Q8692": ["bilbao"], "Q8717": ["sevilla"], "Q14328": ["tenerife"]}
    feeds_by_muni = {q: [{k: v for k, v in f.items() if k != "_text"} for f in feed_rows if any(w in f["_text"] for w in words)] for q, words in FEED_CITY_WORDS.items()}
    cities = []
    for q, it in munis.items():
        if bbox and not in_bbox(it["coord"][0], it["coord"][1], bbox):
            continue
        ps = by_city.get(q, [])
        t1 = [p for p in ps if p["tier"] == 1]
        cat_dist = collections.Counter(c for p in t1 for c in p["cat"])
        center = it["coord"]
        lodging_3km = sum(1 for p in ps if "lodging" in p["cat"] and hav(center[0], center[1], p["lat"], p["lon"]) <= C.LODGING_CENTER_RADIUS_M)
        com, prov = assign_admin(boundaries, center[0], center[1])
        pv = views.get(q)
        wvp = wv_qid_to_page.get(q)
        wv_n = len(wv_rows_by_qid.get(q, [])) if wvp else 0
        stratum = "big" if (it["pop"] or 0) >= 100000 else ("guide" if wv_n >= 5 else ("small" if (it["pop"] or 0) < 20000 else "other"))
        name_l = it["labels"]
        cities.append({
            "id": q, "n": {"local": name_l.get("es") or name_l.get("en"), "es": name_l.get("es"), "en": name_l.get("en"), "ko": name_l.get("ko"), "ca": name_l.get("ca"), "eu": name_l.get("eu"), "gl": name_l.get("gl")},
            "lat": center[0], "lon": center[1], "pop": it["pop"], "stratum": stratum, "region": {"community": (com or {}).get("wikidata"), "province": (prov or {}).get("wikidata"), "p131": it["p131"]},
            "wv": {"en": wvp, "understand": (page_en.get(wvp) or {}).get("understand") if wvp else None, "listings": wv_n, "pages": sorted(pages_of.get(wvp, set())) if wvp else []},
            "wiki": it["wiki"], "sl": it["sitelinks"], "pv": pv, "places": {"tier1": len(t1), "tier2": len(ps) - len(t1), "cat": dict(cat_dist), "foreign": sum(1 for p in t1 if (p["pop"]["en_share"] or 0) >= 0.5 and p["pop"]["sl"] >= 10)},
            "lodging_3km": lodging_3km, "districts": sorted([{"id": d["id"], "n": d.get("name"), "lat": d["lat"], "lon": d["lon"], "kind": d["value"], "lodging": d["lodging"]} for d in dist_by_city.get(q, [])], key=lambda x: -x["lodging"])[:30],
            "price_profile": price_profile.get(q), "transit_feeds": feeds_by_muni.get(q, []), "taxi_fare": C.TAXI_FARES.get(q),
        })
    log(f"도시 {len(cities):,}건")
    # 지역: 행정 경계 4·6 + Wikivoyage 지역 문서
    regions = []
    if boundaries:
        for lvl, kind in (("4", "community"), ("6", "province")):
            for b in boundaries.by_level[lvl]:
                c = b["geom"].centroid
                regions.append({"id": b.get("wikidata") or b["osm_id"], "kind": kind, "n": {"local": b.get("name"), "es": b.get("name_es") or b.get("name")}, "lat": round(c.y, 5), "lon": round(c.x, 5), "osm": b["osm_id"]})
    for p in pages_en:
        if p["kind"] == "region" or p["depth"] <= 1:
            regions.append({"id": "wv:en:" + p["title"], "kind": "guide_region", "n": {"en": p["title"]}, "parent": ("wv:en:" + p["parent"]) if p.get("parent") else None, "understand": p.get("understand"), "depth": p["depth"]})
    # 범주 파일
    tier1 = [p for p in places if p["tier"] == 1]
    cat_counts = collections.Counter(c for p in tier1 for c in p["cat"])
    examples = {}
    for c in C.CATEGORIES:
        top = sorted((p for p in tier1 if c in p["cat"]), key=lambda p: (-p["pop"]["sl"], -((p["pop"]["pv"] or {}).get("en", 0))))[:3]
        examples[c] = [{"id": p["id"], "n": p["n"].get("ko") or p["n"].get("local")} for p in top]
    categories = {"categories": [{"id": c, "ko": k, "tier1": cat_counts.get(c, 0), "examples": examples[c]} for c, k in C.CATEGORIES.items()], "osm_map": C.OSM_TAG_CATEGORY, "wv_map": C.WV_TYPE_CATEGORY, "wd_map": C.WD_CLASS_CATEGORY}
    # 설명 출처 본문 샤드(Wikivoyage content)와 장소 파일
    content_by_key = {(w["lang"], w["page"], w["idx"]): w["content"] for w in list_en + list_es if w.get("content")}
    shards = collections.defaultdict(dict)
    for p in places:
        for d in p["desc"]:
            if d["src"] == "wikivoyage":
                key = (d["lang"], d["page"], d["idx"])
                if key in content_by_key:
                    shards[hashlib.md5(p["id"].encode()).hexdigest()[:2]][f"{p['id']}|{d['lang']}|{d['page']}|{d['idx']}"] = content_by_key[key]
    # 출력
    sizes = {}
    sizes["cities"] = dump_gz(out / "cities.json.gz", cities)
    sizes["regions"] = dump_gz(out / "regions.json.gz", regions)
    sizes["categories"] = dump_gz(out / "categories.json.gz", categories)
    sizes["places_tier1"] = dump_gz(out / "places_tier1.json.gz", tier1)
    t2_by_city = collections.defaultdict(list)
    for p in places:
        if p["tier"] == 2:
            t2_by_city[p["city"] or "none"].append(p)
    t2_total = 0
    for cq, ps in t2_by_city.items():
        t2_total += dump_gz(out / "places_tier2" / f"{cq}.json.gz", ps)[1]
    for sh, d in shards.items():
        dump_gz(out / "sources" / f"{sh}.json.gz", d)
    sizes["airports"] = dump_gz(out / "airports.json.gz", [{"id": o["id"], "n": o.get("name"), "en": o.get("name:en"), "lat": o["lat"], "lon": o["lon"], "wd": o.get("wikidata")} for o in airports if o.get("name")])
    attribution = {"generated": time.strftime("%Y-%m-%d"), "sources": C.ATTRIBUTION, "data_license": "data/LICENSE-DATA.md", "counts": {"places": len(places), "tier1": len(tier1), "tier2": len(places) - len(tier1), "cities": len(cities), "regions": len(regions)}}
    (out / "attribution.json").write_text(json.dumps(attribution, ensure_ascii=False, indent=1), encoding="utf-8")
    cv = collections.Counter(p["cv"] for p in places); ver = collections.Counter(p["ver"] for p in places); cs = collections.Counter(p["cs"] for p in places); cityhow = {k: v for k, v in dropped.items() if k.startswith("city_")}
    report = {"generated": time.strftime("%Y-%m-%d %H:%M"), "inputs": {"wikidata": len(wd), "osm_places": len(osm_places), "wv_en": len(list_en), "wv_es": len(list_es), "pageviews": len(views), "boundaries": boundaries.count if boundaries else 0},
              "match": mstats, "places": {"total": len(places), "tier1": len(tier1), "tier2": len(places) - len(tier1), "crossval": dict(cv), "verified": {str(k): v for k, v in ver.items()}, "coord_source": dict(cs), "city_assignment": cityhow},
              "categories_tier1": dict(cat_counts), "names": {"ko": sum(1 for p in tier1 if p["n"].get("ko")), "en": sum(1 for p in tier1 if p["n"].get("en")), "es": sum(1 for p in tier1 if p["n"].get("es"))},
              "fields_tier1": {"hours": sum(1 for p in tier1 if p["hrs"]), "price": sum(1 for p in tier1 if p["price"]), "desc_wv": sum(1 for p in tier1 if any(d["src"] == "wikivoyage" for d in p["desc"])), "pageviews": sum(1 for p in tier1 if p["pop"]["pv"])},
              "files": {k: {"raw_bytes": v[0], "gz_bytes": v[1]} for k, v in sizes.items()}, "tier2_gz_bytes": t2_total, "elapsed_s": round(time.time() - t0)}
    (out / "crossval_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"완료. 파일 크기(gz): " + ", ".join(f"{k} {v[1] / 1e6:.1f}MB" for k, v in sizes.items()) + f", tier2 합계 {t2_total / 1e6:.1f}MB")
    print(json.dumps(report["places"], ensure_ascii=False))


if __name__ == "__main__":
    main()
