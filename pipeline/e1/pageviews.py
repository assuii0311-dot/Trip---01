"""여러 달의 월간 페이지뷰 덤프에서 대상 문서의 언어별 조회수를 뽑아 월평균을 낸다 (E1 2절, D-023: 최근 3개월).

입력: 덤프 bz2 여러 개, 제목 파일(sitelinks.jsonl, labels.jsonl: enwiki, eswiki, kowiki 제목)
출력: views.jsonl {qid, en, es, ko, months} (월평균, 정수)
실행: python -I -m pipeline.e1.pageviews <출력 JSONL> <제목 JSONL...> -- <덤프.bz2...>
"""
import bz2
import json
import sys
import time

CODES = {"en.wikipedia": "en", "es.wikipedia": "es", "ko.wikipedia": "ko"}


def load_titles(paths):
    want = {}  # (lang, title) → set(qid)
    for p in paths:
        for line in open(p, encoding="utf-8"):
            r = json.loads(line)
            for lang in ("en", "es", "ko"):
                t = r.get(f"{lang}wiki")
                if t:
                    want.setdefault((lang, t.replace(" ", "_")), set()).add(r["qid"])
    return want


def scan(dump, want, totals):
    t0 = time.time(); n = hit = 0
    with bz2.open(dump, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            n += 1
            sp = line.find(" ")
            code = line[:sp]
            lang = CODES.get(code)
            if not lang:
                continue
            parts = line.split(" ")
            if len(parts) < 5:
                continue
            key = (lang, parts[1])
            qids = want.get(key)
            if not qids:
                continue
            try:
                v = int(parts[4])
            except ValueError:
                continue
            for q in qids:
                totals.setdefault(q, {"en": 0, "es": 0, "ko": 0})[lang] += v
            hit += 1
            if hit % 2000 == 0:
                pass
    print(f"  {dump}: {n:,}줄, 적중 {hit:,}, {time.time() - t0:.0f}초", flush=True)


def main():
    args = sys.argv[1:]
    sep = args.index("--")
    out, titles, dumps = args[0], args[1:sep], args[sep + 1:]
    want = load_titles(titles)
    print(f"  대상 제목 {len(want):,}건, 덤프 {len(dumps)}개", flush=True)
    totals = {}
    for d in dumps:
        scan(d, want, totals)
    m = len(dumps)
    with open(out, "w", encoding="utf-8") as f:
        for q, v in sorted(totals.items()):
            f.write(json.dumps({"qid": q, "en": round(v["en"] / m), "es": round(v["es"] / m), "ko": round(v["ko"] / m), "months": m}) + "\n")
    print(f"  문서 {len(totals):,}건 저장 → {out}", flush=True)


if __name__ == "__main__":
    main()
