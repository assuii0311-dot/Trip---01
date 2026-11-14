#!/usr/bin/env python3
"""여행지 목록 검수표를 만든다(D-030). data/cities.json.gz의 dest·focus·hl·wv.lead를 읽어 마크다운 표로 쓴다.
검수 결과는 pipeline/e1/config.py의 DEST_OVERRIDES(제외·포함·등급 고정)에 반영하고 데이터를 다시 만든다.
실행: python3 -I scripts/destinations_report.py <cities.json.gz> <regions.json.gz> <airports.json.gz> <출력.md> [<e5/destinations.json.gz>]
다섯째 인자를 주면 E5의 한국어 요약과 생성한 한글 이름을 함께 보인다(D-032 검수용).
"""
import gzip
import json
import math
import sys

KO = {"heritage": "유적", "religious": "종교", "museum": "박물관", "nature": "자연", "park": "공원", "beach": "해변", "square": "광장", "market": "시장", "restaurant": "식당", "cafe": "카페·바", "activity": "체험"}
VIA = {"rank": "순위", "unesco": "유네스코 보정", "island": "섬 포함 규칙", "manual": "수동 보정"}


def hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(x))


def main():
    cities = json.load(gzip.open(sys.argv[1], "rt", encoding="utf-8"))
    regions = {r["id"]: r for r in json.load(gzip.open(sys.argv[2], "rt", encoding="utf-8"))}
    airports = [a for a in json.load(gzip.open(sys.argv[3], "rt", encoding="utf-8")) if (a.get("pax") or 0) >= 100000]
    by_id = {c["id"]: c for c in cities}
    e5 = json.load(gzip.open(sys.argv[5], "rt", encoding="utf-8"))["items"] if len(sys.argv) > 5 else {}
    dest = sorted((c for c in cities if c.get("dest")), key=lambda c: (c["dest"]["tier"], c["dest"]["rank"]))
    def name(c):
        gen = (e5.get(c["id"]) or {}).get("name_ko") if not c["n"].get("ko") else None
        return f"{c['n'].get('ko') or (gen + ' [생성]' if gen else '')} ({c['n'].get('en') or c['n'].get('es') or c['n'].get('local')})".strip()
    region = lambda c: (regions.get((c.get("region") or {}).get("community") or "") or {}).get("n", {}).get("local") or ("섬(자치주 경계 없음)" if c.get("kind") == "island" else "")
    def airport(c):
        best = min(airports, key=lambda a: hav(c["lat"], c["lon"], a["lat"], a["lon"]))
        return f"{best['iata']} {hav(c['lat'], c['lon'], best['lat'], best['lon']):.0f}km"
    L = ["# 여행지 목록 검수표", "", f"- 대상: 여행지 {len(dest)}곳(도시 {sum(1 for c in dest if c.get('kind') != 'island')}, 섬 {sum(1 for c in dest if c.get('kind') == 'island')}). 규칙은 `docs/engines/E1-data-pipeline.md` 4절 14~16항(D-030).",
         "- 등급은 인기 참고값이다(세 신호의 순위 평균: 해외 대표 명소 수, 가이드 목록 수, 영문 월조회수). 취향 중심과 대표 명소도 데이터로 계산한 값이다.",
         "- 검수 방법: 빼야 할 곳, 넣어야 할 곳, 등급을 바꿀 곳을 알려 주면 `pipeline/e1/config.py`의 DEST_OVERRIDES에 반영한다.", ""]
    for tier in (1, 2, 3):
        rows = [c for c in dest if c["dest"]["tier"] == tier]
        L += [f"## 참고 {tier}등급 ({len(rows)}곳)", "", "| 순위 | 여행지 | 종류 | 지역 | 인구 | 취향 중심 | 대표 명소 | 대표 명소 수 | 가이드 목록 | 영문 월조회 | 유네스코 | 가까운 공항 | 선정 | 한국어 소개(생성본) | 영문 가이드 첫 문장 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for c in rows:
            d = c["dest"]; s = d["signals"]
            kind = f"섬(지자체 {len(c['members'])}곳)" if c.get("kind") == "island" else "도시"
            hl = ", ".join(h["n"].get("ko") or h["n"].get("en") or h["n"].get("local") for h in c.get("hl") or [])
            lead = (c["wv"].get("lead") or "").split(". ")[0].replace("|", "/")[:140]
            L.append(f"| {d['rank']} | {name(c)} | {kind} | {region(c)} | {c.get('pop') or 0:,} | {'·'.join(KO[f] for f in c.get('focus') or []) or '—'} | {hl} | {s['foreign']} | {s['listings']} | {s['pv_en']:,} | {d['unesco'] or ''} | {airport(c)} | {VIA[d['via']]} | {((e5.get(c['id']) or {}).get('summary') or '').replace('|', '/')} | {lead} |")
        L.append("")
    isl = [c for c in dest if c.get("kind") == "island"]
    L += ["## 섬 여행지와 소속 지자체", "", "| 섬 | 소속 지자체(인구 순) |", "|---|---|"]
    for c in isl:
        L.append(f"| {name(c)} | {', '.join((by_id[m]['n'].get('ko') or by_id[m]['n'].get('en') or by_id[m]['n'].get('es') or m) for m in c['members'])} |")
    out_rank = sorted((c for c in cities if c.get("dest") is None and "dest" in c), key=lambda c: c["n"].get("en") or "")
    L += ["", f"## 가이드 문서는 있지만 목록에 들지 못한 지자체 ({len(out_rank)}곳)", "", "검색으로는 찾을 수 있다. 목록에 넣으려면 DEST_OVERRIDES의 include에 적는다.", "", ", ".join(name(c) for c in out_rank)]
    open(sys.argv[4], "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"검수표: 여행지 {len(dest)}곳, 목록 밖 가이드 지자체 {len(out_rank)}곳 → {sys.argv[4]}")


if __name__ == "__main__":
    main()
