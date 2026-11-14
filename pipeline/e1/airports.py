#!/usr/bin/env python3
"""E1 보조: 공항 목록(E1 4절 13항, D-029). Wikidata에서 IATA 코드가 있는 스페인 공항을 받아 OSM 공항·도시와 잇는다.

- 수집: `python -I pipeline/run.py e1.airports <출력 JSONL>`. SPARQL 한 번(식별 UA). 결과는 저장소에 넣지 않는다(D-016).
- 빌드: `build.py --airports <JSONL>`가 읽어 `build_airports`로 data/airports.json.gz를 만든다.
- 순수 함수(`parse_rows`, `build_airports`)는 네트워크를 모르며 pipeline/tests/test_e1.py에 고정 입력이 있다.
"""
import json
import sys

from .match import hav

UA = "Trip01-E1/0.1 (https://github.com/assuii0311-dot/Trip---01)"
SPARQL = "https://query.wikidata.org/sparql"
# P238 IATA, P239 ICAO, P31 분류, P931 소속 도시, P625 좌표, P3872 연 이용객(P585 시점)
QUERY = """SELECT ?a ?iata ?icao ?len ?les ?lko ?cls ?city ?cityEn ?cityKo ?cityIsland ?coord ?pax ?paxT WHERE {
  ?a wdt:P238 ?iata ; wdt:P17 wd:Q29 .
  OPTIONAL { ?a wdt:P239 ?icao }
  OPTIONAL { ?a rdfs:label ?len FILTER(LANG(?len)="en") }
  OPTIONAL { ?a rdfs:label ?les FILTER(LANG(?les)="es") }
  OPTIONAL { ?a rdfs:label ?lko FILTER(LANG(?lko)="ko") }
  OPTIONAL { ?a wdt:P31 ?cls }
  OPTIONAL { ?a wdt:P931 ?city .
    OPTIONAL { ?city rdfs:label ?cityEn FILTER(LANG(?cityEn)="en") }
    OPTIONAL { ?city rdfs:label ?cityKo FILTER(LANG(?cityKo)="ko") }
    BIND(EXISTS { ?city wdt:P31/wdt:P279* wd:Q23442 } AS ?cityIsland) }
  OPTIONAL { ?a wdt:P625 ?coord }
  OPTIONAL { ?a p:P3872 ?s . ?s ps:P3872 ?pax . OPTIONAL { ?s pq:P585 ?paxT } }
}"""
# 남기는 분류: 공항, 국제공항, 상업 비행장, 헬리포트. 공군기지(Q695850)와 철도역(Q55488 등)의 IATA 코드는 제외된다.
AIRPORT_CLASSES = ("Q1248784", "Q644371", "Q94993988", "Q502074")
PLANE_CLASSES = ("Q1248784", "Q644371", "Q94993988")
CITY_MIN_POP = 20000   # 소속 도시 추정 때 후보 도시의 최소 인구
CITY_NEAR_M = 20000    # 이 거리 안에 인구 2만 이상 도시가 있으면 그 도시를 소속 도시로 본다(추정값)


def qid(uri):
    return uri.rsplit("/", 1)[-1] if uri else None


def parse_point(s):
    """'Point(lon lat)' → (lat, lon). 소수 6자리."""
    if not s or not s.startswith("Point("):
        return None
    lon, lat = s[6:-1].split()
    return (round(float(lat), 6), round(float(lon), 6))


def cap(s):
    """Wikidata 스페인어 라벨은 소문자로 시작하는 경우가 많아 첫 글자만 대문자로 한다."""
    return (s[0].upper() + s[1:]) if s else s


def parse_rows(bindings):
    """SPARQL 바인딩(행마다 분류·이용객이 곱해져 나온다)을 QID 하나당 레코드 하나로 모은다."""
    g = lambda b, k: b.get(k, {}).get("value")
    by = {}
    for b in bindings:
        q = qid(g(b, "a"))
        it = by.setdefault(q, {"qid": q, "iata": g(b, "iata"), "icao": None, "labels": {"en": None, "es": None, "ko": None}, "classes": set(),
                                "city": {"qid": None, "en": None, "ko": None, "island": False}, "coord": None, "pax": set()})
        it["icao"] = it["icao"] or g(b, "icao")
        for l in ("en", "es", "ko"):
            it["labels"][l] = it["labels"][l] or g(b, "l" + l)
        if g(b, "cls"):
            it["classes"].add(qid(g(b, "cls")))
        if g(b, "city") and not it["city"]["qid"]:
            it["city"] = {"qid": qid(g(b, "city")), "en": g(b, "cityEn"), "ko": g(b, "cityKo"), "island": g(b, "cityIsland") == "true"}
        if g(b, "coord") and not it["coord"]:
            it["coord"] = parse_point(g(b, "coord"))
        if g(b, "pax"):
            it["pax"].add(((g(b, "paxT") or "")[:4], int(float(g(b, "pax")))))
    out = []
    for q in sorted(by):
        it = by[q]
        it["classes"] = sorted(it["classes"])
        pax = sorted(it["pax"])  # (연도, 값) 오름차순 → 마지막이 가장 최근 연도
        it["pax"] = {"value": pax[-1][1], "year": int(pax[-1][0]) if pax[-1][0] else None} if pax else None
        out.append(it)
    return out


def load_rows(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def build_airports(wd_airports, osm_airports, cities):
    """공항 레코드를 만든다(순수 함수).

    wd_airports: parse_rows 결과. osm_airports: sources.load_osm의 공항 레코드(id, lat, lon, name, name:en, wikidata).
    cities: build의 도시 레코드(id, n{en, ko}, lat, lon, pop).
    규칙(E1 4절 13항): 공항 분류만 남기고, 같은 IATA는 공항 분류·이용객·QID 순으로 하나. OSM 공항은 wikidata 태그가 같은 것만 잇고
    그때 좌표와 이름(name, name:en)은 OSM 우선. 소속 도시: (1) P931이 cities에 있으면 그 도시, (2) P931이 섬이면 섬 이름,
    (3) 20km 안에 인구 2만 이상 도시가 있으면 그중 인구가 가장 많은 도시(비고 공항이 교외 소도시에 있어도 중심 도시가 나오게), (4) P931 라벨,
    (5) 최근접 인구 2만 이상 도시. (2)~(5)는 추정(guess) 표시.
    """
    cities_by_id = {c["id"]: c for c in cities}
    big = [c for c in cities if (c.get("pop") or 0) >= CITY_MIN_POP and c.get("lat") is not None]
    osm_by_wd = {o["wikidata"]: o for o in osm_airports if o.get("wikidata")}
    cands = [a for a in wd_airports if a.get("iata") and a.get("coord") and set(a.get("classes") or ()) & set(AIRPORT_CLASSES)]
    rank = lambda a: (0 if set(a["classes"]) & set(PLANE_CLASSES) else 1, -((a.get("pax") or {}).get("value") or 0), a["qid"])
    best = {}
    for a in sorted(cands, key=rank):
        best.setdefault(a["iata"], a)
    out = []
    for iata, a in best.items():
        lat, lon = a["coord"]
        osm = osm_by_wd.get(a["qid"])
        if osm:
            lat, lon = osm["lat"], osm["lon"]
        cq, cl = a["city"]["qid"], a["city"]
        nearest = min(big, key=lambda c: (hav(lat, lon, c["lat"], c["lon"]), c["id"])) if big else None
        near_big = sorted([c for c in big if hav(lat, lon, c["lat"], c["lon"]) <= CITY_NEAR_M], key=lambda c: (-(c.get("pop") or 0), c["id"]))
        if cq in cities_by_id:
            c = cities_by_id[cq]
            city = {"id": cq, "en": c["n"].get("en"), "ko": c["n"].get("ko"), "guess": False}
        elif cl.get("island") and cl.get("en"):
            city = {"id": nearest["id"] if nearest else None, "en": cl["en"], "ko": cl.get("ko"), "guess": True}
        elif near_big:
            city = {"id": near_big[0]["id"], "en": near_big[0]["n"].get("en"), "ko": near_big[0]["n"].get("ko"), "guess": True}
        elif cl.get("en"):
            city = {"id": nearest["id"] if nearest else None, "en": cl["en"], "ko": cl.get("ko"), "guess": True}
        else:
            city = {"id": nearest["id"] if nearest else None, "en": nearest["n"].get("en") if nearest else None, "ko": nearest["n"].get("ko") if nearest else None, "guess": True}
        en = (osm or {}).get("name:en") or a["labels"]["en"]
        local = (osm or {}).get("name") or cap(a["labels"]["es"]) or en
        out.append({"id": a["qid"], "iata": iata, "icao": a.get("icao"),
                    "n": {"en": en, "local": local, "es": cap(a["labels"]["es"]), "ko": a["labels"]["ko"]},
                    "city": city, "lat": lat, "lon": lon,
                    "pax": (a.get("pax") or {}).get("value"), "pax_year": (a.get("pax") or {}).get("year"),
                    "osm": (osm or {}).get("id"), "heliport": not (set(a["classes"]) & set(PLANE_CLASSES))})
    out.sort(key=lambda x: (-(x["pax"] or 0), x["iata"]))
    return out


def fetch():
    import requests
    r = requests.get(SPARQL, params={"query": QUERY, "format": "json"}, headers={"User-Agent": UA}, timeout=180)
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def main():
    out = sys.argv[1]
    rows = parse_rows(fetch())
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"공항 {len(rows)}건 → {out}")


if __name__ == "__main__":
    main()
