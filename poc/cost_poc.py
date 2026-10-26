#!/usr/bin/env python3
"""2단계 PoC E 단계: 비용 네 항목(입장료, 식비, 교통비, 숙박비)의 데이터 확보율과 신뢰도를 잰다 (P-11).

- 영문 Wikivoyage 스페인 문서를 다시 파싱해 목록마다 속한 절(H2)과 하위 절(H3: Budget, Mid-range, Splurge)을 기록하고,
  price 필드에서 숫자(유로 금액, 범위, 무료)를 뽑는다.
- OSM의 fee, charge 태그를 센다.
- GTFS 요금 파일 유무는 gtfs 검사 결과 JSON에서 읽는다.
실행: python -I poc/cost_poc.py <영문 덤프.bz2> <OSM pois.jsonl> <GTFS 검사 JSON...> <출력 JSON>
"""
import collections
import json
import re
import statistics
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import wikivoyage_parse as W  # noqa: E402

TIER_WORDS = {"budget": "저가", "mid-range": "중가", "splurge": "고가"}
PRICE_RE = re.compile(r"(?:€\s?(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s?(?:€|euro|eur\b))", re.I)
FREE_RE = re.compile(r"\b(free|gratis|gratuito|no charge)\b", re.I)


def parse_price(s):
    if not s:
        return None
    if FREE_RE.search(s):
        return 0.0
    nums = [float((a or b).replace(",", ".")) for a, b in PRICE_RE.findall(s)]
    nums = [n for n in nums if 0 < n < 5000]
    return min(nums) if nums else None


def main():
    dump, pois, out = sys.argv[1], sys.argv[2], sys.argv[-1]
    gtfs_files = sys.argv[3:-1]
    W.CFG = W.LANG["en"]
    ispartof_re = re.compile(W.CFG["ispartof"])
    texts, parents = {}, {}
    for ns, title, redirect, text in W.iter_pages(dump):
        if ns != "0" or redirect:
            continue
        texts[title] = text
        m = ispartof_re.search(text)
        if m:
            parents[title] = W.norm_title(m.group(1))
    children = collections.defaultdict(list)
    for c, p in parents.items():
        children[p].append(c)
    order, queue = [], ["Spain"]
    seen = set(queue)
    while queue:
        cur = queue.pop(0); order.append(cur)
        for ch in children.get(cur, []):
            if ch not in seen:
                seen.add(ch); queue.append(ch)
    stats = collections.defaultdict(lambda: {"n": 0, "price_field": 0, "numeric": 0, "free": 0, "tier": collections.Counter(), "values": []})
    for title in order:
        text = texts.get(title)
        if not text:
            continue
        # 절 경계
        h2 = [(m.start(), m.group(1).strip().lower()) for m in W.H2_RE.finditer(text)]
        h3 = [(m.start(), m.group(1).strip().lower()) for m in W.H3_RE.finditer(text)]
        pos = 0
        for inner in W.find_templates(text):
            idx = text.find("{{" + inner[:40], pos)
            if idx >= 0:
                pos = idx
            parsed = W.parse_listing(inner)
            if not parsed:
                continue
            ltype, params = parsed
            sec = next((n for p, n in reversed(h2) if p <= idx), "")
            sub = next((n for p, n in reversed(h3) if p <= idx and p > max([p2 for p2, _ in h2 if p2 <= idx] or [0])), "")
            tier = next((v for k, v in TIER_WORDS.items() if k in sub), None)
            st = stats[ltype]; st["n"] += 1
            price = params.get("price")
            if price:
                st["price_field"] += 1
                v = parse_price(price)
                if v is not None:
                    st["numeric"] += 1
                    if v == 0: st["free"] += 1
                    else: st["values"].append(v)
            if tier:
                st["tier"][tier] += 1
    # 도시 문서의 Get in / Get around 절에 유로 금액 언급이 있는지 (교통비 대리 신호)
    transport = {"docs": 0, "get_around_eur": 0, "get_in_eur": 0, "get_around_section": 0}
    for title in order:
        text = texts.get(title)
        if not text:
            continue
        transport["docs"] += 1
        h2 = [(m.start(), m.group(1).strip().lower()) for m in W.H2_RE.finditer(text)] + [(len(text), "")]
        for (a, name), (b, _) in zip(h2, h2[1:]):
            if name.startswith("get around"):
                transport["get_around_section"] += 1
                if PRICE_RE.search(text[a:b]): transport["get_around_eur"] += 1
            elif name.startswith("get in"):
                if PRICE_RE.search(text[a:b]): transport["get_in_eur"] += 1
    result = {"wikivoyage": {}, "wikivoyage_transport": transport}
    for t, st in stats.items():
        vals = sorted(st["values"])
        result["wikivoyage"][t] = {"listings": st["n"], "price_field_pct": round(100 * st["price_field"] / st["n"], 1), "numeric_pct": round(100 * st["numeric"] / st["n"], 1),
                                   "free_pct": round(100 * st["free"] / st["n"], 1), "tier_pct": round(100 * sum(st["tier"].values()) / st["n"], 1), "tier": dict(st["tier"]),
                                   "eur_median": vals[len(vals) // 2] if vals else None, "eur_p25_p75": (vals[len(vals) // 4], vals[3 * len(vals) // 4]) if len(vals) >= 4 else None}
    # OSM 요금 태그
    n = fee = charge = fee_yes = fee_no = 0
    by_cat = collections.defaultdict(lambda: [0, 0])
    for line in open(pois, encoding="utf-8"):
        o = json.loads(line); n += 1
        cat = f'{o["key"]}={o["value"]}'
        by_cat[cat][0] += 1
        if o.get("fee"):
            fee += 1; by_cat[cat][1] += 1
            if o["fee"] == "yes": fee_yes += 1
            elif o["fee"] == "no": fee_no += 1
        if o.get("charge"):
            charge += 1
    top = sorted(((c, v[0], v[1]) for c, v in by_cat.items() if v[0] >= 500), key=lambda x: -x[2] / x[1])[:10]
    result["osm"] = {"places": n, "fee_tag": fee, "fee_yes": fee_yes, "fee_no": fee_no, "charge_tag": charge, "top_fee_coverage": [(c, t_, f_, round(100 * f_ / t_, 1)) for c, t_, f_ in top]}
    # GTFS 요금
    g = []
    for f in gtfs_files:
        for r in json.load(open(f, encoding="utf-8")):
            g.append({"feed": r.get("feed") or r.get("provider"), "fare_attributes": r.get("fare_attributes"), "fare_rules": r.get("fare_rules"), "fare_v2": bool(r.get("fare_v2") or r.get("fare_products")), "samples": r.get("fare_samples")})
    result["gtfs"] = {"feeds": len(g), "with_fare_attributes": sum(1 for x in g if x["fare_attributes"]), "with_fare_v2": sum(1 for x in g if x["fare_v2"]), "detail": g}
    json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for t in ("see", "do", "eat", "drink", "sleep", "buy"):
        r = result["wikivoyage"].get(t)
        if r:
            print(f"  {t:6} n={r['listings']:5} price 필드 {r['price_field_pct']}% 숫자 {r['numeric_pct']}% 무료 {r['free_pct']}% 등급절 {r['tier_pct']}% {r['tier']} 중앙값 €{r['eur_median']} 사분위 {r['eur_p25_p75']}")
    print(f"  교통 절: 문서 {transport['docs']}건 중 Get around 절 {transport['get_around_section']}건, 유로 금액 있음 {transport['get_around_eur']}건; Get in 유로 금액 {transport['get_in_eur']}건")
    print(f"  OSM: fee 태그 {fee}/{n} (yes {fee_yes}, no {fee_no}), charge {charge}; fee 보유율 상위: {result['osm']['top_fee_coverage'][:5]}")
    print(f"  GTFS: {result['gtfs']['feeds']}개 피드 중 요금 파일 {result['gtfs']['with_fare_attributes']}개, 요금 v2 {result['gtfs']['with_fare_v2']}개")


if __name__ == "__main__":
    main()
