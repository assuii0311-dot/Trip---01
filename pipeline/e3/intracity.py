"""E3 사전 계산 2: 도시 안 도보 쌍. 1등급 장소(사이트링크 1개 이상 또는 가이드 수록) 중 2km 안 쌍의 도보 시간·거리를 로컬 경로 엔진 행렬로 계산한다 (E3 4절 1항, D-025 (b)).

출력 travel/<city>.json.gz: {ids:[...], pairs:[[i, j, walk_min, dist_m], ...]} (i<j, 양방향 동일로 본다). 출발지마다 가까운 80곳까지.
실행: python -I pipeline/run.py e3.intracity <타일 디렉터리> <places_tier1.json.gz> --out <travel 디렉터리> [--min-places 2] [--max-targets 80]
"""
import argparse
import collections
import gzip
import json
import math
import pathlib
import time

R_PAIR_M = 2000.0
WALK_CORRECTION = 1.12  # D-025 (c)


def hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(min(1, x)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("tiles"); ap.add_argument("tier1"); ap.add_argument("--out", required=True); ap.add_argument("--min-places", type=int, default=2); ap.add_argument("--max-targets", type=int, default=80); ap.add_argument("--only")
    a = ap.parse_args(); t0 = time.time()
    from valhalla import Actor, get_config
    cfg = get_config(tile_dir=a.tiles, tile_extract="")
    cfg["service_limits"]["pedestrian"]["max_matrix_location_pairs"] = 50000; cfg["service_limits"]["pedestrian"]["max_locations"] = 500
    actor = Actor(cfg)
    places = json.load(gzip.open(a.tier1, "rt", encoding="utf-8"))
    by_city = collections.defaultdict(list)
    for p in places:
        if p["city"] and (p["pop"]["sl"] >= 1 or p["src"]["wv"]):
            by_city[p["city"]].append(p)
    out_dir = pathlib.Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)
    done = 0; total_pairs = 0; skipped = 0
    cities = sorted(by_city.items(), key=lambda kv: -len(kv[1]))
    for q, ps in cities:
        if a.only and q != a.only:
            continue
        if len(ps) < a.min_places:
            skipped += 1; continue
        ps.sort(key=lambda p: p["id"])
        n = len(ps); cell = 0.02; grid = collections.defaultdict(list)
        for i, p in enumerate(ps):
            grid[(int(p["lat"] / cell), int(p["lon"] / cell))].append(i)
        pairs = {}
        for i, p in enumerate(ps):
            kx, ky = int(p["lat"] / cell), int(p["lon"] / cell)
            cands = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in grid.get((kx + dx, ky + dy), ()):
                        if j != i:
                            d = hav(p["lat"], p["lon"], ps[j]["lat"], ps[j]["lon"])
                            if d <= R_PAIR_M:
                                cands.append((d, j))
            cands.sort(); targets = [j for _, j in cands[:a.max_targets] if (min(i, j), max(i, j)) not in pairs]
            if not targets:
                continue
            try:
                m = actor.matrix({"sources": [{"lat": p["lat"], "lon": p["lon"]}], "targets": [{"lat": ps[j]["lat"], "lon": ps[j]["lon"]} for j in targets], "costing": "pedestrian"})
            except Exception:
                continue
            for j, c in zip(targets, m["sources_to_targets"][0]):
                if c.get("time") is not None:
                    pairs[(min(i, j), max(i, j))] = (round(c["time"] / 60 * WALK_CORRECTION, 1), round(c["distance"] * 1000))
        obj = {"ids": [p["id"] for p in ps], "pairs": [[i, j, t, d] for (i, j), (t, d) in sorted(pairs.items())], "correction": WALK_CORRECTION}
        with gzip.open(out_dir / f"{q}.json.gz", "wt", encoding="utf-8") as f:
            json.dump(obj, f, separators=(",", ":"))
        done += 1; total_pairs += len(pairs)
        if done % 50 == 0 or n >= 300:
            print(f"  {done}번째 {q}: 장소 {n}, 쌍 {len(pairs):,} ({time.time() - t0:.0f}초)", flush=True)
    print(f"  완료: 도시 {done}개, 쌍 {total_pairs:,}, 건너뜀(장소 {a.min_places}곳 미만) {skipped}, {time.time() - t0:.0f}초", flush=True)


if __name__ == "__main__":
    main()
