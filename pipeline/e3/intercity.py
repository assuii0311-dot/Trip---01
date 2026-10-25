"""E3 사전 계산 1: 도시 간 행렬. 인구 상위 60개 도시 + 공항 도시의 차량 행렬(로컬 경로 엔진)과 Renfe GTFS 직통 최단 운행 시간.

출력 travel/intercity.json.gz: {cities:[{id, n, lat, lon}], car_min[][], car_km[][], train_min[][], trains_per_day[][], unreachable 쌍은 null}
실행: python -I pipeline/run.py e3.intercity <타일 디렉터리> <cities.json.gz> <airports.json.gz> <Renfe GTFS zip...> --out <travel 디렉터리>
"""
import argparse
import collections
import csv
import gzip
import io
import json
import math
import pathlib
import time
import zipfile

TOP_N = 60  # D-025 (a)


def hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(min(1, x)))


def pick_cities(cities, airports):
    by_pop = sorted([c for c in cities if c.get("pop")], key=lambda c: -c["pop"])[:TOP_N]
    ids = {c["id"] for c in by_pop}
    # 공항에서 가장 가까운 지자체를 추가(섬 공항 포함)
    for a in airports:
        best = min(cities, key=lambda c: hav(a["lat"], a["lon"], c["lat"], c["lon"]))
        if best["id"] not in ids and hav(a["lat"], a["lon"], best["lat"], best["lon"]) < 30000 and (best.get("pop") or 0) >= 20000:
            ids.add(best["id"]); by_pop.append(best)
    return by_pop


def car_matrix(tiles, pts):
    from valhalla import Actor, get_config
    cfg = get_config(tile_dir=tiles, tile_extract="")
    cfg["service_limits"]["auto"]["max_matrix_location_pairs"] = 50000; cfg["service_limits"]["auto"]["max_matrix_distance"] = 5000000; cfg["service_limits"]["auto"]["max_locations"] = 200
    actor = Actor(cfg)
    locs = [{"lat": p["lat"], "lon": p["lon"]} for p in pts]
    n = len(locs); mins = [[None] * n for _ in range(n)]; kms = [[None] * n for _ in range(n)]
    for i0 in range(0, n, 25):
        m = actor.matrix({"sources": locs[i0:i0 + 25], "targets": locs, "costing": "auto"})
        for di, row in enumerate(m["sources_to_targets"]):
            for j, c in enumerate(row):
                if c.get("time") is not None:
                    mins[i0 + di][j] = round(c["time"] / 60 * 1.23)  # 속도 보정 ×1.23 (D-025 (c))
                    kms[i0 + di][j] = round(c["distance"], 1)
    return mins, kms


def rows(z, name):
    with z.open(name) as f:
        return [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"))]


def train_times(gtfs_paths, pts):
    """역 → 가장 가까운 대상 도시(15km 안). 각 운행(trip)의 정차 순서에서 도시 쌍별 최단 소요와 하루 운행 수."""
    n = len(pts); best = [[None] * n for _ in range(n)]; cnt = [[0] * n for _ in range(n)]
    for path in gtfs_paths:
        z = zipfile.ZipFile(path)
        stops = {s["stop_id"]: (float(s["stop_lat"]), float(s["stop_lon"])) for s in rows(z, "stops.txt") if s.get("stop_lat")}
        stop_city = {}
        for sid, (la, lo) in stops.items():
            j, d = min(((j, hav(la, lo, p["lat"], p["lon"])) for j, p in enumerate(pts)), key=lambda x: x[1])
            if d <= 15000:
                stop_city[sid] = j
        # 운행 수: calendar 기준 평일 운행 service_id 수를 세지 않고, 운행(trip) 수 ÷ 유효 일수로 근사한다(추정)
        cal = rows(z, "calendar.txt") if "calendar.txt" in z.namelist() else []
        days = 0
        for c in cal:
            try:
                s, e = c.get("start_date"), c.get("end_date")
                if s and e:
                    from datetime import datetime
                    days = max(days, (datetime.strptime(e, "%Y%m%d") - datetime.strptime(s, "%Y%m%d")).days + 1)
            except ValueError:
                pass
        days = max(days, 1)
        by_trip = collections.defaultdict(list)
        for st in rows(z, "stop_times.txt"):
            if st["stop_id"] in stop_city:
                by_trip[st["trip_id"]].append((int(st["stop_sequence"]), st["arrival_time"] or st["departure_time"], stop_city[st["stop_id"]]))
        def sec(t):
            h, m, s = t.split(":"); return int(h) * 3600 + int(m) * 60 + int(s)
        pair_trips = collections.Counter()
        for tid, seq in by_trip.items():
            seq.sort()
            for a in range(len(seq)):
                for b in range(a + 1, len(seq)):
                    ca, cb = seq[a][2], seq[b][2]
                    if ca == cb:
                        continue
                    try:
                        dur = (sec(seq[b][1]) - sec(seq[a][1])) / 60
                    except (ValueError, AttributeError):
                        continue
                    if dur <= 0:
                        continue
                    if best[ca][cb] is None or dur < best[ca][cb]:
                        best[ca][cb] = round(dur)
                    pair_trips[(ca, cb)] += 1
        for (a, b), k in pair_trips.items():
            cnt[a][b] += round(k / days, 1)
    return best, cnt


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("tiles"); ap.add_argument("cities"); ap.add_argument("airports"); ap.add_argument("gtfs", nargs="*"); ap.add_argument("--out", required=True)
    a = ap.parse_args(); t0 = time.time()
    cities = json.load(gzip.open(a.cities, "rt", encoding="utf-8")); airports = json.load(gzip.open(a.airports, "rt", encoding="utf-8"))
    pts = pick_cities(cities, airports)
    print(f"  대상 도시 {len(pts)}곳", flush=True)
    car_min, car_km = car_matrix(a.tiles, pts); print(f"  차량 행렬 완료 ({time.time() - t0:.0f}초), 도달 불가 {sum(1 for r in car_min for v in r if v is None)}셀", flush=True)
    tr_min, tr_cnt = train_times(a.gtfs, pts); print(f"  기차 직통 쌍 {sum(1 for r in tr_min for v in r if v)}개 ({time.time() - t0:.0f}초)", flush=True)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    obj = {"generated": time.strftime("%Y-%m-%d"), "correction": {"car": 1.23}, "cities": [{"id": c["id"], "n": c["n"].get("ko") or c["n"].get("es"), "lat": c["lat"], "lon": c["lon"]} for c in pts], "car_min": car_min, "car_km": car_km, "train_min": tr_min, "trains_per_day": tr_cnt}
    with gzip.open(out / "intercity.json.gz", "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  저장 {out / 'intercity.json.gz'} ({(out / 'intercity.json.gz').stat().st_size / 1e3:.0f}KB)", flush=True)


if __name__ == "__main__":
    main()
