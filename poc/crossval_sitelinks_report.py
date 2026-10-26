#!/usr/bin/env python3
"""2단계 PoC C 단계: 사이트링크 조회 결과로 언어별 문서·설명 커버리지(P-03, P-08, P-10)와 D 단계 층별 도시 수를 센다.

입력: 데이터 루트(wikidata/*.jsonl, wikidata/sitelinks.jsonl, wikivoyage_en/out/pages.jsonl, osm/out/pois.jsonl)
출력: 요약 JSON
실행: python -I poc/crossval_sitelinks_report.py <데이터 루트> <출력 JSON>
"""
import collections
import json
import pathlib
import sys


def pct(a, b):
    return round(100 * a / b, 1) if b else None


def main():
    root, out = pathlib.Path(sys.argv[1]), sys.argv[2]
    wd = {}
    for f in (root / "wikidata").glob("*.jsonl"):
        if f.name == "sitelinks.jsonl":
            continue
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            wd.setdefault(r["qid"], r)
            wd[r["qid"]].setdefault("classes", set()).add(r["cls"])
    links = {}
    for line in open(root / "wikidata" / "sitelinks.jsonl", encoding="utf-8"):
        r = json.loads(line)
        links[r["qid"]] = r
    muni = {q for q, r in wd.items() if "Q2074737" in r["classes"]}
    wv_list_q = {json.loads(l).get("wikidata") for l in open(root / "wikivoyage_en" / "out" / "listings.jsonl", encoding="utf-8")}
    wv_list_q = {q for q in wv_list_q if q and q in wd}
    osm_q = set()
    for line in open(root / "osm" / "out" / "pois.jsonl", encoding="utf-8"):
        o = json.loads(line)
        if o.get("wikidata"):
            for q in o["wikidata"].split(";"):
                if q.strip() in wd:
                    osm_q.add(q.strip())
    heritage_only = {q for q, r in wd.items() if r["classes"] == {"P1435"}}

    def cov(qs, name):
        rows = [links[q] for q in qs if q in links]
        n = len(rows)
        return {"set": name, "targets": len(qs), "looked_up": n,
                "enwiki": pct(sum(1 for r in rows if r.get("enwiki")), n), "eswiki": pct(sum(1 for r in rows if r.get("eswiki")), n),
                "kowiki": pct(sum(1 for r in rows if r.get("kowiki")), n), "wv_en": pct(sum(1 for r in rows if r.get("wv_en")), n),
                "label_es": pct(sum(1 for r in rows if r.get("label_es")), n), "label_en": pct(sum(1 for r in rows if r.get("label_en")), n),
                "label_ko": pct(sum(1 for r in rows if r.get("label_ko")), n),
                "desc_es": pct(sum(1 for r in rows if r.get("desc_es")), n), "desc_en": pct(sum(1 for r in rows if r.get("desc_en")), n),
                "desc_ko": pct(sum(1 for r in rows if r.get("desc_ko")), n)}

    sets = [cov(muni, "지자체"), cov(wv_list_q, "Wikivoyage 목록 QID"), cov(osm_q, "OSM∩Wikidata"), cov(osm_q & heritage_only, "OSM∩문화유산 전용")]
    # 인구 상위 지자체의 한국어 문서
    big = sorted((q for q in muni if wd[q].get("pop")), key=lambda q: -float(wd[q]["pop"]))
    tiers = {}
    for name, qs in (("인구 상위 50", big[:50]), ("상위 51~200", big[50:200]), ("상위 201~500", big[200:500])):
        tiers[name] = cov(set(qs), name)
    # Wikivoyage 도시 ↔ 지자체 매핑과 D 단계 층
    pages = {json.loads(l)["title"]: json.loads(l) for l in open(root / "wikivoyage_en" / "out" / "pages.jsonl", encoding="utf-8")}
    title_to_q = {}
    for q in muni:
        t = links.get(q, {}).get("wv_en")
        if t:
            title_to_q[t] = q
    wv_cities = {t: p for t, p in pages.items() if p["kind"] == "city"}
    mapped = {t: title_to_q[t] for t in wv_cities if t in title_to_q}
    strata = collections.Counter()
    strata_examples = collections.defaultdict(list)
    for q in muni:
        pop = float(wd[q]["pop"]) if wd[q].get("pop") else None
        t = links.get(q, {}).get("wv_en")
        n_list = sum(pages[t]["listings"].values()) if t and t in pages else 0
        if pop is not None and pop >= 100000:
            s = "대도시"
        elif t and t in wv_cities and n_list >= 5 and (pop is None or pop < 100000):
            s = "중소 관광 도시"
        elif (pop is not None and pop < 20000) and (not t or n_list < 5):
            s = "데이터 빈약 소도시"
        else:
            s = "기타(2만~10만, 가이드 미약)"
        strata[s] += 1
        if len(strata_examples[s]) < 5:
            strata_examples[s].append(wd[q].get("label_es") or q)
    summary = {"coverage_by_set": sets, "municipality_tiers": tiers,
               "wv_city_pages": len(wv_cities), "wv_city_mapped_to_municipality": len(mapped),
               "strata_counts": dict(strata), "strata_examples": dict(strata_examples)}
    json.dump(summary, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for s in sets + list(tiers.values()):
        print(f"  {s['set']:16} n={s['looked_up']:6} enwiki {s['enwiki']}% eswiki {s['eswiki']}% kowiki {s['kowiki']}% wv {s['wv_en']}% | 라벨 es {s['label_es']}% en {s['label_en']}% ko {s['label_ko']}% | 설명 es {s['desc_es']}% en {s['desc_en']}% ko {s['desc_ko']}%")
    print(f"  Wikivoyage 도시 문서 {len(wv_cities)}건 중 지자체 매핑 {len(mapped)}건")
    print(f"  층별 지자체 수: {dict(strata)}")
    print(f"  예시: {dict(strata_examples)}")


if __name__ == "__main__":
    main()
