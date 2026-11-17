#!/usr/bin/env python3
"""E1 보조: 섬 단위 여행지(E1 4절 14항, D-030).

- 수집: `python -I pipeline/run.py e1.islands <출력 JSONL> <섬 폴리곤 JSONL...>`. osm_islands.py가 만든 섬 폴리곤 파일의 wikidata 태그를 모아
  Wikidata에서 라벨(en·es·ko)과 위키백과·영문 Wikivoyage 문서 제목을 받는다(SPARQL, 100개 묶음, 초당 1회, 식별 UA). 결과는 저장소에 넣지 않는다(D-016).
  출력 JSONL {qid, label_en, label_es, label_ko, enwiki, eswiki, kowiki, enwikivoyage}는 pageviews.py의 제목 파일로도 쓴다.
- 판정: `assign_members`가 지자체 중심 좌표를 섬 폴리곤에 넣어 소속 섬을 정한다(순수 함수, shapely).
- 여행지가 되는 섬: 소속 지자체가 1곳 이상이고 영문 Wikivoyage의 스페인 하위 문서가 있는 섬(`eligible`).
"""
import json
import sys
import time
import urllib.parse

UA = "place-data-pipeline/0.1 (batch; 1 req/s)"
SPARQL = "https://query.wikidata.org/sparql"
BATCH = 100
QUERY = """SELECT ?i ?len ?les ?lko ?enwiki ?eswiki ?kowiki ?envoy WHERE {
  VALUES ?i { %s }
  OPTIONAL { ?i rdfs:label ?len FILTER(LANG(?len)="en") }
  OPTIONAL { ?i rdfs:label ?les FILTER(LANG(?les)="es") }
  OPTIONAL { ?i rdfs:label ?lko FILTER(LANG(?lko)="ko") }
  OPTIONAL { ?enwiki schema:about ?i ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?eswiki schema:about ?i ; schema:isPartOf <https://es.wikipedia.org/> }
  OPTIONAL { ?kowiki schema:about ?i ; schema:isPartOf <https://ko.wikipedia.org/> }
  OPTIONAL { ?envoy schema:about ?i ; schema:isPartOf <https://en.wikivoyage.org/> }
}"""


def load_osm_islands(paths):
    """섬 폴리곤 파일 여러 개를 읽어 합친다. 같은 wikidata(없으면 같은 이름)의 섬은 osm_id가 앞선 하나만 남긴다."""
    rows = []
    for p in paths:
        rows += [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: r["osm_id"]):
        key = r.get("wikidata") or ("name:" + (r.get("name") or ""))
        if key in seen:
            continue
        seen.add(key); out.append(r)
    return out


def title_of(url):
    return urllib.parse.unquote(url.rsplit("/wiki/", 1)[-1]).replace("_", " ") if url else None


def parse_rows(bindings):
    g = lambda b, k: b.get(k, {}).get("value")
    by = {}
    for b in bindings:
        q = g(b, "i").rsplit("/", 1)[-1]
        it = by.setdefault(q, {"qid": q, "label_en": None, "label_es": None, "label_ko": None, "enwiki": None, "eswiki": None, "kowiki": None, "enwikivoyage": None})
        for src, dst in (("len", "label_en"), ("les", "label_es"), ("lko", "label_ko")):
            it[dst] = it[dst] or g(b, src)
        for src, dst in (("enwiki", "enwiki"), ("eswiki", "eswiki"), ("kowiki", "kowiki"), ("envoy", "enwikivoyage")):
            it[dst] = it[dst] or title_of(g(b, src))
    return [by[q] for q in sorted(by)]


def assign_members(osm_islands, cities):
    """지자체 중심 좌표가 들어 있는 섬을 찾는다. 겹치면 면적이 가장 작은 섬. 반환: {섬 인덱스: [지자체 레코드...]} (입력 순서 유지)"""
    from shapely import wkb
    from shapely.geometry import Point
    from shapely.strtree import STRtree
    geoms = [wkb.loads(bytes.fromhex(r["wkb"])) for r in osm_islands]
    tree = STRtree(geoms) if geoms else None
    out = {}
    for c in cities:
        if c.get("lat") is None or tree is None:
            continue
        pt = Point(c["lon"], c["lat"])
        hits = [int(i) for i in tree.query(pt) if geoms[int(i)].contains(pt)]
        if hits:
            out.setdefault(min(hits, key=lambda i: (geoms[i].area, i)), []).append(c)
    return out


def eligible(osm_island, wd_row, guide_titles):
    """여행지가 되는 섬이면 영문 Wikivoyage 문서 제목을, 아니면 None을 돌려준다. Wikidata 사이트링크를 우선하고 없으면 이름으로 찾는다."""
    cands = [(wd_row or {}).get("enwikivoyage"), osm_island.get("name_en"), (wd_row or {}).get("label_en"), osm_island.get("name"), osm_island.get("name_es")]
    return next((t for t in cands if t and t in guide_titles), None)


def fetch(qids):
    import requests
    rows = []
    for i in range(0, len(qids), BATCH):
        q = QUERY % " ".join("wd:" + x for x in qids[i:i + BATCH])
        r = requests.get(SPARQL, params={"query": q, "format": "json"}, headers={"User-Agent": UA}, timeout=180)
        r.raise_for_status()
        rows += r.json()["results"]["bindings"]
        time.sleep(1)
    return parse_rows(rows)


def main():
    out, paths = sys.argv[1], sys.argv[2:]
    qids = sorted({r["wikidata"] for r in load_osm_islands(paths) if (r.get("wikidata") or "").startswith("Q")})
    rows = fetch(qids)
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"섬 {len(qids)}건 조회, {len(rows)}건 저장 → {out}")


if __name__ == "__main__":
    main()
