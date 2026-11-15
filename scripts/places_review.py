#!/usr/bin/env python3
"""장소 한국어 설명 검수표(E5 4절 5항 (c), D-033). 생성본과 출처 원문을 장소마다 나란히 적은 Markdown을 만든다.
실행: python3 -I scripts/places_review.py <내용 JSONL> <출처 묶음 JSON(e5.places dump)> <표본 JSON(e5.sample)> <cities.json.gz> <출력.md>
"""
import gzip
import json
import sys

STRATUM = {"big": "대도시", "guide": "중소 관광 도시", "small": "소도시"}
URL = {"wikivoyage": "https://{lang}.wikivoyage.org/wiki/{title}", "wikipedia": "https://{lang}.wikipedia.org/wiki/{title}"}
EXCERPT = 4000  # 표본의 출처는 가장 긴 것도 3,504자라 전문이 들어간다


def main():
    content = {r["id"]: r for r in (json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip())}
    bundles = json.load(open(sys.argv[2], encoding="utf-8"))
    sample = {r["id"]: r for r in json.load(open(sys.argv[3], encoding="utf-8"))}
    cities = {c["id"]: c for c in json.load(gzip.open(sys.argv[4], "rt", encoding="utf-8"))}
    out = ["# 장소 한국어 설명 검수표 (대표 모수)", "",
           "확인할 것: ① 출처와 다른 서술, ② 읽기 쉬움(5점 만점), ③ 길이, ④ 한글 이름 표기. 생성본 아래에 출처 원문을 그대로 적었다.", ""]
    n_detail = 0
    for i, b in enumerate(bundles, 1):
        r = content.get(b["id"])
        if not r:
            continue
        n = b["n"]; city = cities.get(b["city"]) or {}
        cn = (city.get("n") or {}); kinds = {s["kind"] for s in b["sources"] if s["kind"] in URL}
        name = n.get("ko") or r.get("name_ko") or n.get("local")
        orig = " / ".join(dict.fromkeys(x for x in (n.get("local"), n.get("es"), n.get("en")) if x))
        out += [f"## {i}. {name}{' (한글 이름 생성)' if not n.get('ko') and r.get('name_ko') else ''}", "",
                f"- 원어 이름: {orig}",
                f"- 도시: {cn.get('ko') or cn.get('es') or cn.get('local') or b['city']} · 층: {STRATUM.get((sample.get(b['id']) or {}).get('stratum'), '?')} · 범주: {', '.join(b['cat'])} · ID: {b['id']}",
                f"- 신뢰도: {'높음' if len(kinds) >= 2 else '보통'}(글 출처 {len(kinds)}종) · 요약 {len(r['summary_ko'])}자 · 상세 {len(r['detail_ko'])}자", "",
                "**요약**", "", r["summary_ko"], ""]
        if r["detail_ko"]:
            n_detail += 1
            out += ["**상세**", ""] + [x for p in r["detail_ko"].split("\n") for x in (p, "")]
        else:
            out += ["상세 없음(출처가 짧아 요약만 만들었다).", ""]
        out += ["**출처 원문**", ""]
        for s in b["sources"]:
            head = f"{s['lang']}.{s['kind']}" + (f" · [{s['title']}]({URL[s['kind']].format(lang=s['lang'], title=s['title'].replace(' ', '_'))})" if s["kind"] in URL else " 설명")
            text = " ".join(s["text"].split())
            out.append(f"- {head} ({len(text)}자): {text[:EXCERPT]}{' …(뒤 생략)' if len(text) > EXCERPT else ''}")
        out.append("")
    out.insert(4, f"장소 {len(content)}곳 · 상세 있는 곳 {n_detail}곳 · 한글 이름 생성 {sum(1 for r in content.values() if r.get('name_ko'))}곳")
    out.insert(5, "")
    open(sys.argv[5], "w", encoding="utf-8").write("\n".join(out) + "\n")
    print(f"검수표 {len(content)}곳 → {sys.argv[5]}")


if __name__ == "__main__":
    main()
