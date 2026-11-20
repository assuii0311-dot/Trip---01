#!/usr/bin/env python3
"""E1 보조: 수집 질의(poc/wikidata_collect.py)에서 빠진 지자체를 Wikidata에서 하나씩 받아 지자체 파일에 보탠다(T-049 세우타).

대상은 config.MUNICIPALITY_SUPPLEMENT의 QID다. 이미 파일에 있는 QID는 건너뛴다(여러 번 돌려도 같다).
실행: python -I pipeline/run.py e1.wikidata_supplement <루트>/wikidata
그 뒤 라벨(wikidata_labels.py, 남은 항목만 받는다)과 페이지뷰(e1.pageviews)를 다시 돌려야 이름·조회수가 채워진다.
"""
import json
import pathlib
import sys

import requests

from . import config as C

UA = "place-data-pipeline/0.1 (batch; 1 req/s)"
MUNI_CLASS = "Q2074737"


def record_from_entity(qid, ent):
    """Wikidata 엔티티 JSON → 수집 파일(Q2074737.jsonl)의 한 줄. 인구는 우선 순위(preferred) 값, 없으면 시점이 가장 늦은 값."""
    claims = ent.get("claims", {})

    def val(c):
        return c.get("mainsnak", {}).get("datavalue", {}).get("value")
    coord = next((val(c) for c in claims.get("P625", []) if val(c)), None)
    pops = [(c.get("rank") == "preferred", (c.get("qualifiers", {}).get("P585", [{}])[0].get("datavalue", {}).get("value", {}) or {}).get("time") or "", val(c)["amount"]) for c in claims.get("P1082", []) if val(c)]
    pop = max(pops)[2].lstrip("+") if pops else None
    p131 = next((val(c)["id"] for c in claims.get("P131", []) if val(c)), None)
    label = lambda l: (ent.get("labels", {}).get(l) or {}).get("value")
    return {"qid": qid, "cls": MUNI_CLASS, "coord": f"Point({coord['longitude']} {coord['latitude']})" if coord else None, "pop": pop, "sitelinks": str(len(ent.get("sitelinks", {}))), "p131": p131,
            "label_es": label("es"), "label_en": label("en"), "label_ko": label("ko"), "n_heritage": 0, "wv_en": "enwikivoyage" in ent.get("sitelinks", {})}


def main():
    wd = pathlib.Path(sys.argv[1]); path = wd / f"{MUNI_CLASS}.jsonl"
    have = {json.loads(line)["qid"] for line in open(path, encoding="utf-8")}
    todo = [q for q in C.MUNICIPALITY_SUPPLEMENT if q not in have]
    print(f"  보충 대상 {len(C.MUNICIPALITY_SUPPLEMENT)}건, 이미 있음 {len(C.MUNICIPALITY_SUPPLEMENT) - len(todo)}건", flush=True)
    sess = requests.Session(); sess.headers.update({"User-Agent": UA})
    with open(path, "a", encoding="utf-8") as f:
        for q in todo:
            r = sess.get(f"https://www.wikidata.org/wiki/Special:EntityData/{q}.json", timeout=60); r.raise_for_status()
            rec = record_from_entity(q, r.json()["entities"][q])
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"    {q} {rec['label_es']} 인구 {rec['pop']} 좌표 {rec['coord']}", flush=True)


if __name__ == "__main__":
    main()
