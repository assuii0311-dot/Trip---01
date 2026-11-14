"""E1: 여행지 목록(E1 4절 14~16항, D-030). 도시(지자체)와 섬을 한 목록으로 만들고 참고 등급, 취향 중심 표기, 대표 명소, 소개 문장을 붙인다.

모두 순수 함수다(네트워크·파일을 모른다). 고정 입력 테스트는 pipeline/tests/test_e1.py.
- 후보: 영문 Wikivoyage 가이드 문서가 있는 지자체와, 지자체가 1곳 이상 있고 가이드 문서가 있는 섬. 섬에 속한 지자체는 섬으로 대표된다.
- 등급은 정렬과 참고 표시용이다. 선택은 사용자가 요약 정보를 보고 한다(D-030).
"""
import collections
import html
import math
import re

from . import config as C


def place_weight(p):
    """장소의 대표성 가중치: ln(1 + 사이트링크 수) + Wikivoyage 수록이면 0.7(추정값)"""
    return math.log1p((p.get("pop") or {}).get("sl") or 0) + (C.DEST_FOCUS_WV_BONUS if (p.get("src") or {}).get("wv") else 0.0)


def top_places(places, n):
    """취향 범주가 있는 장소 중 가중치 상위 n곳(같으면 ID 순)"""
    ps = [p for p in places if place_weight(p) > 0 and any(k in C.DEST_FOCUS_CATS for k in p["cat"])]
    return sorted(ps, key=lambda p: (-place_weight(p), p["id"]))[:n]


def cat_profile(places):
    """상위 장소의 범주별 가중치 합과 장소 수. 범주가 여럿인 장소는 가중치를 나눈다."""
    w, n = collections.Counter(), collections.Counter()
    for p in top_places(places, C.DEST_FOCUS_TOP_N):
        ks = [k for k in p["cat"] if k in C.DEST_FOCUS_CATS]
        for k in ks:
            w[k] += place_weight(p) / len(ks); n[k] += 1
    return w, n


def taste_focus(profile, counts, base):
    """취향 중심 범주(최대 DEST_FOCUS_MAX개). 점수 = 비중 × ln(비중 ÷ 기준 비중). 기준보다 뚜렷이 높은 범주만 남긴다."""
    tot, btot = sum(profile.values()), sum(base.values())
    if tot <= 0 or btot <= 0:
        return []
    scored = []
    for k in C.DEST_FOCUS_CATS:
        if counts.get(k, 0) < C.DEST_FOCUS_MIN_PLACES or profile.get(k, 0) <= 0 or base.get(k, 0) <= 0:
            continue
        share = profile[k] / tot
        s = share * math.log(share / (base[k] / btot))
        if s >= C.DEST_FOCUS_MIN_SCORE:
            scored.append((-s, k))
    return [k for _, k in sorted(scored)[:C.DEST_FOCUS_MAX]]


def is_foreign_landmark(p):
    pop = p.get("pop") or {}
    return (pop.get("en_share") or 0) >= 0.5 and (pop.get("sl") or 0) >= 10


def highlights(places, n=3):
    """대표 명소 이름. 볼거리 범주(유적·종교·박물관·자연·공원·해변·광장)를 먼저, 그 안에서 해외 대표 명소를 사이트링크 순으로.
    경기장·공연장·식당처럼 볼거리 범주가 없는 장소는 뒤로 보내고, 숙박과 역(이름으로 판별)은 뺀다."""
    def station(p):
        return any(C.DEST_HL_SKIP_NAME.search(v) for v in (p["n"].get("en"), p["n"].get("local")) if v)
    ps = [p for p in places if "lodging" not in p["cat"] and place_weight(p) > 0 and not station(p)]
    sight = lambda p: any(k in C.DEST_HL_SIGHT_CATS for k in p["cat"])
    ps.sort(key=lambda p: (0 if sight(p) else 1, 0 if is_foreign_landmark(p) else 1, -((p.get("pop") or {}).get("sl") or 0), -place_weight(p), p["id"]))
    return [{"id": p["id"], "n": {k: p["n"].get(k) for k in ("ko", "en", "local") if p["n"].get(k)}} for p in ps[:n]]


HATNOTE_RE = re.compile(r"^(For|This article|See also|Not to be confused)\b.*", re.I)


def first_sentences(text, n=2, limit=320):
    """소개 문장: 머리글의 첫 줄(다른 문서 안내 줄은 건너뜀)에서 앞 n문장. limit자를 넘으면 문장 수를 줄이고, 한 문장도 넘으면 낱말 경계에서 자른다."""
    lines = [html.unescape(l).replace("\xa0", " ").strip() for l in (text or "").split("\n")]
    line = next((l for l in lines if l and not HATNOTE_RE.match(l)), "")
    sents, cur = [], ""
    for ch in line:
        cur += ch
        if ch in ".!?" and len(cur.strip()) > 20:
            sents.append(cur.strip()); cur = ""
            if len(sents) >= n:
                break
    if not sents:
        sents = [line] if line else []
    out = ""
    for s_ in sents:
        if out and len(out) + 1 + len(s_) > limit:
            break
        out = (out + " " + s_).strip()
    if len(out) > limit:
        out = out[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return out or None


def island_record(isl, members, places):
    """섬을 도시 레코드와 같은 모양으로 만든다(앱이 같은 코드로 다루게). 좌표·지역·가격대·택시는 인구가 가장 많은 지자체(중심 도시) 것을 쓴다."""
    ms = sorted(members, key=lambda c: (-(c.get("pop") or 0), c["id"]))
    cap = ms[0]
    cat = collections.Counter()
    for c in ms:
        cat.update((c.get("places") or {}).get("cat") or {})
    feeds, seen = [], set()
    for c in ms:
        for f in c.get("transit_feeds") or []:
            if f.get("mdb") not in seen:
                seen.add(f.get("mdb")); feeds.append(f)
    districts = sorted((d for c in ms for d in c.get("districts") or []), key=lambda d: (-d["lodging"], d["id"]))[:30]
    prof = next((c["price_profile"] for c in ms if c.get("price_profile")), None)
    return {
        "id": isl["id"], "kind": "island", "members": [c["id"] for c in ms], "capital": cap["id"],
        "n": {"local": isl["n"].get("local"), "es": isl["n"].get("es"), "en": isl["n"].get("en"), "ko": isl["n"].get("ko"), "ca": None, "eu": None, "gl": None},
        "lat": cap["lat"], "lon": cap["lon"], "pop": sum(c.get("pop") or 0 for c in ms), "stratum": "island", "region": cap.get("region"),
        "wv": {"en": isl["wv"]["en"], "lead": isl["wv"].get("lead"), "understand": isl["wv"].get("understand"),
               "listings": isl["wv"].get("listings") or 0, "pages": [isl["wv"]["en"]]},
        "wiki": isl.get("wiki") or {}, "sl": None, "pv": isl.get("pv"),
        "places": {"tier1": sum((c.get("places") or {}).get("tier1") or 0 for c in ms), "tier2": sum((c.get("places") or {}).get("tier2") or 0 for c in ms),
                   "cat": dict(cat), "foreign": sum(1 for p in places if p.get("tier") == 1 and is_foreign_landmark(p))},
        "lodging_3km": cap.get("lodging_3km") or 0, "districts": districts, "price_profile": prof, "transit_feeds": feeds, "taxi_fare": cap.get("taxi_fare"),
    }


def competition_ranks(items, key):
    """값이 큰 순서의 순위(1부터). 같은 값은 같은 순위."""
    order = sorted(items, key=lambda x: -key(x))
    ranks, prev, r = {}, None, 0
    for i, x in enumerate(order, 1):
        v = key(x)
        if v != prev:
            r, prev = i, v
        ranks[x["id"]] = r
    return ranks


def build_destinations(cities, places_by_city, islands, overrides=None):
    """도시 레코드에 여행지 필드를 붙이고 섬 레코드를 더한다.

    cities: build의 도시 레코드(제자리에서 고친다). places_by_city: {지자체 ID: [장소...]}.
    islands: [{id, n{local,es,en,ko}, members[지자체 ID], wv{en,lead,understand,listings}, wiki, pv}] (가이드 문서가 있는 섬만).
    반환: (섬 레코드 목록, 보고서 dict)
    붙이는 필드: focus(취향 중심 범주), hl(대표 명소), island(소속 섬 ID), dest{tier, rank, via, unesco, signals}. 소개 문장(wv.lead)은 build가 넣는다.
    """
    ov = overrides if overrides is not None else C.DEST_OVERRIDES
    by_id = {c["id"]: c for c in cities}
    island_recs, member_of = [], {}
    for isl in sorted(islands, key=lambda x: x["id"]):
        members = [by_id[m] for m in isl["members"] if m in by_id]
        if not members or isl["id"] in by_id:  # 섬 ID가 지자체 ID와 같으면 지자체가 이미 그 섬을 대표한다
            continue
        ps = [p for m in members for p in places_by_city.get(m["id"], [])]
        rec = island_record(isl, members, ps)
        island_recs.append(rec)
        for m in members:
            m["island"] = rec["id"]; member_of[m["id"]] = rec["id"]
    places_of = lambda c: [p for m in c["members"] for p in places_by_city.get(m, [])] if c.get("kind") == "island" else places_by_city.get(c["id"], [])
    cands = [c for c in cities if (c.get("wv") or {}).get("en")] + island_recs
    profiles, base = {}, collections.Counter()
    for c in cands:
        t1 = [p for p in places_of(c) if p.get("tier") == 1]
        w, n = cat_profile(t1)
        profiles[c["id"]] = (w, n, t1)
        if c["id"] not in member_of:  # 기준 비중은 목록 후보(섬에 속한 지자체 제외)로 낸다
            base.update(w)
    for c in cands:
        w, n, t1 = profiles[c["id"]]
        c["focus"] = taste_focus(w, n, base)
        c["hl"] = highlights(t1)
    # 순위: 세 신호의 순위 평균
    pool = [c for c in cands if c["id"] not in member_of and c["id"] not in set(ov.get("exclude") or [])]
    sig = lambda c: {"foreign": (c.get("places") or {}).get("foreign") or 0, "listings": (c.get("wv") or {}).get("listings") or 0, "pv_en": (c.get("pv") or {}).get("en") or 0}
    rk = [competition_ranks(pool, lambda c, k=k: sig(c)[k]) for k in ("foreign", "listings", "pv_en")]
    score = {c["id"]: sum(r[c["id"]] for r in rk) / 3 for c in pool}
    pool.sort(key=lambda c: (score[c["id"]], -(c.get("pop") or 0), c["id"]))
    s1, s2, s3 = C.DEST_TIER_SIZES
    report = {"candidates": len(pool), "islands": len(island_recs), "island_members": len(member_of), "via": collections.Counter(), "tiers": collections.Counter()}
    for i, c in enumerate(pool, 1):
        unesco = sum(1 for p in profiles[c["id"]][2] if C.WD_WORLD_HERITAGE in (p.get("her") or []))
        tier = 1 if i <= s1 else 2 if i <= s1 + s2 else 3 if i <= s1 + s2 + s3 else None
        via = "rank" if tier else None
        if tier is None and c.get("kind") == "island":
            tier, via = 3, "island"
        if tier is None and unesco:
            tier, via = 3, "unesco"
        if c["id"] in (ov.get("include") or {}):
            tier, via = (tier or ov["include"][c["id"]]), (via or "manual")
        if c["id"] in (ov.get("tier") or {}):
            tier, via = ov["tier"][c["id"]], "manual"
        c["dest"] = {"tier": tier, "rank": i, "via": via, "unesco": unesco, "signals": sig(c)} if tier else None
        if tier:
            report["via"][via] += 1; report["tiers"][str(tier)] += 1
    report["via"], report["tiers"] = dict(report["via"]), dict(report["tiers"])
    report["destinations"] = sum(report["tiers"].values())
    return island_recs, report
