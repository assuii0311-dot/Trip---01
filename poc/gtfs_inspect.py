#!/usr/bin/env python3
"""2단계 PoC E 단계: GTFS 피드를 내려받아 구성 파일과 규모, 요금 파일 유무를 검사한다 (P-06, P-11, P-15).

입력: 이름과 URL 목록. 출력: 피드별 파일 목록, 노선·정류장·운행 수, 요금 파일 유무, 라이선스 메모.
실행: python -I poc/gtfs_inspect.py <저장 디렉터리> <출력 JSON>
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
FEEDS = [
    ("Renfe 고속·장거리·중거리", "https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip", "CC BY 4.0"),
    ("Renfe Cercanías(광역전철)", "https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip", "CC BY 4.0"),
    ("NAP 마드리드 광역버스(1361)", "https://nap.transportes.gob.es/api/Fichero/download/1361", "미확인"),
    ("NAP 바르셀로나 광역버스(1496)", "https://nap.transportes.gob.es/api/Fichero/download/1496", "미확인"),
    ("NAP 발렌시아 광역버스(1526)", "https://nap.transportes.gob.es/api/Fichero/download/1526", "CC BY 4.0"),
]


def count_rows(z, name):
    try:
        with z.open(name) as f:
            return sum(1 for _ in io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace")) - 1
    except KeyError:
        return None


def main():
    d, out = pathlib.Path(sys.argv[1]), sys.argv[2]
    d.mkdir(parents=True, exist_ok=True)
    sess = requests.Session(); sess.headers["User-Agent"] = UA
    results = []
    for name, url, lic in FEEDS:
        t = time.time()
        rec = {"feed": name, "url": url, "license": lic}
        try:
            r = sess.get(url, timeout=120, allow_redirects=True)
            rec["http"] = r.status_code; rec["bytes"] = len(r.content); rec["content_type"] = r.headers.get("Content-Type", "")[:40]
            if r.status_code == 200 and r.content[:2] == b"PK":
                path = d / (name.split("(")[0].replace(" ", "_").replace("·", "_") + ".zip")
                path.write_bytes(r.content)
                z = zipfile.ZipFile(path)
                files = z.namelist()
                rec["files"] = files
                rec["routes"] = count_rows(z, "routes.txt"); rec["stops"] = count_rows(z, "stops.txt"); rec["trips"] = count_rows(z, "trips.txt")
                rec["fare_attributes"] = "fare_attributes.txt" in files; rec["fare_rules"] = "fare_rules.txt" in files
                rec["fare_products"] = any(f.startswith("fare_") for f in files if f not in ("fare_attributes.txt", "fare_rules.txt"))
                if "agency.txt" in files:
                    with z.open("agency.txt") as f:
                        rec["agencies"] = [row.get("agency_name") for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))][:5]
                if "calendar.txt" in files or "calendar_dates.txt" in files:
                    for cal in ("calendar.txt", "calendar_dates.txt"):
                        if cal in files:
                            with z.open(cal) as f:
                                dates = [(row.get("end_date") or row.get("date") or "").strip() for row in ({k.strip(): v for k, v in r.items() if k} for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))]  # Renfe 헤더에 공백 패딩이 있어 열 이름을 strip
                            rec["max_date"] = max((x for x in dates if x), default=None)  # 빈 파일이면 None
                            break
            else:
                rec["note"] = "zip 아님 또는 오류. 본문 앞부분: " + r.content[:120].decode("utf-8", "replace").replace("\n", " ")
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:80]}"
        rec["sec"] = round(time.time() - t, 1)
        results.append(rec)
        print(f"  {name}: HTTP {rec.get('http')} {rec.get('bytes', 0)/1e6:.1f}MB 노선 {rec.get('routes')} 정류장 {rec.get('stops')} 운행 {rec.get('trips')} 요금 {rec.get('fare_attributes')}/{rec.get('fare_rules')} 유효 {rec.get('max_date')} {rec.get('note', rec.get('error', ''))[:100]}", flush=True)
        time.sleep(2)
    json.dump(results, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
