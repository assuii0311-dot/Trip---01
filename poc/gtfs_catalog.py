#!/usr/bin/env python3
"""2단계 PoC E 단계: Mobility Database 카탈로그에서 스페인 주요 운영사의 GTFS 피드를 공개 주소(urls.latest)로 내려받아 검사한다 (P-06, P-11, P-15).

카탈로그: https://bit.ly/catalogs-csv (MobilityData). 공개 저장소의 최신 파일 주소라 인증이 필요 없다.
검사: 노선·정류장·운행 수, 요금 파일(fare_attributes, fare_rules, fare_products) 유무, 유효 기간, 라이선스 안내.
실행: python -I poc/gtfs_catalog.py <카탈로그 CSV> <저장 디렉터리> <출력 JSON>
"""
import csv
import io
import json
import pathlib
import sys
import time
import zipfile

import requests

UA = "Trip01-PoC/0.1 (https://github.com/assuii0311-dot/Trip---01)"
KEYS = ["crtm", "transportes de madrid", "emt madrid", "metro de madrid", "tmb", "transports metropolitans de barcelona", "àrea metropolitana de barcelona", "amb - barcelona",
        "tram barcelona", "emt valencia", "metrovalencia", "metro de valencia", "metro de sevilla", "metro de málaga", "malagueña", "metro bilbao", "andalusian", "andalucía",
        "metrotenerife", "generalitat valenciana (intercity", "public works agency"]


def rows_of(z, name):
    try:
        with z.open(name) as f:
            return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace")))
    except KeyError:
        return None


def main():
    cat, d, out = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3]
    d.mkdir(parents=True, exist_ok=True)
    rows = [r for r in csv.DictReader(open(cat, encoding="utf-8")) if r.get("location.country_code") == "ES" and r.get("data_type") == "gtfs" and r.get("status") != "deprecated"]
    picked, seen = [], set()
    for r in rows:
        p = (r.get("provider") or "").lower()
        if any(k in p for k in KEYS) and r.get("urls.latest") and r["mdb_source_id"] not in seen:
            seen.add(r["mdb_source_id"]); picked.append(r)
    print(f"  스페인 활성 GTFS {len(rows)}건 중 주요 운영사 {len(picked)}건 선택", flush=True)
    sess = requests.Session(); sess.headers["User-Agent"] = UA
    results = []
    for r in picked[:22]:
        name = f"{r.get('provider','')[:45]} / {r.get('name','')[:30]}"
        rec = {"mdb_id": r["mdb_source_id"], "provider": r.get("provider"), "name": r.get("name"), "municipality": r.get("location.municipality"), "catalog_license": r.get("urls.license"), "latest": r.get("urls.latest")}
        t = time.time()
        try:
            resp = sess.get(r["urls.latest"], timeout=180)
            rec["http"] = resp.status_code; rec["mb"] = round(len(resp.content) / 1e6, 1)
            if resp.status_code == 200 and resp.content[:2] == b"PK":
                path = d / f"{r['mdb_source_id']}.zip"; path.write_bytes(resp.content)
                z = zipfile.ZipFile(path); files = z.namelist(); rec["files"] = files
                for k in ("routes", "stops", "trips"):
                    rs = rows_of(z, f"{k}.txt"); rec[k] = len(rs) if rs is not None else None
                rec["route_types"] = sorted({x.get("route_type") for x in (rows_of(z, "routes.txt") or [])})
                rec["fare_attributes"] = "fare_attributes.txt" in files; rec["fare_rules"] = "fare_rules.txt" in files
                rec["fare_v2"] = [f for f in files if f.startswith("fare_") and f not in ("fare_attributes.txt", "fare_rules.txt")]
                fa = rows_of(z, "fare_attributes.txt") or []
                rec["fare_samples"] = [(x.get("price"), x.get("currency_type")) for x in fa[:3]]
                dates = []
                for cal, col in (("calendar.txt", "end_date"), ("calendar_dates.txt", "date")):
                    for x in (rows_of(z, cal) or []):
                        if x.get(col): dates.append(x[col])
                rec["max_date"] = max(dates) if dates else None
                fi = rows_of(z, "feed_info.txt") or []
                if fi: rec["feed_info"] = {k: fi[0].get(k) for k in ("feed_publisher_name", "feed_version", "feed_end_date") if fi[0].get(k)}
                if "licence_info.txt" in files or "license.txt" in files:
                    with z.open("licence_info.txt" if "licence_info.txt" in files else "license.txt") as f: rec["licence_file_head"] = f.read(300).decode("utf-8", "replace")
            else:
                rec["note"] = resp.content[:100].decode("utf-8", "replace")
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:60]}"
        rec["sec"] = round(time.time() - t, 1); results.append(rec)
        print(f"  {name[:60]:60} {rec.get('http')} {rec.get('mb')}MB 노선 {rec.get('routes')} 정류장 {rec.get('stops')} 유형 {rec.get('route_types')} 요금 {rec.get('fare_attributes')} v2 {bool(rec.get('fare_v2'))} 유효 {rec.get('max_date')}", flush=True)
        time.sleep(1.5)
    json.dump(results, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
