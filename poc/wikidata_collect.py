#!/usr/bin/env python3
"""2단계 PoC B 단계: Wikidata에서 스페인의 지자체와 관광 관련 장소를 분할 조회한다.

속도 제한 규칙: 동시 1개, 요청 간 1초 이상, 429는 Retry-After만큼 대기, 쿼리당 60초 제한.
실행:
  python -I poc/wikidata_collect.py counts  <데이터디렉터리>   # 클래스별 건수만
  python -I poc/wikidata_collect.py collect <데이터디렉터리>   # 항목 수집(JSONL)
"""
import json
import sys
import time
import pathlib
import requests

UA = "Trip01-PoC/0.1 (https://github.com/assuii0311-dot/Trip---01)"
ENDPOINT = "https://query.wikidata.org/sparql"
SPAIN = "wd:Q29"

# 조회 대상 클래스. (QID, 설명, 조회 방식) 방식: direct = P31 직접, sub = P31/P279* (지자체만)
CLASSES = [
    ("Q2074737", "스페인 지자체", "sub"),
    ("Q515", "도시", "direct"), ("Q3957", "소도시(town)", "direct"), ("Q532", "마을", "direct"),
    ("Q570116", "관광 명소", "direct"), ("Q33506", "박물관", "direct"), ("Q207694", "미술관", "direct"),
    ("Q16970", "교회 건물", "direct"), ("Q2977", "대성당", "direct"), ("Q44613", "수도원", "direct"),
    ("Q23413", "성", "direct"), ("Q16560", "궁전", "direct"), ("Q4989906", "기념물", "direct"),
    ("Q839954", "고고 유적", "direct"), ("Q15243209", "역사 지구", "direct"),
    ("Q22698", "공원", "direct"), ("Q1107656", "정원", "direct"), ("Q46169", "국립공원", "direct"),
    ("Q179049", "자연 보호구역", "direct"), ("Q40080", "해변", "direct"), ("Q8502", "산", "direct"),
    ("Q35509", "동굴", "direct"), ("Q23397", "호수", "direct"),
    ("Q174782", "광장", "direct"), ("Q330284", "시장", "direct"), ("Q24354", "극장", "direct"),
    ("Q483110", "경기장", "direct"), ("Q43501", "동물원", "direct"), ("Q39715", "등대", "direct"),
    ("Q12280", "다리", "direct"), ("Q1248784", "공항", "direct"), ("Q55488", "철도역", "direct"),
    ("Q11315", "쇼핑몰", "direct"), ("Q11707", "식당", "direct"),
    ("P1435", "문화유산 지정 보유(좌표 있음)", "heritage"),
]
HERITAGE = ("P1435", "문화유산 지정(P1435) 보유")

FIELDS = """
  ?x ?coord ?pop ?sl ?p131
  (SAMPLE(?les) AS ?label_es) (SAMPLE(?len) AS ?label_en) (SAMPLE(?lko) AS ?label_ko)
  (COUNT(DISTINCT ?her) AS ?n_heritage)
  (SAMPLE(?wv) AS ?wv_en)
"""
OPTIONALS = """
  OPTIONAL { ?x wdt:P625 ?coord . }
  OPTIONAL { ?x wdt:P1082 ?pop . }
  OPTIONAL { ?x wikibase:sitelinks ?sl . }
  OPTIONAL { ?x wdt:P131 ?p131 . }
  OPTIONAL { ?x rdfs:label ?les FILTER(LANG(?les)="es") }
  OPTIONAL { ?x rdfs:label ?len FILTER(LANG(?len)="en") }
  OPTIONAL { ?x rdfs:label ?lko FILTER(LANG(?lko)="ko") }
  OPTIONAL { ?x wdt:P1435 ?her . }
  OPTIONAL { ?wv schema:about ?x ; schema:isPartOf <https://en.wikivoyage.org/> . }
"""


class Client:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept": "application/sparql-results+json"})
        self.last = 0.0
        self.calls = 0
        self.r429 = 0

    def query(self, q, retries=6):
        for attempt in range(retries):
            wait = 1.0 - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.calls += 1
            try:
                r = self.s.get(ENDPOINT, params={"query": q}, timeout=70)
            except requests.RequestException as e:
                print(f"    요청 오류 {type(e).__name__}, 재시도 {attempt+1}", file=sys.stderr)
                time.sleep(5)
                continue
            if r.status_code == 429:
                self.r429 += 1
                ra = int(r.headers.get("Retry-After", "30"))
                print(f"    429, {ra}초 대기 (누적 429 {self.r429})", file=sys.stderr)
                time.sleep(min(ra, 120))
                continue
            if r.status_code in (500, 502, 503, 504):
                print(f"    {r.status_code} (시간 초과 가능), 재시도 {attempt+1}", file=sys.stderr)
                time.sleep(10)
                continue
            r.raise_for_status()
            return r.json()["results"]["bindings"]
        raise RuntimeError("재시도 초과")


def pattern(qid, mode):
    if mode == "sub":
        return f"?x wdt:P31/wdt:P279* wd:{qid} ."
    if mode == "heritage":
        return f"?x wdt:P1435 ?h ; wdt:P17 {SPAIN} ; wdt:P625 ?co0 ."
    return f"?x wdt:P31 wd:{qid} ; wdt:P17 {SPAIN} ."


def count_query(qid, mode):
    return f"SELECT (COUNT(DISTINCT ?x) AS ?c) WHERE {{ {pattern(qid, mode)} }}"


def collect_query(qid, mode, limit, offset):
    return f"""SELECT {FIELDS} WHERE {{ {pattern(qid, mode)} {OPTIONALS} }}
GROUP BY ?x ?coord ?pop ?sl ?p131 ORDER BY ?x LIMIT {limit} OFFSET {offset}"""


def val(b, k):
    return b[k]["value"] if k in b else None


def main():
    mode, outdir = sys.argv[1], pathlib.Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    c = Client()
    t0 = time.time()
    if mode == "counts":
        rows = []
        for qid, desc, m in CLASSES:
            try:
                n = int(c.query(count_query(qid, m))[0]["c"]["value"])
            except Exception as e:
                n = f"실패({type(e).__name__})"
            rows.append((qid, desc, m, n))
            print(f"  {qid:10} {desc:14} {n}")
        n = int(c.query(f"SELECT (COUNT(DISTINCT ?x) AS ?c) WHERE {{ ?x wdt:P17 {SPAIN} ; wdt:P625 ?co . }}")[0]["c"]["value"])
        print(f"  전체     스페인 소재 좌표 보유 항목 {n}")
        rows.append(("ALL", "스페인 소재 좌표 보유 항목", "all", n))
        json.dump({"counted_at": time.strftime("%Y-%m-%d %H:%M"), "rows": rows, "calls": c.calls, "r429": c.r429,
                   "seconds": round(time.time() - t0)}, open(outdir / "counts.json", "w"), ensure_ascii=False, indent=1)
    elif mode in ("collect", "collect-one"):
        summary = {}
        targets = [c_ for c_ in CLASSES if mode == "collect" or c_[0] == sys.argv[3]]
        for qid, desc, m in targets:
            out = outdir / f"{qid}.jsonl"
            n_total, offset, limit = 0, 0, 5000
            with open(out, "w", encoding="utf-8") as f:
                while True:
                    try:
                        rows = c.query(collect_query(qid, m, limit, offset))
                    except Exception as e:
                        print(f"  {qid} {desc}: 실패 {type(e).__name__} (offset {offset})", file=sys.stderr)
                        break
                    for b in rows:
                        rec = {"qid": val(b, "x").rsplit("/", 1)[-1], "cls": qid, "coord": val(b, "coord"),
                               "pop": val(b, "pop"), "sitelinks": val(b, "sl"), "p131": (val(b, "p131") or "").rsplit("/", 1)[-1] or None,
                               "label_es": val(b, "label_es"), "label_en": val(b, "label_en"), "label_ko": val(b, "label_ko"),
                               "n_heritage": int(val(b, "n_heritage") or 0),
                               "wv_en": bool(val(b, "wv_en"))}
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n_total += len(rows)
                    if len(rows) < limit:
                        break
                    offset += limit
            summary[qid] = {"desc": desc, "rows": n_total}
            print(f"  {qid:10} {desc:14} {n_total}건 ({round(time.time()-t0)}초, 호출 {c.calls}, 429 {c.r429})")
        json.dump({"collected_at": time.strftime("%Y-%m-%d %H:%M"), "classes": summary, "calls": c.calls, "r429": c.r429,
                   "seconds": round(time.time() - t0)}, open(outdir / "collect_summary.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
