#!/usr/bin/env python3
"""2단계 PoC B 단계: 스페인의 문화유산 지정(P1435) 항목을 지정 종류별로 쪼개어 조회한다.

wikidata_collect.py의 한 번에 묶는 쿼리는 7만 건 규모에서 시간 초과가 나므로,
1) 지정 종류(?h)별 건수를 세고, 2) 종류별로 가벼운 쿼리(정렬·집계 없음)로 QID와 좌표를 받고,
3) 다른 클래스 파일에 없는 QID만 200개씩 묶어 라벨(es, en, ko)과 Wikivoyage 링크를 받는다.
큰 종류(1만 건 초과)는 자치주(P131 상위) 대신 위도 띠로 나눈다.

실행: python -I poc/wikidata_heritage.py <데이터 디렉터리> [--no-labels]
--no-labels: 3) 라벨 조회를 건너뛴다(큰 묶음 조회가 시간 초과를 반복할 때). 진행 상황은 즉시 출력된다.
"""
import functools
print = functools.partial(print, flush=True)  # 백그라운드 로그에 즉시 기록
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from wikidata_collect import Client, SPAIN, val  # noqa: E402

LAT_BANDS = [(27, 36.5), (36.5, 38.5), (38.5, 40.5), (40.5, 42), (42, 44)]


def q_designations():
    return f"SELECT ?h (COUNT(DISTINCT ?x) AS ?c) WHERE {{ ?x wdt:P1435 ?h ; wdt:P17 {SPAIN} ; wdt:P625 ?co . }} GROUP BY ?h ORDER BY DESC(?c)"


def q_items(h, band=None):
    f = ""
    if band:
        f = f'FILTER(geof:latitude(?co) >= {band[0]} && geof:latitude(?co) < {band[1]})'
    return f"SELECT DISTINCT ?x ?co ?sl WHERE {{ ?x wdt:P1435 wd:{h} ; wdt:P17 {SPAIN} ; wdt:P625 ?co . OPTIONAL {{ ?x wikibase:sitelinks ?sl . }} {f} }}"


def q_labels(qids):
    vals = " ".join(f"wd:{q}" for q in qids)
    return f"""SELECT ?x (SAMPLE(?les) AS ?label_es) (SAMPLE(?len) AS ?label_en) (SAMPLE(?lko) AS ?label_ko) (SAMPLE(?wv) AS ?wv_en) (SAMPLE(?p131) AS ?p131) WHERE {{
  VALUES ?x {{ {vals} }}
  OPTIONAL {{ ?x rdfs:label ?les FILTER(LANG(?les)="es") }}
  OPTIONAL {{ ?x rdfs:label ?len FILTER(LANG(?len)="en") }}
  OPTIONAL {{ ?x rdfs:label ?lko FILTER(LANG(?lko)="ko") }}
  OPTIONAL {{ ?x wdt:P131 ?p131 . }}
  OPTIONAL {{ ?wv schema:about ?x ; schema:isPartOf <https://en.wikivoyage.org/> . }}
}} GROUP BY ?x"""


def main():
    d = pathlib.Path(sys.argv[1])
    no_labels = "--no-labels" in sys.argv
    c = Client()
    t0 = time.time()
    known = set()
    for f in d.glob("Q*.jsonl"):
        for line in open(f, encoding="utf-8"):
            known.add(json.loads(line)["qid"])
    print(f"  다른 클래스에서 이미 수집된 QID {len(known)}건")
    des = [(val(b, "h").rsplit("/", 1)[-1], int(val(b, "c"))) for b in c.query(q_designations())]
    print(f"  지정 종류 {len(des)}개, 상위 5개: {des[:5]}")
    items = {}
    for h, n in des:
        bands = LAT_BANDS if n > 10000 else [None]
        got = 0
        for band in bands:
            try:
                rows = c.query(q_items(h, band), retries=3)
            except Exception as e:
                print(f"    {h} (밴드 {band}) 실패 {type(e).__name__}", file=sys.stderr)
                continue
            for b in rows:
                q = val(b, "x").rsplit("/", 1)[-1]
                r = items.setdefault(q, {"qid": q, "cls": "P1435", "coord": val(b, "co"), "sitelinks": val(b, "sl"), "designations": []})
                if h not in r["designations"]:
                    r["designations"].append(h)
            got += len(rows)
        print(f"  {h} 기대 {n} 수신 {got} ({round(time.time()-t0)}초, 호출 {c.calls}, 429 {c.r429})")
    need = [] if no_labels else [q for q in items if q not in known]
    print(f"  고유 항목 {len(items)}건, 라벨 조회 필요 {len(need)}건 (묶음 {-(-len(need)//200)}회)")
    for i in range(0, len(need), 200):
        chunk = need[i:i + 200]
        try:
            rows = c.query(q_labels(chunk), retries=2)
        except Exception as e:
            print(f"    라벨 묶음 {i} 실패 {type(e).__name__}", file=sys.stderr)
            continue
        for b in rows:
            q = val(b, "x").rsplit("/", 1)[-1]
            items[q].update({"label_es": val(b, "label_es"), "label_en": val(b, "label_en"), "label_ko": val(b, "label_ko"),
                             "wv_en": bool(val(b, "wv_en")), "p131": (val(b, "p131") or "").rsplit("/", 1)[-1] or None})
        if (i // 200) % 25 == 0:
            print(f"    라벨 {i+len(chunk)}/{len(need)} ({round(time.time()-t0)}초, 429 {c.r429})")
    with open(d / "P1435.jsonl", "w", encoding="utf-8") as f:
        for r in items.values():
            r.setdefault("n_heritage", len(r["designations"]))
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump({"collected_at": time.strftime("%Y-%m-%d %H:%M"), "designations": des, "unique": len(items), "labels_fetched": len(need),
               "calls": c.calls, "r429": c.r429, "seconds": round(time.time() - t0)}, open(d / "heritage_summary.json", "w"), ensure_ascii=False, indent=1)
    print(f"  완료: {len(items)}건 저장 ({round(time.time()-t0)}초, 호출 {c.calls}, 429 {c.r429})")


if __name__ == "__main__":
    main()
