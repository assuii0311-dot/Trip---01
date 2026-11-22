#!/usr/bin/env python3
"""E1 보조: Wikidata의 공통 라벨(mul)을 받는다(E1 4절 1항, D-066).

Wikidata는 언어마다 같은 라벨을 공통 라벨 하나로 합치고 있다. 합친 항목에는 스페인어·영어 라벨이 따로 없어서
수집 질의(es·en·ko 라벨만 읽는다)로는 이름이 빈다(2026-11-22 확인: 알메리아 Q10400, 엘체 Q10509).
- 대상: 클래스·유산 지정·사이트링크·라벨 파일을 합친 항목 가운데 스페인어나 영어 라벨이 없는 것.
- 호출: SPARQL VALUES 200개 묶음, 식별 UA, 요청 사이 1초, 429와 5xx는 쉬었다가 다시. 결과는 저장소에 넣지 않는다(D-016).
- 출력 JSONL: {qid, label_mul}. 공통 라벨이 없는 항목은 label_mul을 null로 적어 다시 묻지 않는다(이어 받기).
  sources.load_wikidata(mul_path=...)가 읽어 스페인어·영어 라벨의 빈칸을 채운다.
실행: python -I pipeline/run.py e1.wikidata_mul <wikidata 디렉터리> <라벨 JSONL> <출력 JSONL>
순수 함수(targets, parse_rows)는 네트워크를 모른다. 테스트는 pipeline/tests/test_e1.py.
"""
import json
import os
import sys
import time

from . import sources

UA = "place-data-pipeline/0.1 (batch; 1 req/s)"
SPARQL = "https://query.wikidata.org/sparql"
BATCH = 200
QUERY = 'SELECT ?x ?l WHERE { VALUES ?x { %s } ?x rdfs:label ?l . FILTER(LANG(?l) = "mul") }'


def targets(items):
    """스페인어나 영어 라벨이 없는 항목의 QID(정렬)"""
    return sorted(q for q, it in items.items() if not it["labels"].get("es") or not it["labels"].get("en"))


def parse_rows(bindings):
    """SPARQL 응답 → {qid: 공통 라벨}"""
    out = {}
    for b in bindings:
        q = b["x"]["value"].rsplit("/", 1)[-1]
        out.setdefault(q, b["l"]["value"])
    return out


def query(session, qids):
    import requests
    last = None
    for attempt in range(8):
        try:
            r = session.get(SPARQL, params={"query": QUERY % " ".join("wd:" + q for q in qids)}, timeout=90)
        except requests.RequestException as e:  # 연결이 끊기면 쉬었다가 다시 한다
            last = type(e).__name__; time.sleep(20); continue
        if r.status_code == 200:
            return parse_rows(r.json()["results"]["bindings"])
        last = r.status_code
        time.sleep(min(int(r.headers.get("Retry-After") or 15), 120))
    raise RuntimeError(f"재시도 초과({last})")


def main():
    import requests
    wd_dir, labels, out = sys.argv[1], sys.argv[2], sys.argv[3]
    want = targets(sources.load_wikidata(wd_dir, labels))
    done = {json.loads(l)["qid"] for l in open(out, encoding="utf-8")} if os.path.exists(out) else set()
    todo = [q for q in want if q not in done]
    print(f"  대상 {len(want):,}건, 완료 {len(done):,}건, 남은 {len(todo):,}건", flush=True)
    s = requests.Session(); s.headers.update({"User-Agent": UA, "Accept": "application/sparql-results+json"})
    t0, hit = time.time(), 0
    with open(out, "a", encoding="utf-8") as f:
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            got = query(s, chunk)
            for q in chunk:
                f.write(json.dumps({"qid": q, "label_mul": got.get(q)}, ensure_ascii=False) + "\n")
            f.flush(); hit += len(got)
            if (i // BATCH) % 25 == 0:
                print(f"    {i + len(chunk):,}/{len(todo):,} (공통 라벨 {hit:,}건, {time.time() - t0:.0f}초)", flush=True)
            time.sleep(1.0)
    print(f"  끝: 이번에 받은 공통 라벨 {hit:,}건 → {out}", flush=True)


if __name__ == "__main__":
    main()
