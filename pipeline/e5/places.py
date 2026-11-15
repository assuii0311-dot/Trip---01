#!/usr/bin/env python3
"""E5: 장소 한국어 설명(E5 4절 9항, D-033). 개발 세션에서 생성한 내용 파일을 검증해 data/e5/places/<샤드>.json.gz와 data/e5/index.json으로 내보낸다.

- 출처 묶음: 장소 레코드의 desc에 적힌 Wikivoyage 목록 본문(data/sources 샤드), 위키백과 머리 문단(e1.wikipedia_extracts의 JSONL), Wikidata 설명.
- 내용 파일(pipeline/e5/content/places_ko.jsonl): 한 줄에 {id, summary_ko, detail_ko, name_ko, src_md5, generated}. detail_ko는 빈 줄 없이 "\\n"으로 단락을 나눈다.
- 검증: 요약 200자, 상세 1,200자와 단락 2~4개(상세가 있을 때), 평서문 끝, 금지어, 출처 해시. 출처 묶음이 바뀐 장소는 내보내지 않는다(E5 4절 6항).
- 신뢰도: 글 출처가 둘 이상(Wikivoyage와 위키백과. 위키백과 언어판은 하나로 센다)이면 높음, 하나면 보통.
실행:
  python -I pipeline/run.py e5.places dump <ID 목록 JSON> <places_tier1.json.gz> <data/sources> <발췌 JSONL> <출력 JSON>      # 생성에 쓸 출처 묶음
  python -I pipeline/run.py e5.places build <내용 JSONL> <places_tier1.json.gz> <data/sources> <발췌 JSONL> --out <data/e5> [--stamp]
"""
import argparse
import gzip
import hashlib
import json
import pathlib
import sys

from .destinations import BANNED

SUMMARY_MAX = 200
DETAIL_MAX = 1200
LICENSE = "CC BY-SA 4.0"
WIKI_URL = {"wikivoyage": "https://{lang}.wikivoyage.org/wiki/{title}", "wikipedia": "https://{lang}.wikipedia.org/wiki/{title}"}


def shard_of(place_id):
    return hashlib.md5(place_id.encode("utf-8")).hexdigest()[:2]


def source_bundle(place, wv_text, extracts):
    """장소의 글 출처 목록. wv_text: {(id, lang, page, idx): 본문}, extracts: {(lang, title): 머리 문단}. 순서는 desc에 적힌 순서."""
    out = []
    for d in place.get("desc") or []:
        if d.get("src") == "wikivoyage":
            text = wv_text.get((place["id"], d["lang"], d["page"], d["idx"]))
            if text:
                out.append({"kind": "wikivoyage", "lang": d["lang"], "title": d["page"], "license": d.get("lic") or LICENSE, "text": text})
        elif d.get("src") == "wikipedia":
            text = extracts.get((d["lang"], d["title"]))
            if text:
                out.append({"kind": "wikipedia", "lang": d["lang"], "title": d["title"], "license": d.get("lic") or LICENSE, "text": text})
        elif d.get("src") == "wikidata" and d.get("text"):
            out.append({"kind": "wikidata", "lang": d["lang"], "title": None, "license": d.get("lic") or "CC0", "text": d["text"]})
    return out


def source_md5(bundle):
    h = hashlib.md5()
    for s in bundle:
        h.update(f"{s['kind']}|{s['lang']}|{s['title']}|{s['text']}\n".encode("utf-8"))
    return h.hexdigest()


def confidence(bundle):
    """(신뢰도, 글 출처 수). Wikidata 설명은 한 줄이라 글 출처로 세지 않는다."""
    kinds = {s["kind"] for s in bundle if s["kind"] in ("wikivoyage", "wikipedia")}
    return ("높음" if len(kinds) >= 2 else "보통"), len(kinds)


def validate(rec):
    out = []
    s, d = rec.get("summary_ko") or "", rec.get("detail_ko") or ""
    if not s:
        out.append("요약 없음")
    if len(s) > SUMMARY_MAX:
        out.append(f"요약 {len(s)}자({SUMMARY_MAX}자 초과)")
    if s and not s.endswith("다."):
        out.append("요약이 평서문으로 끝나지 않음")
    if d:
        paras = d.split("\n")
        if len(d) > DETAIL_MAX:
            out.append(f"상세 {len(d)}자({DETAIL_MAX}자 초과)")
        if not 2 <= len(paras) <= 4:
            out.append(f"상세 단락 {len(paras)}개(2~4개여야 함)")
        if any(not p.strip() for p in paras):
            out.append("상세에 빈 단락")
        if any(p.strip() and not p.strip().endswith("다.") for p in paras):
            out.append("상세 단락이 평서문으로 끝나지 않음")
    out += [f"금지어 '{b}'" for b in BANNED if b in s or b in d]
    return out


def attribution(bundle):
    names = []
    if any(s["kind"] == "wikivoyage" for s in bundle):
        names.append("Wikivoyage(CC BY-SA 4.0)")
    if any(s["kind"] == "wikipedia" for s in bundle):
        names.append("위키백과(CC BY-SA 4.0)")
    if any(s["kind"] == "wikidata" for s in bundle):
        names.append("Wikidata(CC0)")
    return "출처: " + ", ".join(names) + ". 이 설명은 위 출처를 바탕으로 만든 생성본입니다."


def build(content, places, bundles, generated=None):
    """(샤드별 객체 {샤드: {장소 ID: 항목}}, 색인, 보고서). bundles: {장소 ID: 출처 묶음}"""
    by_id = {p["id"]: p for p in places}
    shards, names, report = {}, {}, {"invalid": {}, "stale": [], "unknown": [], "no_source": [], "name_ignored": []}
    for rec in sorted(content, key=lambda r: r["id"]):
        p = by_id.get(rec["id"])
        if not p:
            report["unknown"].append(rec["id"]); continue
        problems = validate(rec)
        if problems:
            report["invalid"][rec["id"]] = problems; continue
        bundle = bundles.get(rec["id"]) or []
        if not bundle:
            report["no_source"].append(rec["id"]); continue
        if source_md5(bundle) != rec.get("src_md5"):
            report["stale"].append(rec["id"]); continue
        name = rec.get("name_ko") or None
        if name and (p.get("n") or {}).get("ko"):
            report["name_ignored"].append(rec["id"]); name = None
        conf, n_src = confidence(bundle)
        item = {"summary": rec["summary_ko"], "detail": (rec.get("detail_ko") or "").split("\n") if rec.get("detail_ko") else [], "name_ko": name,
                "confidence": conf, "source_count": n_src, "basis": "text", "attribution": attribution(bundle),
                "sources": [{"kind": s["kind"], "lang": s["lang"], "title": s["title"], "license": s["license"],
                             "url": WIKI_URL[s["kind"]].format(lang=s["lang"], title=s["title"].replace(" ", "_")) if s["kind"] in WIKI_URL else None} for s in bundle],
                "generated": rec.get("generated")}
        shards.setdefault(shard_of(rec["id"]), {})[rec["id"]] = item
        if name:
            names[rec["id"]] = name
    count = sum(len(v) for v in shards.values())
    index = {"format": "trip01-e5-index", "version": 1, "generated": generated, "license": LICENSE, "places": count, "place_shards": sorted(shards), "names": dict(sorted(names.items()))}
    report["count"] = count; report["names"] = len(names)
    return shards, index, report


def load_inputs(places_path, sources_dir, extracts_path, ids):
    places = json.load(gzip.open(places_path, "rt", encoding="utf-8"))
    idset = set(ids)
    wv_text = {}
    for sh in sorted({shard_of(i) for i in idset}):
        f = pathlib.Path(sources_dir) / f"{sh}.json.gz"
        if f.exists():
            for key, text in json.load(gzip.open(f, "rt", encoding="utf-8")).items():
                pid, lang, page, idx = key.rsplit("|", 3)
                if pid in idset:
                    wv_text[(pid, lang, page, int(idx))] = text
    extracts = {}
    if extracts_path and pathlib.Path(extracts_path).exists():
        for l in open(extracts_path, encoding="utf-8"):
            r = json.loads(l); extracts[(r["lang"], r["title"])] = r["extract"]
    bundles = {p["id"]: source_bundle(p, wv_text, extracts) for p in places if p["id"] in idset}
    return places, bundles


def write_gz(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as f:  # 같은 입력에 같은 바이트
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump"); [d.add_argument(x) for x in ("ids", "places", "sources", "extracts", "out")]
    b = sub.add_parser("build"); [b.add_argument(x) for x in ("content", "places", "sources", "extracts")]; b.add_argument("--out", required=True); b.add_argument("--stamp", action="store_true")
    a = ap.parse_args()
    if a.cmd == "dump":
        raw = json.load(open(a.ids, encoding="utf-8")); ids = [x["id"] if isinstance(x, dict) else x for x in raw]
        places, bundles = load_inputs(a.places, a.sources, a.extracts, ids)
        by_id = {p["id"]: p for p in places}
        out = [{"id": i, "n": by_id[i]["n"], "cat": by_id[i]["cat"], "her": by_id[i].get("her"), "city": by_id[i].get("city"), "src_md5": source_md5(bundles[i]), "sources": bundles[i]} for i in ids]
        json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"출처 묶음 {len(out)}건 → {a.out}"); return
    content = [json.loads(l) for l in open(a.content, encoding="utf-8") if l.strip()]
    places, bundles = load_inputs(a.places, a.sources, a.extracts, [r["id"] for r in content])
    if a.stamp:
        for rec in content:
            if bundles.get(rec["id"]):
                rec["src_md5"] = source_md5(bundles[rec["id"]])
        with open(a.content, "w", encoding="utf-8") as f:
            for rec in content:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    shards, index, report = build(content, places, bundles, generated=max((r.get("generated") or "" for r in content), default=None))
    out = pathlib.Path(a.out)
    for sh, items in shards.items():
        write_gz(out / "places" / f"{sh}.json.gz", items)
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"장소 설명 {report['count']}건(샤드 {len(shards)}개, 이름 생성 {report['names']}건) → {out}")
    for k in ("invalid", "stale", "unknown", "no_source", "name_ignored"):
        if report[k]:
            print(f"  {k}: {report[k]}")
    if report["invalid"] or report["stale"] or report["unknown"] or report["no_source"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
