#!/usr/bin/env python3
"""E5: 대표 모수(층화 표본) 선정(E5 4절 5항 (b), D-033). 같은 입력에 같은 표본이 나온다.

- 층: 장소가 속한 도시의 층(cities의 stratum). 대도시(big), 중소 관광 도시(guide), 데이터 빈약 소도시(small)에서 각 10곳.
- 후보: 1등급이고 볼거리 범주가 있으며 글 출처(Wikivoyage 목록 또는 위키백과 문서)가 하나 이상인 장소.
- 순서: md5(장소 ID)의 오름차순. 한 도시에서 2곳까지, 한 층에서 같은 대표 범주는 4곳까지.
- 대도시 층은 절반(5곳)을 해외 대표 명소에서 뽑는다(생성 순서 (3)의 대상이 표본에 들어가게. 제안값).
실행: python -I pipeline/run.py e5.sample <places_tier1.json.gz> <cities.json.gz> <출력 JSON>
"""
import gzip
import hashlib
import json
import sys

STRATA = ("big", "guide", "small")
PER_STRATUM = 10
MAX_PER_CITY = 2
MAX_PER_CATEGORY = 4
BIG_LANDMARKS = 5
SIGHT_CATS = ("heritage", "religious", "museum", "nature", "park", "beach", "square", "activity", "market")


def has_text_source(p):
    """글 출처가 있는가: 본문이 있는 Wikivoyage 목록(desc에 길이와 함께 기록된다) 또는 위키백과 문서"""
    return any(d.get("src") in ("wikivoyage", "wikipedia") for d in p.get("desc") or [])


def is_landmark(p):
    pop = p.get("pop") or {}
    return (pop.get("en_share") or 0) >= 0.5 and (pop.get("sl") or 0) >= 10


def order_key(p):
    return hashlib.md5(p["id"].encode("utf-8")).hexdigest()


def pick(cands, n, per_city, per_cat, city_count, cat_count):
    out = []
    for p in sorted(cands, key=order_key):
        if len(out) >= n:
            break
        c, k = p.get("city"), p["cat"][0]
        if city_count.get(c, 0) >= per_city or cat_count.get(k, 0) >= per_cat:
            continue
        city_count[c] = city_count.get(c, 0) + 1; cat_count[k] = cat_count.get(k, 0) + 1
        out.append(p)
    return out


def select_sample(places, cities):
    """[{id, stratum, landmark}] 30건(후보가 모자라면 그보다 적다)"""
    stratum = {c["id"]: c.get("stratum") for c in cities if c.get("kind") != "island"}
    cands = [p for p in places if p.get("tier") == 1 and p.get("city") in stratum and has_text_source(p) and any(k in SIGHT_CATS for k in p["cat"][:1])]
    out = []
    for s in STRATA:
        pool = [p for p in cands if stratum[p["city"]] == s]
        city_count, cat_count = {}, {}
        chosen = []
        if s == "big":
            chosen += pick([p for p in pool if is_landmark(p)], BIG_LANDMARKS, MAX_PER_CITY, MAX_PER_CATEGORY, city_count, cat_count)
        ids = {p["id"] for p in chosen}
        chosen += pick([p for p in pool if p["id"] not in ids and not (s == "big" and is_landmark(p))], PER_STRATUM - len(chosen), MAX_PER_CITY, MAX_PER_CATEGORY, city_count, cat_count)
        out += [{"id": p["id"], "stratum": s, "landmark": is_landmark(p)} for p in chosen]
    return out


def main():
    places = json.load(gzip.open(sys.argv[1], "rt", encoding="utf-8")); cities = json.load(gzip.open(sys.argv[2], "rt", encoding="utf-8"))
    sample = select_sample(places, cities)
    json.dump(sample, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"표본 {len(sample)}건 → {sys.argv[3]}")


if __name__ == "__main__":
    main()
