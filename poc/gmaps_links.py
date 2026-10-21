#!/usr/bin/env python3
"""2단계 PoC E 단계: 구글맵 연동 링크와 일괄 저장 파일의 형식을 검증용 표본으로 만든다 (R-27, P-18).

- 장소 링크: https://www.google.com/maps/search/?api=1&query=<위도>,<경도> 와 query=<명칭> (공식 Maps URLs 문서 형식)
- 경로 링크: https://www.google.com/maps/dir/?api=1&origin=..&destination=..&waypoints=a|b&travelmode=walking
  경유지 한도는 모바일 3개, 그 외 9개(Maps URLs 문서)이므로 하루 일정을 그 단위로 나눈 링크를 만든다.
- 일괄 저장: Google My Maps 가져오기용 CSV(이름, 설명, 위도, 경도)와 KML. My Maps 한도는 레이어당 2,000행, KML 5MB.
실행: python -I poc/gmaps_links.py <review_sample.json> <출력 디렉터리>
"""
import ast
import csv
import json
import pathlib
import sys
import urllib.parse
import xml.sax.saxutils as sx

SEARCH = "https://www.google.com/maps/search/?api=1&query={q}"
DIR = "https://www.google.com/maps/dir/?api=1&origin={o}&destination={d}{wp}&travelmode={mode}"
LIMITS = {"mobile": 3, "other": 9}


def ll(p):
    return f"{p['lat']:.6f},{p['lon']:.6f}"


def dir_links(points, mode="walking", limit=3):
    """경유지 한도(limit)에 맞춰 구간을 나눈 경로 링크 목록. 각 구간은 출발·도착 + 최대 limit 경유지."""
    links, i = [], 0
    while i < len(points) - 1:
        seg = points[i:i + limit + 2]
        wps = seg[1:-1]
        wp = "&waypoints=" + urllib.parse.quote("|".join(ll(p) for p in wps), safe="|,") if wps else ""
        links.append({"from": seg[0]["name"], "to": seg[-1]["name"], "via": [p["name"] for p in wps], "url": DIR.format(o=ll(seg[0]), d=ll(seg[-1]), wp=wp, mode=mode)})
        i += limit + 1
    return links


def kml(points, name):
    pm = "".join(f"<Placemark><name>{sx.escape(p['name'])}</name><description>{sx.escape(p.get('desc', ''))}</description><Point><coordinates>{p['lon']:.6f},{p['lat']:.6f},0</coordinates></Point></Placemark>" for p in points)
    return f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>{sx.escape(name)}</name>{pm}</Document></kml>'


def main():
    sample, out = json.load(open(sys.argv[1], encoding="utf-8")), pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    # review_sample.json: cities[].places[] (좌표는 문자열, osm/wd/wv는 dict의 repr 문자열)
    pts = []
    for c in sample.get("cities", []):
        for r in c.get("places", []):
            if r.get("no_coord") in (True, "True") or not r.get("lat"):
                continue
            name = None
            for src in ("osm", "wd", "wv"):
                d = r.get(src)
                if isinstance(d, str):  # 문자열로 저장된 경우만 해석
                    try:
                        d = ast.literal_eval(d)
                    except (ValueError, SyntaxError):
                        d = None
                if isinstance(d, dict):
                    name = d.get("name") or d.get("label_es") or d.get("label_en") or d.get("label")
                    if name:
                        break
            pts.append({"name": name or r["key"], "lat": float(r["lat"]), "lon": float(r["lon"]), "desc": f"{r.get('group', '')} / {c.get('name_es', '')}".strip(" /"), "id": r["key"]})
    print(f"  표본 장소 {len(pts)}곳 (좌표 보유)")
    # 1) 장소 링크
    place_links = [{"name": p["name"], "by_coord": SEARCH.format(q=ll(p)), "by_name": SEARCH.format(q=urllib.parse.quote(p["name"]))} for p in pts]
    # 2) 하루 일정 표본: 마드리드 근처 5곳 (위도 40.3~40.5, 경도 -3.8~-3.6) 없으면 앞 5곳
    day = [p for p in pts if 40.3 < p["lat"] < 40.5 and -3.8 < p["lon"] < -3.6][:6] or pts[:6]
    if len(day) < 4:
        day = [{"name": "Museo del Prado", "lat": 40.413781, "lon": -3.692127}, {"name": "Parque del Retiro", "lat": 40.415260, "lon": -3.684430}, {"name": "Puerta del Sol", "lat": 40.416947, "lon": -3.703527}, {"name": "Plaza Mayor", "lat": 40.415363, "lon": -3.707398}, {"name": "Palacio Real", "lat": 40.417955, "lon": -3.714312}, {"name": "Templo de Debod", "lat": 40.424055, "lon": -3.717758}]
    links = {k: dir_links(day, "walking", v) for k, v in LIMITS.items()}
    # 3) 일괄 저장 파일
    with open(out / "mymaps_sample.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["name", "description", "latitude", "longitude"])
        for p in pts:
            w.writerow([p["name"], p["desc"], f"{p['lat']:.6f}", f"{p['lon']:.6f}"])
    (out / "mymaps_sample.kml").write_text(kml(pts, "Trip01 PoC 표본"), encoding="utf-8")
    kml_bytes = (out / "mymaps_sample.kml").stat().st_size
    per_place = kml_bytes / max(len(pts), 1)
    summary = {"places": len(pts), "day_sample": [p["name"] for p in day], "dir_links": links, "place_links_sample": place_links[:3],
               "csv_bytes": (out / "mymaps_sample.csv").stat().st_size, "kml_bytes": kml_bytes, "kml_bytes_per_place": round(per_place),
               "kml_places_under_5mb": int(5_000_000 // per_place), "mymaps_rows_limit": 2000, "url_len_max": max(len(l["url"]) for v in links.values() for l in v)}
    json.dump(summary, open(out / "gmaps_links.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k, v in links.items():
        print(f"  경로 링크({k}, 경유지 {LIMITS[k]}): 구간 {len(v)}개")
        for l in v:
            print(f"    {l['from']} → {' → '.join(l['via'])} → {l['to']}\n      {l['url']}")
    print(f"  CSV {summary['csv_bytes']}바이트, KML {kml_bytes}바이트 (장소당 {round(per_place)}바이트 → 5MB 한도에 약 {summary['kml_places_under_5mb']:,}곳), URL 최대 길이 {summary['url_len_max']}")


if __name__ == "__main__":
    main()
