#!/usr/bin/env python3
"""2단계 PoC C 단계: Wikimedia 월간 페이지뷰 덤프에서 대상 문서의 언어별 조회수를 뽑는다 (P-17 대리 지표).

입력: pageview_complete 월간 user 파일(bz2), 대상 제목 파일(sitelinks.jsonl의 enwiki, eswiki, kowiki 제목)
형식(공백 구분): 위키코드 문서제목 페이지ID 접근방식 월간합계 시간별
출력: 대상 문서별 en, es, ko 월간 조회수 JSONL과 요약
실행: python -I poc/pageviews_extract.py <덤프.bz2> <sitelinks.jsonl> <출력 JSONL>
"""
import bz2
import collections
import json
import sys
import time

WIKIS = {"en.wikipedia": "en", "es.wikipedia": "es", "ko.wikipedia": "ko"}


def main():
    dump, links, out = sys.argv[1], sys.argv[2], sys.argv[3]
    targets = {w: {} for w in WIKIS.values()}
    for line in open(links, encoding="utf-8"):
        r = json.loads(line)
        for w in WIKIS.values():
            t = r.get(f"{w}wiki")
            if t:
                targets[w][t.replace(" ", "_")] = r["qid"]
    print(f"  대상 제목: " + ", ".join(f"{w} {len(v)}" for w, v in targets.items()), flush=True)
    views = collections.defaultdict(lambda: {"en": 0, "es": 0, "ko": 0})
    n, hit, t0 = 0, 0, time.time()
    with bz2.open(dump, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            n += 1
            if n % 20_000_000 == 0:
                print(f"    {n//1_000_000}M줄, 적중 {hit} ({round(time.time()-t0)}초)", flush=True)
            sp = line.find(" ")
            wiki = line[:sp]
            lang = WIKIS.get(wiki)
            if not lang:
                continue
            parts = line.split(" ")
            if len(parts) < 5:
                continue
            q = targets[lang].get(parts[1])
            if q is None:
                continue
            try:
                views[q][lang] += int(parts[4])
                hit += 1
            except ValueError:
                pass
    with open(out, "w", encoding="utf-8") as fo:
        for q, v in views.items():
            fo.write(json.dumps({"qid": q, **v}) + "\n")
    print(f"  완료: {n}줄, 적중 {hit}, 문서 {len(views)}건 ({round(time.time()-t0)}초)", flush=True)


if __name__ == "__main__":
    main()
