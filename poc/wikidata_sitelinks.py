#!/usr/bin/env python3
"""2단계 PoC C 단계: 매칭 대상 QID의 언어별 위키 문서 존재(en, es, ko 위키백과, 영문 Wikivoyage), 라벨, 설명을 50건 묶음으로 조회한다.

대상: Wikidata 지자체 전체, 영문 Wikivoyage 목록의 QID, OSM wikidata 태그 중 Wikidata 수집 집합과 겹치는 QID.
결과는 즉시 파일에 덧붙여 중단돼도 이어서 실행할 수 있다.

실행: python -I poc/wikidata_sitelinks.py <데이터 디렉터리 루트>
"""
import functools
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from wikidata_collect import Client, val  # noqa: E402

print = functools.partial(print, flush=True)
BATCH = 100


def q_batch(qids):
    vals = " ".join(f"wd:{q}" for q in qids)
    return f"""SELECT ?x ?les ?len ?lko ?des ?den ?dko ?enwiki ?eswiki ?kowiki ?wv WHERE {{
  VALUES ?x {{ {vals} }}
  OPTIONAL {{ ?x rdfs:label ?les FILTER(LANG(?les)="es") }}
  OPTIONAL {{ ?x rdfs:label ?len FILTER(LANG(?len)="en") }}
  OPTIONAL {{ ?x rdfs:label ?lko FILTER(LANG(?lko)="ko") }}
  OPTIONAL {{ ?x schema:description ?des FILTER(LANG(?des)="es") }}
  OPTIONAL {{ ?x schema:description ?den FILTER(LANG(?den)="en") }}
  OPTIONAL {{ ?x schema:description ?dko FILTER(LANG(?dko)="ko") }}
  OPTIONAL {{ ?enwiki schema:about ?x ; schema:isPartOf <https://en.wikipedia.org/> . }}
  OPTIONAL {{ ?eswiki schema:about ?x ; schema:isPartOf <https://es.wikipedia.org/> . }}
  OPTIONAL {{ ?kowiki schema:about ?x ; schema:isPartOf <https://ko.wikipedia.org/> . }}
  OPTIONAL {{ ?wv schema:about ?x ; schema:isPartOf <https://en.wikivoyage.org/> . }}
}}"""


def title_of(url):
    if not url:
        return None
    from urllib.parse import unquote
    return unquote(url.rsplit("/wiki/", 1)[-1]).replace("_", " ")


def main():
    root = pathlib.Path(sys.argv[1])
    wd_dir, out = root / "wikidata", root / "wikidata" / "sitelinks.jsonl"
    wd = {}
    for f in wd_dir.glob("*.jsonl"):
        if f.name in ("sitelinks.jsonl",):
            continue
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            wd.setdefault(r["qid"], r)
    muni = {q for q, r in wd.items() if r.get("cls") == "Q2074737"}
    wv = {json.loads(l).get("wikidata") for l in open(root / "wikivoyage_en" / "out" / "listings.jsonl", encoding="utf-8")}
    wv = {q for q in wv if q and q.startswith("Q")}
    osm = set()
    for line in open(root / "osm" / "out" / "pois.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("wikidata"):
            for q in r["wikidata"].split(";"):
                q = q.strip()
                if q in wd:
                    osm.add(q)
    targets = sorted(muni | wv | osm)
    done = set()
    if out.exists():
        for line in open(out, encoding="utf-8"):
            done.add(json.loads(line)["qid"])
    todo = [q for q in targets if q not in done]
    print(f"  대상 QID {len(targets)}건 (지자체 {len(muni)}, Wikivoyage {len(wv)}, OSM 교집합 {len(osm)}), 완료 {len(done)}, 남은 {len(todo)}, 묶음 {-(-len(todo)//BATCH)}회")
    c = Client()
    t0 = time.time()
    with open(out, "a", encoding="utf-8") as f:
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            try:
                rows = c.query(q_batch(chunk), retries=3)
            except Exception as e:
                print(f"    묶음 {i} 실패 {type(e).__name__}", file=sys.stderr)
                continue
            got = {}
            for b in rows:
                q = val(b, "x").rsplit("/", 1)[-1]
                got[q] = {"qid": q, "label_es": val(b, "les"), "label_en": val(b, "len"), "label_ko": val(b, "lko"),
                          "desc_es": val(b, "des"), "desc_en": val(b, "den"), "desc_ko": val(b, "dko"),
                          "enwiki": title_of(val(b, "enwiki")), "eswiki": title_of(val(b, "eswiki")), "kowiki": title_of(val(b, "kowiki")),
                          "wv_en": title_of(val(b, "wv"))}
            for q in chunk:
                f.write(json.dumps(got.get(q, {"qid": q}), ensure_ascii=False) + "\n")
            f.flush()
            if (i // BATCH) % 50 == 0:
                print(f"    {i+len(chunk)}/{len(todo)} ({round(time.time()-t0)}초, 호출 {c.calls}, 429 {c.r429})")
    print(f"  완료 ({round(time.time()-t0)}초, 호출 {c.calls}, 429 {c.r429})")


if __name__ == "__main__":
    main()
