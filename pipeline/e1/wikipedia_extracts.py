#!/usr/bin/env python3
"""E1 보조: 위키백과 문서의 머리 문단(발췌)을 받는다(E1 2절 "위키백과 발췌", E5의 설명 출처).

- 입력: 장소 ID 목록(JSON: [{id,...}] 또는 ["id",...])과 places_tier1.json.gz. 장소 레코드의 desc에서 위키백과 문서 제목(en·es·ko)을 읽는다.
- 호출: 각 언어판의 API(action=query, prop=extracts, exintro, explaintext). 20개 묶음, 초당 1회, 식별 UA, 429는 기다렸다 재시도. 결과는 저장소에 넣지 않는다(D-016).
- 출력 JSONL: {lang, title, extract}. 이미 받은 (lang, title)은 건너뛰어 이어 받을 수 있다.
실행: python -I pipeline/run.py e1.wikipedia_extracts <ID 목록 JSON> <places_tier1.json.gz> <출력 JSONL>
"""
import gzip
import json
import os
import sys
import time

UA = "Trip01-E1/0.1 (https://github.com/assuii0311-dot/Trip---01)"
BATCH = 20
LANGS = ("ko", "en", "es")
MAX_CHARS = 6000  # 머리 문단이 아주 긴 문서는 앞부분만 둔다


def titles_of(places, ids):
    """{lang: [title...]} 장소 레코드의 desc에 적힌 위키백과 문서 제목(중복 제거, 정렬)"""
    want = {l: set() for l in LANGS}
    idset = set(ids)
    for p in places:
        if p["id"] in idset:
            for d in p.get("desc") or []:
                if d.get("src") == "wikipedia" and d.get("lang") in want and d.get("title"):
                    want[d["lang"]].add(d["title"])
    return {l: sorted(v) for l, v in want.items()}


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


def fetch(lang, titles):
    import requests
    out = {}
    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        for attempt in range(5):  # 429는 Retry-After(없으면 5, 10, 20, 40초)만큼 기다렸다 다시 한다
            r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", headers={"User-Agent": UA}, timeout=60,
                             params={"action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1, "redirects": 1, "exlimit": BATCH, "titles": "|".join(chunk), "format": "json"})
            if r.status_code != 429:
                break
            time.sleep(min(int(r.headers.get("Retry-After") or 5 * 2 ** attempt), 120))
        r.raise_for_status()
        out.update(parse_response(r.json()))
        time.sleep(1)
    return out


def main():
    ids_raw = json.load(open(sys.argv[1], encoding="utf-8")); ids = [x["id"] if isinstance(x, dict) else x for x in ids_raw]
    places = json.load(gzip.open(sys.argv[2], "rt", encoding="utf-8")); out_path = sys.argv[3]
    have = set()
    if os.path.exists(out_path):
        for l in open(out_path, encoding="utf-8"):
            r = json.loads(l); have.add((r["lang"], r["title"]))
    want = titles_of(places, ids); n = 0
    with open(out_path, "a", encoding="utf-8") as f:
        for lang in LANGS:
            todo = [t for t in want[lang] if (lang, t) not in have]
            got = fetch(lang, todo) if todo else {}
            for t in todo:
                if got.get(t):
                    f.write(json.dumps({"lang": lang, "title": t, "extract": got[t]}, ensure_ascii=False) + "\n"); n += 1
            print(f"  {lang}: 요청 {len(todo)}건, 받음 {sum(1 for t in todo if got.get(t))}건", flush=True)
    print(f"발췌 {n}건 추가 → {out_path}")


if __name__ == "__main__":
    main()
