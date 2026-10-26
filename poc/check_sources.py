#!/usr/bin/env python3
"""2단계 PoC A 단계: 데이터 소스 접속 확인.

이 개발 환경에서 각 후보 소스에 접속되는지, HTTP 응답 코드와 크기를 기록한다.
본문은 읽지 않고 헤더까지만 받으므로 대량 호출이 아니다.

실행: python3 -I poc/check_sources.py [--json 출력파일]
"""
import json
import sys
import urllib.error
import urllib.request

UA = "Trip01-PoC/0.1 (https://github.com/assuii0311-dot/Trip---01)"

# (소스, URL, 관련 확인 항목, 비고)
SOURCES = [
    # 장소 후보와 속성
    ("Wikidata SPARQL", "https://query.wikidata.org/sparql?format=json&query=SELECT%20%3Fx%20WHERE%20%7B%3Fx%20wdt%3AP31%20wd%3AQ2074737%7D%20LIMIT%201", "P-01", "스페인 지자체 1건 조회"),
    ("Wikidata 엔티티 API", "https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q8717&props=labels&languages=es|en|ko&format=json", "P-10", "세비야 라벨"),
    ("영문 Wikivoyage API", "https://en.wikivoyage.org/w/api.php?action=query&titles=Seville&prop=revisions&rvprop=size&format=json", "P-01", ""),
    ("영문 Wikivoyage 덤프", "https://dumps.wikimedia.org/enwikivoyage/latest/enwikivoyage-latest-pages-articles.xml.bz2", "P-01", "크기 확인"),
    ("스페인어 Wikivoyage 덤프", "https://dumps.wikimedia.org/eswikivoyage/latest/eswikivoyage-latest-pages-articles.xml.bz2", "P-17", "크기 확인"),
    ("영문 위키백과 API", "https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exintro&explaintext&titles=Seville&format=json", "P-08", "설명 추출"),
    ("한국어 위키백과 API", "https://ko.wikipedia.org/w/api.php?action=query&prop=extracts&exintro&explaintext&titles=%EC%84%B8%EB%B9%84%EC%95%BC&format=json", "P-08", ""),
    ("스페인어 위키백과 API", "https://es.wikipedia.org/w/api.php?action=query&prop=extracts&exintro&explaintext&titles=Sevilla&format=json", "P-17", ""),
    ("Wikimedia 페이지뷰 REST", "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/es.wikipedia/all-access/user/Sevilla/monthly/2025090100/2025093000", "P-17", "429 예상"),
    ("Wikimedia 페이지뷰 덤프", "https://dumps.wikimedia.org/other/pageview_complete/monthly/2025/2025-09/", "P-17", "대체 경로"),
    ("Wikimedia API 포털(토큰)", "https://api.wikimedia.org/core/v1/wikipedia/es/page/Sevilla/bare", "P-17", "인증 토큰 경로"),
    # OpenStreetMap
    ("OSM 추출본 openstreetmap.fr", "https://download.openstreetmap.fr/extracts/europe/spain.osm.pbf", "P-12", "크기 확인"),
    ("OSM 추출본 openstreetmap.fr latest", "https://download.openstreetmap.fr/extracts/europe/spain-latest.osm.pbf", "P-12", ""),
    ("OSM 추출본 Geofabrik", "https://download.geofabrik.de/europe/spain-latest.osm.pbf", "P-12", "차단 예상"),
    ("OSM 플래닛", "https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf", "P-12", "크기만 확인"),
    ("OSM bbbike 마드리드", "https://download.bbbike.org/osm/bbbike/Madrid/Madrid.osm.pbf", "P-12", "도시 단위"),
    ("Overpass 본 서버", "https://overpass-api.de/api/status", "P-12", "차단 예상"),
    ("Overpass kumi", "https://overpass.kumi.systems/api/status", "P-12", ""),
    ("Overpass private.coffee", "https://overpass.private.coffee/api/status", "P-12", ""),
    ("Overpass osm.jp", "https://overpass.osm.jp/api/status", "P-12", ""),
    ("Nominatim", "https://nominatim.openstreetmap.org/status", "P-12", "대량 금지, 참고용"),
    # 이동
    ("OSRM 데모 route", "https://router.project-osrm.org/route/v1/driving/-3.7038,40.4168;-3.6900,40.4200?overview=false", "P-05", ""),
    ("OSRM 데모 table", "https://router.project-osrm.org/table/v1/driving/-3.7038,40.4168;-3.6900,40.4200;-3.7000,40.4100", "P-05", "행렬"),
    ("OSRM 데모 foot", "https://routing.openstreetmap.de/routed-foot/route/v1/driving/-3.7038,40.4168;-3.6900,40.4200?overview=false", "P-05", "도보 프로필"),
    ("Transitous geocode", "https://api.transitous.org/api/v1/geocode?text=Sevilla", "P-06", ""),
    ("Transitous plan", "https://api.transitous.org/api/v1/plan?fromPlace=40.4168,-3.7038&toPlace=40.4530,-3.6883&time=2026-11-03T09:00:00Z", "P-06", "마드리드 시내"),
    ("Transitous 사이트", "https://transitous.org/", "P-06", "이용 조건"),
    ("Renfe 공개 데이터", "https://data.renfe.com/api/3/action/package_search?q=gtfs", "P-15", "CKAN API"),
    ("스페인 교통 데이터 포털", "https://nap.transportes.gob.es/", "P-15", "가입 여부"),
    ("OpenRouteService", "https://api.openrouteservice.org/", "P-05", "키 필요"),
    # 비용, 링크
    ("구글맵 경로 링크", "https://www.google.com/maps/dir/?api=1&origin=40.4168,-3.7038&destination=40.42,-3.69&travelmode=transit", "P-16", "키 불필요"),
    ("구글 Maps URLs 문서", "https://developers.google.com/maps/documentation/urls/get-started", "P-16", "경유지 제한"),
    ("구글 My Maps 도움말", "https://support.google.com/mymaps/answer/3024836", "P-16", "가져오기 제한"),
    # 현지 관심도 대리 지표, 추가 출처
    ("YouTube Data API", "https://www.googleapis.com/youtube/v3/search?part=snippet&q=Sevilla&type=video", "P-17", "키 없으면 403"),
    ("YouTube 개발자 정책", "https://developers.google.com/youtube/terms/developer-policies", "P-17", "저장 조항"),
    ("datos.gob.es API", "https://datos.gob.es/apidata/catalog/dataset?q=turismo&_pageSize=2", "P-18", ""),
    ("마드리드 공공데이터", "https://datos.madrid.es/portal/site/egob", "P-18", ""),
    ("바르셀로나 공공데이터 API", "https://opendata-ajuntament.barcelona.cat/data/api/3/action/package_search?q=turisme&rows=2", "P-18", "CKAN"),
    ("Overture 릴리스 목록", "https://overturemaps-us-west-2.s3.amazonaws.com/release/", "P-18", "S3 목록"),
    ("Overture 문서", "https://docs.overturemaps.org/", "P-18", "라이선스"),
    ("Foursquare OS Places(HF)", "https://huggingface.co/datasets/foursquare/fsq-os-places", "P-18", ""),
    ("Foursquare OS Places(S3)", "https://fsq-os-places-us-east-1.s3.amazonaws.com/", "P-18", ""),
    # 도구
    ("PyPI osmium(pyosmium)", "https://pypi.org/pypi/osmium/json", "도구", "OSM 파일 처리"),
    ("PyPI pyvalhalla", "https://pypi.org/pypi/pyvalhalla/json", "도구", "로컬 경로 엔진"),
    ("PyPI duckdb", "https://pypi.org/pypi/duckdb/json", "도구", "Overture parquet 처리"),
]


def probe(url, method="GET"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.headers.get("Content-Length") or "", (r.headers.get("Content-Type") or "")[:30]
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Length") or "", (e.headers.get("Content-Type") or "")[:30]
    except Exception as e:  # 연결 끊김, 시간 초과 등
        return "연결 실패", type(e).__name__, str(e)[:50]


def human(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def main():
    out_json = None
    if "--json" in sys.argv:
        out_json = sys.argv[sys.argv.index("--json") + 1]
    rows = []
    print("| 소스 | 항목 | 응답 | 크기 | 비고 |")
    print("|---|---|---|---|---|")
    for name, url, item, note in SOURCES:
        method = "HEAD" if url.endswith((".bz2", ".pbf")) else "GET"
        status, length, ctype = probe(url, method)
        if status == "연결 실패":
            status_s, size_s = f"연결 실패({length})", ""
        else:
            status_s, size_s = str(status), human(length)
        rows.append({"source": name, "item": item, "url": url, "status": status_s, "size": size_s, "content_type": ctype, "note": note})
        print(f"| {name} | {item} | {status_s} | {size_s} | {note} |")
    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
