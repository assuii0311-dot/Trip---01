#!/usr/bin/env python3
"""E5: 장소 한국어 설명(E5 4절 9항, D-033). 개발 세션에서 생성한 내용 파일을 검증해 data/e5/places/<샤드>.json.gz와 data/e5/index.json으로 내보낸다.

- 출처 묶음: 장소 레코드의 desc에 적힌 Wikivoyage 목록 본문(data/sources 샤드), 위키백과 머리 문단(e1.wikipedia_extracts의 JSONL), Wikidata 설명.
- 내용 파일(pipeline/e5/content/places_ko.jsonl): 한 줄에 {id, summary_ko, detail_ko, name_ko, src_md5, generated}. detail_ko는 빈 줄 없이 "\\n"으로 단락을 나눈다.
- 검증: 요약 200자, 상세 1,200자와 단락 2~4개(상세가 있을 때), 평서문 끝, 금지어, 출처 해시. 출처 묶음이 바뀐 장소는 내보내지 않는다(E5 4절 6항).
- 신뢰도: 글 출처가 둘 이상(Wikivoyage와 위키백과. 위키백과 언어판은 하나로 센다)이면 높음, 하나면 보통.
실행:
  python -I pipeline/run.py e5.places dump <ID 목록 JSON> <places_tier1.json.gz> <data/sources> <발췌 JSONL> <출력 JSON>      # 생성에 쓸 출처 묶음
  python -I pipeline/run.py e5.places build <내용 JSONL> <places_tier1.json.gz> <data/sources> <발췌 JSONL> --out <data/e5> [--stamp]
전수 생성(D-038)에서는 대상이 많아 묶음으로 나눠 만든다.
  python -I pipeline/run.py e5.places chunks <ID 목록 JSON> <places_tier1.json.gz> <cities.json.gz> <data/sources> <발췌 JSONL> <묶음 디렉터리> [--size 40] [--ready-only] [--limit N]
      # 이미 묶음에 들어간 장소는 건너뛰고 번호를 이어 붙인다. --ready-only는 위키백과 발췌를 모두 받은 장소만 넣는다(수집과 생성을 나란히 돌릴 때)
  python -I pipeline/run.py e5.places check <부분 JSONL> <묶음 JSON>      # 한 묶음의 생성 결과 검사. 문제가 있으면 종료 코드 1
  python -I pipeline/run.py e5.places merge <내용 JSONL> <부분 디렉터리>   # 검사를 통과한 부분 파일을 내용 파일에 붙인다(이미 있는 장소는 그대로)
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


CHUNK_TEXT_MAX = 2200   # 묶음 파일에 싣는 출처 하나의 글자 수 한도(해시는 전문으로 계산한다)
CHUNK_CHARS_MAX = 48000  # 한 묶음의 출처 글자 수 한도
HERITAGE = {"Q23712": "bic", "Q9259": "unesco"}  # 스페인 문화재(Bien de Interés Cultural), 유네스코 세계유산


def is_ready(place, fetched):
    """그 장소의 위키백과 문서를 모두 받아 보았는가(문서가 없다는 답도 받은 것으로 친다). fetched: {(lang, title)}"""
    return all((d["lang"], d["title"]) in fetched for d in place.get("desc") or [] if d.get("src") == "wikipedia")


def make_chunks(ids, places, cities, bundles, size=40):
    """생성 작업자가 읽을 묶음 목록. 묶음마다 장소 size곳 이하, 출처 글자 수 CHUNK_CHARS_MAX 이하. 글 출처가 없는 장소는 넣지 않는다."""
    by_id = {p["id"]: p for p in places}
    city_name = {c["id"]: (c.get("n") or {}).get("ko") or (c.get("n") or {}).get("es") or (c.get("n") or {}).get("local") for c in cities}
    out, cur, chars = [], [], 0
    for i in ids:
        p, b = by_id.get(i), bundles.get(i) or []
        if not p or not any(s["kind"] in ("wikivoyage", "wikipedia") for s in b):
            continue
        srcs = [{"kind": s["kind"], "lang": s["lang"], "title": s["title"], "text": s["text"][:CHUNK_TEXT_MAX] + (" …(뒤 생략)" if len(s["text"]) > CHUNK_TEXT_MAX else "")} for s in b]
        n = sum(len(s["text"]) for s in srcs)
        if cur and (len(cur) >= size or chars + n > CHUNK_CHARS_MAX):
            out.append(cur); cur, chars = [], 0
        names = {k: v for k, v in (p.get("n") or {}).items() if v and k != "ko_src"}
        cur.append({"id": i, "names": names, "name_ko_needed": not names.get("ko"), "cat": p.get("cat"), "city": city_name.get(p.get("city")),
                    "heritage": sorted({HERITAGE[h] for h in p.get("her") or [] if h in HERITAGE}), "src_md5": source_md5(b), "sources": srcs})
        chars += n
    if cur:
        out.append(cur)
    return out


def check_part(records, chunk, skipped=()):
    """한 묶음의 생성 결과 검사. 문제 목록 [(장소 ID, 문구)]를 돌려준다. 비어 있으면 통과."""
    want = {c["id"]: c for c in chunk}
    out, seen = [], set()
    for r in records:
        i = r.get("id")
        if i not in want:
            out.append((i, "묶음에 없는 장소")); continue
        if i in seen:
            out.append((i, "같은 장소가 두 번 나옴")); continue
        seen.add(i)
        c = want[i]
        out += [(i, m) for m in validate(r)]
        if r.get("src_md5") != c["src_md5"]:
            out.append((i, "src_md5가 묶음의 값과 다름"))
        if c["name_ko_needed"] and not (r.get("name_ko") or "").strip():
            out.append((i, "한글 이름 없음"))
        if not c["name_ko_needed"] and r.get("name_ko"):
            out.append((i, "한국어 이름이 이미 있는 장소인데 name_ko를 적음(null이어야 함)"))
        name = c["names"].get("ko") or (r.get("name_ko") or "")
        if name and not (r.get("summary_ko") or "").startswith(name):
            out.append((i, f"요약이 장소 이름({name})으로 시작하지 않음"))
        text = (r.get("summary_ko") or "") + (r.get("detail_ko") or "")
        if text.count("(") != text.count(")"):
            out.append((i, "괄호 짝이 맞지 않음"))
        if "  " in text or "\t" in text:
            out.append((i, "공백이 겹치거나 탭이 있음"))
    out += [(i, "결과가 없음(만들거나 skipped에 사유를 적어야 함)") for i in want if i not in seen and i not in set(skipped)]
    return out


def merge_parts(content, parts):
    """내용 목록 뒤에 부분 파일들의 새 장소를 붙인다. 이미 있는 장소는 건드리지 않는다. parts: [(파일 이름, 레코드 목록)] 이름순."""
    have = {r["id"] for r in content}
    out, added = list(content), 0
    for _, rows in sorted(parts, key=lambda x: x[0]):
        for r in rows:
            if r["id"] not in have:
                have.add(r["id"]); out.append(r); added += 1
    return out, added


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
    extracts = load_extracts(extracts_path)
    bundles = {p["id"]: source_bundle(p, wv_text, extracts) for p in places if p["id"] in idset}
    return places, bundles


def load_extracts(extracts_path):
    """{(lang, title): 머리 문단}. 문서가 없던 제목은 빈 문자열로 들어 있다(출처 묶음에는 쓰이지 않는다)."""
    extracts = {}
    if extracts_path and pathlib.Path(extracts_path).exists():
        for l in open(extracts_path, encoding="utf-8"):
            if l.strip():
                r = json.loads(l); extracts[(r["lang"], r["title"])] = r["extract"]
    return extracts


def write_gz(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as f:  # 같은 입력에 같은 바이트
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump"); [d.add_argument(x) for x in ("ids", "places", "sources", "extracts", "out")]
    b = sub.add_parser("build"); [b.add_argument(x) for x in ("content", "places", "sources", "extracts")]; b.add_argument("--out", required=True); b.add_argument("--stamp", action="store_true")
    c = sub.add_parser("chunks"); [c.add_argument(x) for x in ("ids", "places", "cities", "sources", "extracts", "out")]; c.add_argument("--size", type=int, default=40)
    c.add_argument("--ready-only", action="store_true"); c.add_argument("--limit", type=int, default=0)
    k = sub.add_parser("check"); [k.add_argument(x) for x in ("part", "chunk")]
    m = sub.add_parser("merge"); [m.add_argument(x) for x in ("content", "parts")]
    a = ap.parse_args()
    if a.cmd == "chunks":
        raw = json.load(open(a.ids, encoding="utf-8")); ids = [x["id"] if isinstance(x, dict) else x for x in raw]
        out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
        old = sorted(out.glob("chunk_*.json"))
        taken = {c["id"] for f in old for c in json.load(open(f, encoding="utf-8"))}
        start = max([int(f.stem.split("_")[1]) for f in old], default=0)
        todo = [i for i in ids if i not in taken]
        if a.ready_only:
            fetched = set(load_extracts(a.extracts)); by_id = {p["id"]: p for p in json.load(gzip.open(a.places, "rt", encoding="utf-8"))}
            todo = [i for i in todo if i in by_id and is_ready(by_id[i], fetched)]
        if a.limit:
            todo = todo[:a.limit]
        places, bundles = load_inputs(a.places, a.sources, a.extracts, todo)
        chunks = make_chunks(todo, places, json.load(gzip.open(a.cities, "rt", encoding="utf-8")), bundles, a.size)
        for n, ch in enumerate(chunks, start + 1):
            (out / f"chunk_{n:03d}.json").write_text(json.dumps(ch, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"새 묶음 {len(chunks)}개(chunk_{start + 1:03d}부터, 장소 {sum(len(x) for x in chunks)}곳). 이미 묶인 {len(taken)}곳, 아직 준비 안 됐거나 남은 {len(ids) - len(taken) - sum(len(x) for x in chunks)}곳 → {out}"); return
    if a.cmd == "check":
        rows = [json.loads(l) for l in open(a.part, encoding="utf-8") if l.strip()]
        chunk = json.load(open(a.chunk, encoding="utf-8"))
        sk = pathlib.Path(a.part.replace(".jsonl", ".skipped.json"))
        skipped = [x["id"] for x in json.load(open(sk, encoding="utf-8"))] if sk.exists() else []
        problems = check_part(rows, chunk, skipped)
        for i, msg in problems:
            print(f"  {i}: {msg}")
        print(f"검사: 장소 {len(rows)}곳(묶음 {len(chunk)}곳, 건너뜀 {len(skipped)}곳), 문제 {len(problems)}건")
        sys.exit(1 if problems else 0)
    if a.cmd == "merge":
        cp = pathlib.Path(a.content)
        content = [json.loads(l) for l in open(cp, encoding="utf-8") if l.strip()] if cp.exists() else []
        parts = [(f.name, [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]) for f in sorted(pathlib.Path(a.parts).glob("*.jsonl"))]
        merged, added = merge_parts(content, parts)
        with open(cp, "w", encoding="utf-8") as f:
            for r in merged:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"부분 파일 {len(parts)}개에서 {added}곳을 붙였다. 내용 파일 {len(merged)}곳 → {cp}"); return
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
