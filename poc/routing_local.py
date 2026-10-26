#!/usr/bin/env python3
"""2단계 PoC E 단계: 로컬 경로 엔진(pyvalhalla, OSM 스페인 추출본 타일)으로 routing_poc.py의 표본 쌍을 다시 계산해 공개 서버 결과와 비교한다 (P-05).

- 차량 도시 간 60쌍: OSRM 데모 결과와 거리·시간 비교
- 도보 도시 안 50쌍: FOSSGIS 도보 결과와 비교
- 행렬 성능: 도시 안 N×N 도보 행렬 소요 시간
실행: python -I poc/routing_local.py <타일 디렉터리> <데이터 루트> <routing_poc.json> <출력 JSON>
"""
import json
import pathlib
import random
import re
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import routing_poc as R  # noqa: E402

from valhalla import Actor, get_config


def med(xs):
    return round(statistics.median(xs), 3) if xs else None


def pairs_from(root):
    """routing_poc.py와 같은 난수 씨앗으로 같은 표본 쌍을 다시 만든다 (좌표는 결과 JSON에 저장하지 않았기 때문)."""
    rnd = random.Random(R.SEED)
    munis = []
    for line in open(root / "wikidata" / "Q2074737.jsonl", encoding="utf-8"):
        r = json.loads(line)
        m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", r.get("coord") or "")
        if m and r.get("pop"):
            munis.append((float(r["pop"]), r.get("label_es") or r["qid"], float(m.group(2)), float(m.group(1))))
    munis.sort(reverse=True)
    top = munis[:25]
    pairs = [(a, b) for i, a in enumerate(top) for b in top[i + 1:]]
    rnd.shuffle(pairs)
    city_pairs = pairs[:60]
    pois = []
    for line in open(root / "osm" / "out" / "pois.jsonl", encoding="utf-8"):
        o = json.loads(line)
        if o.get("name") and o["key"] in ("tourism", "historic", "amenity"):
            pois.append(o)
    def near(lat, lon, r_m):
        return [o for o in pois if abs(o["lat"] - lat) < 0.03 and abs(o["lon"] - lon) < 0.04 and R.hav(lat, lon, o["lat"], o["lon"]) <= r_m]
    madrid = near(40.4168, -3.7038, 3000); sevilla = near(37.3891, -5.9845, 3000)
    rnd.shuffle(madrid); rnd.shuffle(sevilla)
    walk_pairs = [(madrid[i], madrid[i + 1]) for i in range(0, 120, 2)] + [(sevilla[i], sevilla[i + 1]) for i in range(0, 80, 2)]
    return city_pairs, walk_pairs[:50]


def main():
    tiles, root, src, out = sys.argv[1], pathlib.Path(sys.argv[2]), json.load(open(sys.argv[3], encoding="utf-8")), sys.argv[4]
    city_pairs, walk_pairs = pairs_from(root)
    assert [(a[1], b[1]) for a, b in city_pairs][:3] == [(r["from"], r["to"]) for r in src["driving_intercity"][:3]], "표본 쌍 재현 실패"
    cfg = get_config(tile_dir=tiles, tile_extract="")
    for k in ("pedestrian", "auto", "bicycle"):  # 기본 한도(행렬 2,500쌍)를 PoC 측정용으로 올린다
        cfg["service_limits"][k]["max_matrix_location_pairs"] = 20000
        cfg["service_limits"][k]["max_matrix_distance"] = 2000000
    actor = Actor(cfg)
    res = {"driving": [], "foot": []}
    jobs = (("driving", "auto", [({"lat": a[2], "lon": a[3]}, {"lat": b[2], "lon": b[3]}, r) for (a, b), r in zip(city_pairs, src["driving_intercity"])]),
            ("foot", "pedestrian", [({"lat": a["lat"], "lon": a["lon"]}, {"lat": b["lat"], "lon": b["lon"]}, r) for (a, b), r in zip(walk_pairs, src["foot_fossgis"])]))
    for key, costing, rows in jobs:
        for a, b, r in rows:
            t = time.time()
            try:
                rt = actor.route({"locations": [a, b], "costing": costing, "units": "kilometers"})
                s = rt["trip"]["summary"]
                rec = {"ok": True, "sec": round(time.time() - t, 3), "dist_km": round(s["length"], 2), "dur_min": round(s["time"] / 60, 1)}
            except Exception as e:
                rec = {"ok": False, "sec": round(time.time() - t, 3), "error": str(e)[:80]}
            ref_km = r.get("dist_km") if key == "driving" else (r.get("dist_m") or 0) / 1000
            ref_min = r.get("dur_min")
            rec.update({"from": r.get("from"), "to": r.get("to"), "ref_km": ref_km, "ref_min": ref_min})
            if rec["ok"] and ref_km:
                rec["km_ratio"] = round(rec["dist_km"] / ref_km, 3)
            if rec["ok"] and ref_min:
                rec["min_ratio"] = round(rec["dur_min"] / ref_min, 3)
            res[key].append(rec)
    pts = [{"lat": a["lat"], "lon": a["lon"]} for a, _ in walk_pairs[:30]] + [{"lat": b["lat"], "lon": b["lon"]} for _, b in walk_pairs[:30]]
    summary = {}
    for key in ("driving", "foot"):
        rows = res[key]; ok = [x for x in rows if x["ok"]]
        summary[key] = {"n": len(rows), "ok": len(ok), "sec_median": med([x["sec"] for x in ok]), "km_ratio_median": med([x["km_ratio"] for x in ok if "km_ratio" in x]), "min_ratio_median": med([x["min_ratio"] for x in ok if "min_ratio" in x]),
                        "km_ratio_p10_p90": (med(sorted(x["km_ratio"] for x in ok if "km_ratio" in x)[:max(1, len(ok) // 10)]), med(sorted(x["km_ratio"] for x in ok if "km_ratio" in x)[-max(1, len(ok) // 10):])) if ok else None,
                        "errors": [x["error"] for x in rows if not x["ok"]][:3]}
    # 행렬 성능: 마드리드 도보 표본 지점(최대 60곳)으로 N×N
    for n in (10, 30, 60):
        sub = pts[:n]
        if len(sub) < n:
            break
        t = time.time()
        try:
            m = actor.matrix({"sources": sub, "targets": sub, "costing": "pedestrian"})
            cells = [c for row in m["sources_to_targets"] for c in row]
            summary[f"matrix_{n}x{n}_pedestrian"] = {"sec": round(time.time() - t, 2), "cells": len(cells), "unreachable": sum(1 for c in cells if c.get("time") is None)}
        except Exception as e:
            summary[f"matrix_{n}x{n}_pedestrian"] = {"error": str(e)[:80]}
    json.dump({"summary": summary, **res}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
