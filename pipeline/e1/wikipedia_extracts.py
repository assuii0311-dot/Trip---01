#!/usr/bin/env python3
"""E1 보조: 위키백과 문서의 머리 문단(발췌)을 받는다(E1 2절 "위키백과 발췌", E5의 설명 출처).

- 입력: 장소 ID 목록(JSON: [{id,...}] 또는 ["id",...])과 places_tier1.json.gz. 장소 레코드의 desc에서 위키백과 문서 제목(en·es·ko)을 읽는다.
- 호출: 각 언어판의 API(action=query, prop=extracts, exintro, explaintext). 20개 묶음, 식별 UA. 결과는 저장소에 넣지 않는다(D-016).
- 속도: 요청 사이 1초에서 시작한다. 429를 받으면 Retry-After만큼 쉬고 간격을 두 배(최대 10초)로 늘리며, 성공이 이어지면 조금씩 줄인다.
- 출력 JSONL: {lang, title, extract}. 묶음을 받을 때마다 적는다. 문서가 없거나 머리 문단이 빈 제목은 extract를 빈 문자열로 적어 다시 묻지 않는다.
  이미 적힌 (lang, title)은 건너뛰어 이어 받을 수 있다. 제목은 ID 목록의 순서대로 받는다(앞쪽 장소가 먼저 채워진다).
실행: python -I pipeline/run.py e1.wikipedia_extracts <ID 목록 JSON> <places_tier1.json.gz> <출력 JSONL> [--langs en es ko]
"""
import argparse
import gzip
import json
import os
import sys
import time

UA = "place-data-pipeline/0.1 (batch; 1 req/s)"
BATCH = 20
LANGS = ("ko", "en", "es")
MAX_CHARS = 6000  # 머리 문단이 아주 긴 문서는 앞부분만 둔다


def titles_of(places, ids):
    """{lang: [title...]} 장소 레코드의 desc에 적힌 위키백과 문서 제목(중복 제거, ID 목록의 순서)"""
    want = {l: {} for l in LANGS}
    by_id = {p["id"]: p for p in places}
    for i in ids:
        for d in (by_id.get(i) or {}).get("desc") or []:
            if d.get("src") == "wikipedia" and d.get("lang") in want and d.get("title"):
                want[d["lang"]].setdefault(d["title"], None)
    return {l: list(v) for l, v in want.items()}


def parse_response(data):
    """API 응답 → {요청한 제목: 발췌}. 정규화·넘겨주기로 바뀐 제목을 요청 제목으로 되돌린다."""
    q = data.get("query") or {}
    back = {}
    for m in (q.get("normalized") or []) + (q.get("redirects") or []):
        back[m["to"]] = back.get(m["from"], m["from"])
    out = {}
    for page in (q.get("pages") or {}).values():
        if page.get("extract"):
            t = page["title"]
            while t in back and back[t] != t:
                t = back[t]
            out[t] = page["extract"].strip()[:MAX_CHARS]
    return out


def next_delay(delay, limited):
    """요청 간격 조절: 제한(429)을 받으면 두 배(최대 10초), 아니면 10%씩 줄여 1초까지"""
    return min(delay * 2, 10.0) if limited else max(1.0, delay * 0.9)


def fetch(lang, titles, on_batch=None):
    """묶음마다 on_batch(묶음 제목들, {제목: 발췌})를 부른다. 전체 결과도 돌려준다."""
    import requests
    out, delay = {}, 1.0
    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        for attempt in range(40):
            r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", headers={"User-Agent": UA}, timeout=60,
                             params={"action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1, "redirects": 1, "exlimit": BATCH, "titles": "|".join(chunk), "format": "json"})
            if r.status_code != 429:
                break
            delay = next_delay(delay, True)
            time.sleep(min(int(r.headers.get("Retry-After") or 30), 300))
        r.raise_for_status()
        got = parse_response(r.json())
        out.update(got)
        if on_batch:
            on_batch(chunk, got)
        time.sleep(delay); delay = next_delay(delay, False)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids"); ap.add_argument("places"); ap.add_argument("out"); ap.add_argument("--langs", nargs="*", default=list(LANGS))
    a = ap.parse_args()
    ids_raw = json.load(open(a.ids, encoding="utf-8")); ids = [x["id"] if isinstance(x, dict) else x for x in ids_raw]
    places = json.load(gzip.open(a.places, "rt", encoding="utf-8"))
    have = set()
    if os.path.exists(a.out):
        for l in open(a.out, encoding="utf-8"):
            r = json.loads(l); have.add((r["lang"], r["title"]))
    want = titles_of(places, ids)
    with open(a.out, "a", encoding="utf-8", buffering=1 << 20) as f:
        for lang in a.langs:
            todo = [t for t in want.get(lang, []) if (lang, t) not in have]
            count = {"hit": 0, "done": 0}

            def save(chunk, got, lang=lang, count=count):
                for t in chunk:  # 한 줄씩 한 번에 적는다(여러 언어를 따로 돌려도 줄이 섞이지 않게)
                    f.write(json.dumps({"lang": lang, "title": t, "extract": got.get(t, "")}, ensure_ascii=False) + "\n"); f.flush()
                count["hit"] += sum(1 for t in chunk if got.get(t)); count["done"] += len(chunk)
                if count["done"] % 200 < BATCH:
                    print(f"  {lang}: {count['done']}/{len(todo)}", flush=True)
            if todo:
                fetch(lang, todo, save)
            print(f"  {lang}: 요청 {len(todo)}건, 받음 {count['hit']}건", flush=True)
    print(f"끝 → {a.out}")


if __name__ == "__main__":
    main()
