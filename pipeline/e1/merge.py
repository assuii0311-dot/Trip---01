"""매칭 그룹을 통합 장소 레코드로 만든다 (E1 4절 5~7항, docs/02-data-model.md Place)."""
import re

from . import config as C
from .categories import merge_categories, osm_categories, wd_categories, wv_categories

PRICE_RE = re.compile(r"(?:€\s?(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s?(?:€|euro|eur\b))", re.I)
FREE_RE = re.compile(r"\b(free|gratis|gratuito|gratuita|no charge|libre)\b", re.I)


def parse_price(s):
    """(유로 금액 또는 None, 무료 여부). 금액이 여럿이면 첫 금액(성인 요금 관행)."""
    if not s:
        return None, False
    nums = [float((a or b).replace(",", ".")) for a, b in PRICE_RE.findall(s)]
    nums = [n for n in nums if 0 < n < 5000]
    free_first = bool(re.match(r"\s*(free|gratis|gratuito|gratuita|libre)\b", s, re.I))
    if nums and not free_first:
        return nums[0], False  # 금액이 있으면 첫 금액(보통 성인 요금). "free for children" 같은 부분 무료는 무시
    if FREE_RE.search(s):
        return 0.0, True
    return None, False


def place_from_group(g, pageviews, foreign_cfg=None):
    wd, osm, wv = g["wd"], g["osm"], g["wv"]
    srcs = [s for s, has in (("wd", wd is not None), ("osm", bool(osm)), ("wv", bool(wv))) if has]
    # 좌표 우선순위: OSM > Wikidata > Wikivoyage
    o0 = osm[0] if osm else None
    if o0:
        lat, lon, cs = o0["lat"], o0["lon"], "osm"
    elif wd and wd["coord"]:
        lat, lon, cs = wd["coord"][0], wd["coord"][1], "wikidata"
    else:
        w0 = next((w for w in wv if w.get("lat") is not None), None)
        if not w0:
            return None
        lat, lon, cs = w0["lat"], w0["lon"], "wikivoyage"
    cv = "mismatch" if "mismatch" in g["flags"] else ("match" if len(srcs) >= 2 else "single")
    cc = "high" if cv == "match" and cs != "wikivoyage" else ("low" if cv == "mismatch" or cs == "wikivoyage" else "mid")
    # 명칭
    labels = wd["labels"] if wd else {}
    wv_en = next((w["name"] for w in wv if w["lang"] == "en" and w.get("name")), None)
    wv_es = next((w["name"] for w in wv if w["lang"] == "es" and w.get("name")), None)
    names = {
        "local": (o0 or {}).get("name") or labels.get("es") or wv_es or wv_en or labels.get("en"),
        "es": (o0 or {}).get("name:es") or labels.get("es") or wv_es,
        "en": (o0 or {}).get("name:en") or labels.get("en") or wv_en,
        "ko": (o0 or {}).get("name:ko") or labels.get("ko"),
        "ca": (o0 or {}).get("name:ca") or labels.get("ca"), "eu": (o0 or {}).get("name:eu") or labels.get("eu"), "gl": (o0 or {}).get("name:gl") or labels.get("gl"),
    }
    names = {k: v for k, v in names.items() if v}
    if not names.get("local"):
        return None
    names["ko_src"] = ("osm" if (o0 or {}).get("name:ko") else "wikidata") if names.get("ko") else None
    if not names["ko"] if "ko" in names else True:
        pass
    # 분류
    cats = merge_categories(
        *[osm_categories(o["key"], o["value"]) for o in osm],
        *[wv_categories(w["type"], w.get("raw_type")) for w in wv],
        wd_categories(wd["classes"], bool(wd["heritage"])) if wd else [],
    )
    if not cats and any(w["type"] == "see" for w in wv):
        cats = ["heritage"]  # 유형 없는 see 목록의 기본값
    if not cats:
        return None
    # 영업시간·가격: Wikivoyage > OSM
    hrs = next((w["hours"] for w in wv if w.get("hours")), None)
    hrs_src = "wikivoyage" if hrs else None
    if not hrs:
        hrs = next((o.get("opening_hours") for o in osm if o.get("opening_hours")), None); hrs_src = "osm" if hrs else None
    price_raw = next((w["price"] for w in wv if w.get("price")), None)
    eur, free = parse_price(price_raw)
    price_src = "wikivoyage" if price_raw else None
    if price_raw is None:
        fee = next((o.get("fee") for o in osm if o.get("fee")), None)
        charge = next((o.get("charge") for o in osm if o.get("charge")), None)
        if charge:
            eur, free = parse_price(charge); price_raw, price_src = charge, "osm"
        elif fee == "no":
            eur, free, price_raw, price_src = 0.0, True, "fee=no", "osm"
        elif fee == "yes":
            price_raw, price_src = "fee=yes", "osm"
    tier = next((w["tier"] for w in wv if w.get("tier")), None)
    # 설명 출처(참조만. 본문은 별도 샤드)
    desc = []
    for w in wv:
        if w.get("content"):
            desc.append({"src": "wikivoyage", "lang": w["lang"], "page": w["page"], "idx": w["idx"], "len": len(w["content"]), "lic": "CC BY-SA 4.0"})
    if wd:
        for l, t in wd["desc"].items():
            desc.append({"src": "wikidata", "lang": l, "text": t, "lic": "CC0"})
        for l, t in wd["wiki"].items():
            desc.append({"src": "wikipedia", "lang": l, "title": t, "lic": "CC BY-SA 4.0"})
    # 관심도
    pv = pageviews.get(wd["qid"]) if wd else None
    sl = wd["sitelinks"] if wd else 0
    en, es = (pv or {}).get("en", 0), (pv or {}).get("es", 0)
    fl_share = round(en / (en + es), 3) if (en + es) > 0 else None
    pop = {"sl": sl, "pv": {"en": en, "es": es, "ko": (pv or {}).get("ko", 0)} if pv else None, "en_share": fl_share}
    verified = not (cv == "single" and sl == 0 and not pv)
    heritage = wd["heritage"] if wd else []
    wv_listed = any(w["lang"] == "en" and w["type"] in ("see", "do", "eat", "drink", "sleep", "buy", "listing") for w in wv)
    tier_rank = 1 if (wv_listed or heritage or sl >= C.TIER1_MIN_SITELINKS) else 2
    links = {}
    if wd:
        links.update({f"{l}wiki": t for l, t in wd["wiki"].items()})
    web = next((o.get("website") for o in osm if o.get("website")), None) or next((w.get("url") for w in wv if w.get("url")), None)
    if web:
        links["web"] = web
    pid = wd["qid"] if wd else g["key"]
    return {
        "id": pid, "src": {"wd": wd["qid"] if wd else None, "osm": [o["id"] for o in osm][:5], "wv": [{"lang": w["lang"], "page": w["page"], "idx": w["idx"]} for w in wv][:5]},
        "cv": cv, "ver": verified, "n": names, "lat": lat, "lon": lon, "cs": cs, "cc": cc, "cat": cats, "her": heritage,
        "hrs": hrs, "hrs_src": hrs_src, "price": {"eur": eur, "raw": price_raw, "free": free, "tier": tier, "src": price_src} if (price_raw or tier) else None,
        "desc": desc, "pop": pop, "links": links, "tier": tier_rank,
        "osm_tags": {k: o0.get(k) for k in ("cuisine", "phone", "description", "reservation") if o0 and o0.get(k)} if o0 else {},
    }
