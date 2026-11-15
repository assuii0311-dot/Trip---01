#!/usr/bin/env python3
"""E5: 전수 생성의 대상 장소 고르기(E5 4절 10항, D-038). 같은 입력에 같은 목록이 나온다.

- 대상: 여행지(dest가 있는 도시와 섬)마다 볼거리 범주 1등급 장소의 대표성 상위 N곳과 여행지 카드의 대표 명소(hl).
- 대표성: 사이트링크 수 → 영어·스페인어 월조회수 합 → 장소 ID 순.
- 출력 순서: 여행지 참고 순위 → 여행지 안의 대표성 순위. 앞에서부터 만들면 인기 여행지의 주요 장소가 먼저 채워진다.
- --text-only: 글 출처(Wikivoyage 목록 또는 위키백과 문서)가 있는 장소만. --exclude: 이미 만든 내용 파일(JSONL)의 장소는 뺀다.
- --top 0: 수를 제한하지 않는다. --all-cats: 볼거리 밖의 범주(식당, 숙박 등)도 넣되 여행지 안에서 볼거리 뒤에 둔다.
- --first: 앞서 만든 목록(JSON). 그 장소들을 같은 순서로 맨 앞에 두고 나머지를 뒤에 붙인다(범위를 넓힐 때 앞 범위의 순서를 지킨다).
실행: python -I pipeline/run.py e5.scope <places_tier1.json.gz> <cities.json.gz> <출력 JSON> [--top 10] [--all-cats] [--text-only] [--first <목록 JSON>] [--exclude <내용 JSONL> ...]
"""
import argparse
import gzip
import json

from .sample import SIGHT_CATS, has_text_source


def prominence(p):
    pop = p.get("pop") or {}
    pv = pop.get("pv") or {}
    return (-(pop.get("sl") or 0), -((pv.get("en") or 0) + (pv.get("es") or 0)), p["id"])


def select_scope(places, cities, top=10, text_only=False, exclude=(), all_cats=False):
    """[{id, dest, dest_rank, rank, hl, text}] 여행지 순위와 대표성 순. 여러 여행지에 걸친 장소(섬과 그 안의 도시)는 순위가 앞선 여행지에 한 번만 넣는다."""
    by_id = {p["id"]: p for p in places}
    by_muni = {}
    for p in places:
        if p.get("tier") == 1 and p.get("cat") and (all_cats or p["cat"][0] in SIGHT_CATS):
            by_muni.setdefault(p.get("city"), []).append(p)
    sight_first = lambda p: (0 if p["cat"][0] in SIGHT_CATS else 1,) + prominence(p)  # noqa: E731
    skip, seen, out = set(exclude), set(), []
    for c in sorted((c for c in cities if c.get("dest")), key=lambda c: (c["dest"]["rank"], c["id"])):
        pool = [p for m in (c.get("members") or [c["id"]]) for p in by_muni.get(m, [])]
        ranked = sorted(pool, key=sight_first)
        ranked = ranked[:top] if top else ranked
        hl = [by_id[h["id"]] for h in (c.get("hl") or []) if h.get("id") in by_id]
        hl_ids = {p["id"] for p in hl}
        for rank, p in enumerate(ranked + [p for p in hl if p["id"] not in {x["id"] for x in ranked}], 1):
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            text = has_text_source(p)
            if p["id"] in skip or (text_only and not text):
                continue
            out.append({"id": p["id"], "dest": c["id"], "dest_rank": c["dest"]["rank"], "rank": rank, "hl": p["id"] in hl_ids, "text": text})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("places"); ap.add_argument("cities"); ap.add_argument("out")
    ap.add_argument("--top", type=int, default=10); ap.add_argument("--text-only", action="store_true"); ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--all-cats", action="store_true"); ap.add_argument("--first")
    a = ap.parse_args()
    places = json.load(gzip.open(a.places, "rt", encoding="utf-8")); cities = json.load(gzip.open(a.cities, "rt", encoding="utf-8"))
    done = {json.loads(l)["id"] for f in a.exclude for l in open(f, encoding="utf-8") if l.strip()}
    scope = select_scope(places, cities, top=a.top, text_only=a.text_only, exclude=done, all_cats=a.all_cats)
    if a.first:
        first = [x for x in json.load(open(a.first, encoding="utf-8")) if x["id"] not in done]
        ids = {x["id"] for x in first}
        scope = first + [x for x in scope if x["id"] not in ids]
    json.dump(scope, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"대상 {len(scope)}곳(여행지 {len({s['dest'] for s in scope})}곳, 대표 명소 {sum(s['hl'] for s in scope)}, 글 출처 있음 {sum(s['text'] for s in scope)}, 이미 만든 곳 제외 {len(done)}) → {a.out}")


if __name__ == "__main__":
    main()
