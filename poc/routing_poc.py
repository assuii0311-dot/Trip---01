#!/usr/bin/env python3
"""2단계 PoC E 단계: 공개 경로 서버(OSRM 데모, FOSSGIS)로 도보·차량 경로 계산 가능성과 품질을 표본 요청으로 확인한다 (P-05).

- 요청은 합계 500건 이하, 요청 간 1.1초 이상 (서버 정책: 초당 1회 이하, 비상업 합리적 사용).
- 도시 간 차량: Wikidata 인구 상위 도시 쌍. 도시 안 도보: 표본 도시의 OSM 장소 쌍.
- 기록: 성공률, 응답 시간, 경로 거리와 직선 거리의 비, 소요 시간. 경로 좌표는 저장하지 않는다.

실행: python -I poc/routing_poc.py <데이터 루트> <출력 JSON>
"""
import json
import math
import pathlib
import random
import re
import statistics
import sys
import time

import requests

UA = "Trip01-PoC/0.1 (https://github.com/assuii0311-dot/Trip---01)"
OSRM = "https://router.project-osrm.org"
FOSSGIS = "https://routing.openstreetmap.de"
PAUSE = 1.1
SEED = 20261021


def hav(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    dlat, dlon = (lat2 - lat1) * p, (lon2 - lon1) * p
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dlon / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def route(sess, base, profile, a, b):
    url = f"{base}/{profile}/route/v1/driving/{a[1]:.5f},{a[0]:.5f};{b[1]:.5f},{b[0]:.5f}?overview=false"
    t = time.time()
    try:
        r = sess.get(url, timeout=30)
        dt = time.time() - t
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code, "sec": round(dt, 2)}
        j = r.json()
        if j.get("code") != "Ok":
            return {"ok": False, "status": j.get("code"), "sec": round(dt, 2)}
        rt = j["routes"][0]
        return {"ok": True, "sec": round(dt, 2), "dist_m": round(rt["distance"]), "dur_s": round(rt["duration"])}
    except Exception as e:
        return {"ok": False, "status": type(e).__name__, "sec": round(time.time() - t, 2)}


def main():
    root, out = pathlib.Path(sys.argv[1]), sys.argv[2]
    rnd = random.Random(SEED)
    sess = requests.Session(); sess.headers["User-Agent"] = UA
    # 도시: 인구 상위 25개 지자체
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
    # 도시 안 장소: 마드리드 중심 3km 안 OSM 장소에서 쌍 60개 (도보), 세비야도 40개
    pois = []
    for line in open(root / "osm" / "out" / "pois.jsonl", encoding="utf-8"):
        o = json.loads(line)
        if o.get("name") and o["key"] in ("tourism", "historic", "amenity"):
            pois.append(o)
    def near(lat, lon, r_m):
        return [o for o in pois if abs(o["lat"] - lat) < 0.03 and abs(o["lon"] - lon) < 0.04 and hav(lat, lon, o["lat"], o["lon"]) <= r_m]
    madrid = near(40.4168, -3.7038, 3000); sevilla = near(37.3891, -5.9845, 3000)
    rnd.shuffle(madrid); rnd.shuffle(sevilla)
    walk_pairs = [(madrid[i], madrid[i + 1]) for i in range(0, 120, 2)] + [(sevilla[i], sevilla[i + 1]) for i in range(0, 80, 2)]
    results = {"driving_intercity": [], "foot_intracity_osrm": [], "foot_intracity_fossgis": []}
    n = 0
    for a, b in city_pairs:
        res = route(sess, OSRM, "routed-car" if False else "", "car", "car") if False else None
        url_base = OSRM
        res = route(sess, url_base, "", (a[2], a[3]), (b[2], b[3])) if False else None
        # OSRM 데모의 프로필 경로는 /route/v1/driving 고정
        t = time.time()
        try:
            r = sess.get(f"{OSRM}/route/v1/driving/{a[3]:.5f},{a[2]:.5f};{b[3]:.5f},{b[2]:.5f}?overview=false", timeout=30)
            j = r.json() if r.status_code == 200 else {}
            ok = r.status_code == 200 and j.get("code") == "Ok"
            rec = {"from": a[1], "to": b[1], "ok": ok, "sec": round(time.time() - t, 2), "status": r.status_code if not ok else "Ok"}
            if ok:
                rt = j["routes"][0]; sl = hav(a[2], a[3], b[2], b[3])
                rec.update({"dist_km": round(rt["distance"] / 1000, 1), "dur_min": round(rt["duration"] / 60), "straight_km": round(sl / 1000, 1), "ratio": round(rt["distance"] / sl, 2)})
        except Exception as e:
            rec = {"from": a[1], "to": b[1], "ok": False, "status": type(e).__name__}
        results["driving_intercity"].append(rec); n += 1
        print(f"  차량 {a[1][:14]:14}→{b[1][:14]:14} {rec.get('status')} {rec.get('dist_km','')}km {rec.get('dur_min','')}분 비 {rec.get('ratio','')}", flush=True)
        time.sleep(PAUSE)
    for key, base, path in (("foot_intracity_osrm", OSRM, "/route/v1/foot"), ("foot_intracity_fossgis", FOSSGIS, "/routed-foot/route/v1/driving")):
        for a, b in walk_pairs[: 50 if key.endswith("osrm") else 50]:
            t = time.time()
            try:
                r = sess.get(f"{base}{path}/{a['lon']:.5f},{a['lat']:.5f};{b['lon']:.5f},{b['lat']:.5f}?overview=false", timeout=30)
                j = r.json() if r.status_code == 200 else {}
                ok = r.status_code == 200 and j.get("code") == "Ok"
                rec = {"ok": ok, "sec": round(time.time() - t, 2), "status": r.status_code if not ok else "Ok"}
                if ok:
                    rt = j["routes"][0]; sl = hav(a["lat"], a["lon"], b["lat"], b["lon"])
                    rec.update({"dist_m": round(rt["distance"]), "dur_min": round(rt["duration"] / 60, 1), "straight_m": round(sl), "ratio": round(rt["distance"] / max(sl, 1), 2)})
            except Exception as e:
                rec = {"ok": False, "status": type(e).__name__}
            results[key].append(rec); n += 1
            time.sleep(PAUSE)
        oks = [x for x in results[key] if x["ok"]]
        print(f"  {key}: 성공 {len(oks)}/{len(results[key])}, 응답 중앙값 {statistics.median(x['sec'] for x in results[key]):.2f}초, 경로/직선 비 중앙값 {statistics.median(x['ratio'] for x in oks) if oks else None}", flush=True)
    d = results["driving_intercity"]; oks = [x for x in d if x["ok"]]
    summary = {"requests_total": n, "driving": {"n": len(d), "ok": len(oks), "sec_median": statistics.median(x["sec"] for x in d) if d else None,
               "ratio_median": statistics.median(x["ratio"] for x in oks) if oks else None, "speed_kmh_median": statistics.median(x["dist_km"] / (x["dur_min"] / 60) for x in oks if x["dur_min"]) if oks else None}}
    for key in ("foot_intracity_osrm", "foot_intracity_fossgis"):
        f = results[key]; oks = [x for x in f if x["ok"]]
        summary[key] = {"n": len(f), "ok": len(oks), "sec_median": statistics.median(x["sec"] for x in f) if f else None, "ratio_median": statistics.median(x["ratio"] for x in oks) if oks else None,
                        "speed_kmh_median": statistics.median((x["dist_m"] / 1000) / (x["dur_min"] / 60) for x in oks if x["dur_min"]) if oks else None, "fail_status": [x["status"] for x in f if not x["ok"]][:5]}
    json.dump({"summary": summary, "driving_intercity": d, "foot_osrm": results["foot_intracity_osrm"], "foot_fossgis": results["foot_intracity_fossgis"]}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  요약:", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
