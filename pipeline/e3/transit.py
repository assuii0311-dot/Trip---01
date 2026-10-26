"""E3 사전 계산 3: 대중교통 B 단계 요약. 도시별 GTFS 피드에서 정류장, 노선, 정차 순서, 1회권 요금을 뽑는다 (E3 4절 3항).

출력 transit/<city>.json.gz: {feeds:[...], stops:[[lat,lon,name]], routes:[{id, name, type, feed, seq:[stop idx...]}], fares:[{feed, price, currency}]}
실행: python -I pipeline/run.py e3.transit <gtfs_catalog.json> <피드 zip 디렉터리> <Renfe zip 디렉터리> <cities.json.gz> --out <transit 디렉터리>
"""
import argparse
import collections
import csv
import gzip
import io
import json
import math
import pathlib
import zipfile

FEED_CITY_WORDS = {"Q2807": ["madrid"], "Q1492": ["barcelona", "tmb", "amb"], "Q8818": ["valencia"], "Q8851": ["málaga", "malaga"], "Q8692": ["bilbao"], "Q8717": ["sevilla"], "Q14328": ["tenerife"]}
CITY_RADIUS_M = 40000  # 광역 피드의 정류장 중 도시 중심 40km 안만


def hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(min(1, x)))


def rows(z, name):
    if name not in z.namelist():
        return []
    with z.open(name) as f:
        return [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"))]


def summarize(zpath, feed_label, center, out):
    z = zipfile.ZipFile(zpath)
    stops_all = rows(z, "stops.txt")
    keep = {}
    for s in stops_all:
        try:
            la, lo = float(s["stop_lat"]), float(s["stop_lon"])
        except (ValueError, KeyError):
            continue
        if hav(la, lo, center[0], center[1]) <= CITY_RADIUS_M and (s.get("location_type") in ("", "0", None)):
            keep[s["stop_id"]] = len(out["stops"]); out["stops"].append([round(la, 5), round(lo, 5), s.get("stop_name", "")[:60]])
    routes = {r["route_id"]: r for r in rows(z, "routes.txt")}
    trips = {t["trip_id"]: t["route_id"] for t in rows(z, "trips.txt")}
    seqs = collections.defaultdict(list)
    for st in rows(z, "stop_times.txt"):
        rid = trips.get(st["trip_id"])
        if rid is None or st["stop_id"] not in keep:
            continue
        seqs[(rid, st["trip_id"])].append((int(st["stop_sequence"]), keep[st["stop_id"]]))
    per_route = collections.defaultdict(set)
    for (rid, tid), lst in seqs.items():
        lst.sort(); per_route[rid].add(tuple(i for _, i in lst))
    n_routes = 0
    for rid, variants in per_route.items():
        r = routes.get(rid, {})
        # 가장 긴 정차 순서 두 개(방향)만 저장
        vs = sorted(variants, key=len, reverse=True)[:2]
        out["routes"].append({"id": rid, "name": (r.get("route_short_name") or r.get("route_long_name") or rid)[:40], "long": (r.get("route_long_name") or "")[:80], "type": int(r.get("route_type") or 3), "feed": feed_label, "seq": [list(v) for v in vs]})
        n_routes += 1
    for fa in rows(z, "fare_attributes.txt")[:5]:
        try:
            out["fares"].append({"feed": feed_label, "price": float(fa.get("price") or 0), "currency": fa.get("currency_type") or "EUR", "id": fa.get("fare_id")})
        except ValueError:
            pass
    return n_routes


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("catalog"); ap.add_argument("feeds"); ap.add_argument("renfe"); ap.add_argument("cities"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cat = json.load(open(a.catalog, encoding="utf-8")); cities = {c["id"]: c for c in json.load(gzip.open(a.cities, "rt", encoding="utf-8"))}
    out_dir = pathlib.Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)
    for q, words in FEED_CITY_WORDS.items():
        c = cities.get(q)
        if not c:
            continue
        out = {"city": q, "stops": [], "routes": [], "fares": [], "feeds": []}
        for r in cat:
            text = f"{r.get('provider', '')} {r.get('name', '')} {r.get('municipality', '')}".lower()
            if r.get("http") != 200 or not r.get("routes") or not any(w in text for w in words):
                continue
            zp = pathlib.Path(a.feeds) / f"{r['mdb_id']}.zip"
            if not zp.exists():
                continue
            n = summarize(zp, r["provider"][:30], (c["lat"], c["lon"]), out)
            out["feeds"].append({"mdb": r["mdb_id"], "provider": r["provider"], "routes": n, "license": r.get("catalog_license"), "valid_to": r.get("max_date")})
        for zp in sorted(pathlib.Path(a.renfe).glob("*.zip")):
            n = summarize(zp, "Renfe " + zp.stem.split("_", 1)[-1][:20], (c["lat"], c["lon"]), out)
            if n:
                out["feeds"].append({"provider": "Renfe", "file": zp.name, "routes": n, "license": "CC BY 4.0"})
        p = out_dir / f"{q}.json.gz"
        with gzip.open(p, "wt", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  {c['n'].get('ko') or q}: 정류장 {len(out['stops']):,}, 노선 {len(out['routes'])}, 요금 {len(out['fares'])}, 피드 {len(out['feeds'])} → {p.stat().st_size / 1e3:.0f}KB", flush=True)


if __name__ == "__main__":
    main()
