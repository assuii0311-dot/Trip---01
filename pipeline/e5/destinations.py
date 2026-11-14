#!/usr/bin/env python3
"""E5: 여행지 한국어 소개(E5 4절 8항, D-032). 개발 세션에서 생성한 내용 파일을 검증해 data/e5/destinations.json.gz로 내보낸다.

- 내용 파일(pipeline/e5/content/destinations_ko.jsonl): 한 줄에 {id, page, summary_ko, name_ko, src_md5, generated}.
  요약은 영문 Wikivoyage 가이드 문서의 머리글과 Understand 절에 있는 사실만으로 쓴다(E5 4절 3항).
- 검증: 길이(200자), 문장 끝, 금지어(평가어와 영업시간·가격·예약), 출처 해시. 출처 문서가 바뀌면(src_md5 불일치) 내보내지 않고 "낡음"으로 보고한다(E5 4절 6항).
- 순수 함수(validate, source_md5, build)는 네트워크와 파일을 모른다. 테스트는 pipeline/tests/test_e5.py.
실행: python -I pipeline/run.py e5.destinations <내용 JSONL> <cities.json.gz> <wv_en/pages.jsonl> --out <data/e5/destinations.json.gz> [--stamp]
  --stamp: 현재 출처 문서의 해시를 내용 파일에 적는다(새로 생성했거나 출처와 다시 대조한 뒤에만 쓴다).
"""
import argparse
import gzip
import hashlib
import json
import pathlib
import sys

SUMMARY_MAX = 200
LICENSE = "CC BY-SA 4.0"
# 평가어와 데이터 필드로 따로 보이는 항목(E5 4절 3항, 6절 금지 항목). 부분 문자열로 찾는다
BANNED = ("아름다", "멋진", "멋있", "환상적", "매력", "훌륭", "최고의", "꼭 가", "놓치", "추천", "볼 만", "가볼 만", "완벽", "낭만", "숨은 보석",
          "영업", "입장료", "예약", "유로", "€", "시간표", "요금")


def source_md5(page):
    """출처 문서의 머리글과 Understand 절로 만든 해시. 이 값이 바뀌면 요약을 다시 대조해야 한다."""
    text = (page.get("lead") or "") + "\n" + (page.get("understand") or "")
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def validate(rec):
    """내용 한 건의 문제 목록(없으면 빈 목록)"""
    out = []
    s = rec.get("summary_ko") or ""
    if not s:
        out.append("요약 없음")
    if len(s) > SUMMARY_MAX:
        out.append(f"요약 {len(s)}자({SUMMARY_MAX}자 초과)")
    if s and not s.endswith("다."):
        out.append("평서문으로 끝나지 않음")
    out += [f"금지어 '{b}'" for b in BANNED if b in s]
    if not rec.get("page"):
        out.append("출처 문서 제목 없음")
    return out


def build(content, cities, pages, generated=None):
    """내보낼 객체와 보고서를 만든다.

    content: 내용 파일의 레코드 목록. cities: cities.json.gz의 레코드. pages: {문서 제목: {lead, understand}}.
    여행지(dest가 있는 레코드)이고 검증을 통과하며 출처 해시가 맞는 것만 내보낸다. 한국어 이름이 이미 있는 여행지의 name_ko는 쓰지 않는다.
    """
    by_id = {c["id"]: c for c in cities}
    dest_ids = [c["id"] for c in cities if c.get("dest")]
    items, report = {}, {"invalid": {}, "stale": [], "not_destination": [], "name_ignored": []}
    for rec in sorted(content, key=lambda r: r["id"]):
        c = by_id.get(rec["id"])
        if not c or not c.get("dest"):
            report["not_destination"].append(rec["id"]); continue
        problems = validate(rec)
        if problems:
            report["invalid"][rec["id"]] = problems; continue
        page = pages.get(rec["page"])
        if not page or source_md5(page) != rec.get("src_md5"):
            report["stale"].append(rec["id"]); continue
        name = rec.get("name_ko") or None
        if name and (c.get("n") or {}).get("ko"):
            report["name_ignored"].append(rec["id"]); name = None
        items[rec["id"]] = {"summary": rec["summary_ko"], "name_ko": name, "confidence": "보통", "basis": "text",
                            "sources": [{"title": rec["page"], "lang": "en", "url": "https://en.wikivoyage.org/wiki/" + rec["page"].replace(" ", "_"), "license": LICENSE}],
                            "generated": rec.get("generated")}
    report["missing"] = sorted(i for i in dest_ids if i not in items)
    report["count"] = len(items); report["names"] = sum(1 for v in items.values() if v["name_ko"]); report["destinations"] = len(dest_ids)
    out = {"format": "trip01-e5-destinations", "version": 1, "generated": generated, "license": LICENSE,
           "attribution": "출처: Wikivoyage(CC BY-SA 4.0) 영문 가이드를 바탕으로 만든 한국어 요약(생성본)", "items": items}
    return out, report


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("content"); ap.add_argument("cities"); ap.add_argument("pages"); ap.add_argument("--out", required=True); ap.add_argument("--stamp", action="store_true")
    a = ap.parse_args()
    content = [json.loads(l) for l in open(a.content, encoding="utf-8") if l.strip()]
    cities = json.load(gzip.open(a.cities, "rt", encoding="utf-8"))
    pages = {}
    for l in open(a.pages, encoding="utf-8"):
        r = json.loads(l); pages[r["title"]] = r
    if a.stamp:
        for rec in content:
            if rec.get("page") in pages:
                rec["src_md5"] = source_md5(pages[rec["page"]])
        with open(a.content, "w", encoding="utf-8") as f:
            for rec in content:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out, report = build(content, cities, pages, generated=max((r.get("generated") or "" for r in content), default=None))
    p = pathlib.Path(a.out); p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as f:  # 시각과 파일 이름을 머리에 넣지 않아 같은 입력에 같은 바이트가 나온다
        f.write(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    print(f"여행지 소개 {report['count']}/{report['destinations']}건(이름 생성 {report['names']}건) → {a.out}")
    for k in ("invalid", "stale", "not_destination", "name_ignored", "missing"):
        if report[k]:
            print(f"  {k}: {report[k]}")
    if report["invalid"] or report["stale"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
