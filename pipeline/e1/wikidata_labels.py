#!/usr/bin/env python3
"""E1 보조: 라벨·설명·위키 문서 제목이 없는 Wikidata 항목을 SPARQL VALUES 묶음으로 조회한다 (E1 2절 "사이트링크와 라벨").

- 대상: 문화유산 지정(P1435) 전용 항목과 클래스 수집 항목 중 sitelinks.jsonl에 없는 것.
- 방식: wbgetentities API는 이 환경에서 429가 잦아(2026-10-25 측정) SPARQL(초당 1회, 100개 묶음)로 바꿨다. 중단 후 재개 가능.
- 출력 JSONL: {qid, label_es, label_en, label_ko, label_ca, label_eu, label_gl, desc_es, desc_en, desc_ko, sitelinks(None: SPARQL 수집값 사용), enwiki, eswiki, kowiki}
실행: python -I pipeline/e1/wikidata_labels.py <wikidata 디렉터리> <출력 JSONL>
"""
import glob
import json
import os
import sys
import time

import requests

UA = "Trip01-E1/0.1 (https://github.com/assuii0311-dot/Trip---01)"
SPARQL = "https://query.wikidata.org/sparql"
BATCH = 100
LANGS = ["es", "en", "ko", "ca", "eu", "gl"]
Q = """SELECT ?item ?les ?len ?lko ?lca ?leu ?lgl ?des ?den ?dko ?enwiki ?eswiki ?kowiki WHERE {
  VALUES ?item { %s }
  OPTIONAL { ?item rdfs:label ?les FILTER(LANG(?les)="es") }
  OPTIONAL { ?item rdfs:label ?len FILTER(LANG(?len)="en") }
  OPTIONAL { ?item rdfs:label ?lko FILTER(LANG(?lko)="ko") }
  OPTIONAL { ?item rdfs:label ?lca FILTER(LANG(?lca)="ca") }
  OPTIONAL { ?item rdfs:label ?leu FILTER(LANG(?leu)="eu") }
  OPTIONAL { ?item rdfs:label ?lgl FILTER(LANG(?lgl)="gl") }
  OPTIONAL { ?item schema:description ?des FILTER(LANG(?des)="es") }
  OPTIONAL { ?item schema:description ?den FILTER(LANG(?den)="en") }
  OPTIONAL { ?item schema:description ?dko FILTER(LANG(?dko)="ko") }
  OPTIONAL { ?enwiki schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?eswiki schema:about ?item ; schema:isPartOf <https://es.wikipedia.org/> }
  OPTIONAL { ?kowiki schema:about ?item ; schema:isPartOf <https://ko.wikipedia.org/> }
}"""
import urllib.parse


def targets(wd):
    have = set()
    for line in open(f"{wd}/sitelinks.jsonl", encoding="utf-8"):
        have.add(json.loads(line)["qid"])
    want = {}
    for f in glob.glob(f"{wd}/Q*.jsonl") + [f"{wd}/P1435.jsonl"]:
        for line in open(f, encoding="utf-8"):
            r = json.loads(line); q = r["qid"]
            if q in have:
                continue
            if f.endswith("P1435.jsonl") or int(r.get("sitelinks") or 0) >= 1:
                want[q] = True
    return sorted(want)


def title_of(url):
    if not url:
        return None
    return urllib.parse.unquote(url.rsplit("/wiki/", 1)[-1]).replace("_", " ")


def main():
    wd, out = sys.argv[1], sys.argv[2]
    done = set()
    if os.path.exists(out):
        for line in open(out, encoding="utf-8"):
            done.add(json.loads(line)["qid"])
    todo = [q for q in targets(wd) if q not in done]
    print(f"  대상 {len(todo) + len(done)}건, 완료 {len(done)}건, 남은 {len(todo)}건", flush=True)
    sess = requests.Session(); sess.headers.update({"User-Agent": UA, "Accept": "application/sparql-results+json"})
    t0 = time.time(); n = 0
    with open(out, "a", encoding="utf-8") as f:
        for i in range(0, len(todo), BATCH):
            ids = todo[i:i + BATCH]
            rows = None
            for attempt in range(5):
                try:
                    r = sess.get(SPARQL, params={"query": Q % " ".join("wd:" + q for q in ids)}, timeout=90)
                    if r.status_code == 429:
                        time.sleep(int(r.headers.get("Retry-After", "15"))); continue
                    r.raise_for_status(); rows = r.json()["results"]["bindings"]; break
                except Exception as e:
                    print(f"  재시도 {attempt + 1}: {type(e).__name__} {str(e)[:60]}", flush=True); time.sleep(5 * (attempt + 1))
            if rows is None:
                print("  연속 실패, 중단", flush=True); return
            recs = {}
            for b in rows:
                q = b["item"]["value"].rsplit("/", 1)[-1]
                rec = recs.setdefault(q, {"qid": q, **{f"label_{l}": None for l in LANGS}, "desc_es": None, "desc_en": None, "desc_ko": None, "sitelinks": None, "enwiki": None, "eswiki": None, "kowiki": None, "missing": False})
                for l in LANGS:
                    v = b.get(f"l{l}");  rec[f"label_{l}"] = rec[f"label_{l}"] or (v or {}).get("value")
                for l in ("es", "en", "ko"):
                    v = b.get(f"d{l}"); rec[f"desc_{l}"] = rec[f"desc_{l}"] or (v or {}).get("value")
                for w in ("enwiki", "eswiki", "kowiki"):
                    v = b.get(w); rec[w] = rec[w] or title_of((v or {}).get("value"))
            for q in ids:
                rec = recs.get(q) or {"qid": q, **{f"label_{l}": None for l in LANGS}, "desc_es": None, "desc_en": None, "desc_ko": None, "sitelinks": None, "enwiki": None, "eswiki": None, "kowiki": None, "missing": True}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush(); n += len(ids)
            if (i // BATCH) % 50 == 0:
                print(f"  {n}/{len(todo)} ({time.time() - t0:.0f}초)", flush=True)
            time.sleep(1.0)
    print(f"  완료 {n}건, {time.time() - t0:.0f}초", flush=True)


if __name__ == "__main__":
    main()
