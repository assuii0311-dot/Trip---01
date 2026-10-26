#!/usr/bin/env python3
"""2단계 PoC B 단계: wikidata_collect.py 결과(JSONL)를 합쳐 중복을 제거하고 필드 커버리지를 센다.

실행: python -I poc/wikidata_coverage.py <데이터 디렉터리> <출력 JSON>
"""
import collections
import json
import pathlib
import sys

FIELDS = ["coord", "label_es", "label_en", "label_ko", "pop", "p131"]


def main():
    d, out = pathlib.Path(sys.argv[1]), sys.argv[2]
    items = {}
    per_class = collections.defaultdict(dict)
    for f in sorted(d.glob("*.jsonl")):
        cls = f.stem
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            q = r["qid"]
            per_class[cls][q] = r
            cur = items.get(q)
            if cur is None:
                r["classes"] = [cls]
                items[q] = r
            else:
                if cls not in cur["classes"]:
                    cur["classes"].append(cls)
                for k in FIELDS + ["sitelinks"]:
                    if not cur.get(k) and r.get(k):
                        cur[k] = r[k]
                cur["wv_en"] = cur.get("wv_en") or r.get("wv_en")
                cur["n_heritage"] = max(cur.get("n_heritage", 0), r.get("n_heritage", 0))

    def cov(rows):
        n = len(rows)
        if n == 0:
            return {}
        c = {k: round(100 * sum(1 for r in rows if r.get(k)) / n, 1) for k in FIELDS}
        c["sitelinks_ge1"] = round(100 * sum(1 for r in rows if int(r.get("sitelinks") or 0) >= 1) / n, 1)
        c["sitelinks_ge5"] = round(100 * sum(1 for r in rows if int(r.get("sitelinks") or 0) >= 5) / n, 1)
        c["wv_en"] = round(100 * sum(1 for r in rows if r.get("wv_en")) / n, 1)
        c["heritage"] = round(100 * sum(1 for r in rows if r.get("n_heritage", 0) > 0) / n, 1)
        return c

    all_rows = list(items.values())
    summary = {
        "unique_items": len(all_rows),
        "coverage_pct_all": cov(all_rows),
        "by_class": {cls: {"unique": len(rows), "coverage_pct": cov(list(rows.values()))} for cls, rows in per_class.items()},
    }
    # 지자체의 인구 분포 (층화 기준용)
    muni = [r for r in per_class.get("Q2074737", {}).values() if r.get("pop")]
    pops = sorted(int(float(r["pop"])) for r in muni)
    if pops:
        def pct(p):
            return pops[min(len(pops) - 1, int(len(pops) * p))]
        summary["municipality_population"] = {"with_pop": len(pops), "p50": pct(.5), "p75": pct(.75), "p90": pct(.9), "p95": pct(.95), "p99": pct(.99),
                                              "ge_100k": sum(1 for p in pops if p >= 100000), "ge_20k": sum(1 for p in pops if p >= 20000),
                                              "lt_5k": sum(1 for p in pops if p < 5000)}
    json.dump(summary, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  고유 항목 {len(all_rows)}건")
    print(f"  전체 커버리지: {summary['coverage_pct_all']}")
    for cls, v in summary["by_class"].items():
        c = v["coverage_pct"]
        print(f"  {cls:9} {v['unique']:6}건 좌표 {c.get('coord')}% es {c.get('label_es')}% en {c.get('label_en')}% ko {c.get('label_ko')}% wv {c.get('wv_en')}% 유산 {c.get('heritage')}%")
    if "municipality_population" in summary:
        print(f"  지자체 인구: {summary['municipality_population']}")


if __name__ == "__main__":
    main()
