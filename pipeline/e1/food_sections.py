#!/usr/bin/env python3
"""E1 보조: 영문 가이드에 대표 음식이 없는 여행지의 음식 관련 절을 다른 출처에서 받는다(E5 4절 12항, D-062).

- 출처와 순서: 스페인어 위키백과 도시 문서의 요리 절(제목에 낱말 "gastronomía"나 "cocina"가 있는 절), 스페인어 위키보이지 문서의 먹거리 절(제목의 첫 낱말이 "Comer").
- 대상: 여행지(dest가 있는 지자체·섬) 가운데, --skip으로 준 대표 음식 내용 파일에 영문 가이드 출처(src 없음 또는 "wv_en") 줄이 있는 곳을 뺀 전부.
- 호출: 각 사이트의 API(action=query, prop=revisions, rvslots=main)로 문서 원문을 묶음으로 받아 절을 잘라 낸다. 식별 UA, 요청 사이 3초,
  429를 받으면 Retry-After만큼 쉰다. 결과는 저장소에 넣지 않는다(D-016).
- 출력 JSONL(id, src 순): {id, src("eswiki"|"esvoy"), title, section, revid, text}. 절이 없는 문서는 적지 않는다. text는 틀·참조·표를 뺀 줄글이다.
실행: python -I pipeline/run.py e1.food_sections <cities.json.gz> <출력 JSONL> [--skip <대표 음식 JSONL>]
순수 함수(find_section, clean_title, section_plain, targets, parse_revisions)는 네트워크를 모른다. 테스트는 pipeline/tests/test_e1.py.
"""
import argparse
import gzip
import json
import re
import time
import unicodedata

from .wikivoyage import plain

UA = "place-data-pipeline/0.1 (batch; 1 req/s)"
BATCH = 5          # 도시 문서는 원문이 커서 작은 묶음으로 받는다
DELAY = 3.0
TEXT_LIMIT = 8000  # 영문 가이드의 먹거리 절과 같은 한도(E1 wikivoyage.EAT_LIMIT)
SOURCES = {
    "eswiki": {"host": "es.wikipedia.org", "words": ("gastronomia", "cocina"), "first": False},
    "esvoy": {"host": "es.wikivoyage.org", "words": ("comer",), "first": True},
}
HEAD_RE = re.compile(r"^(={2,6})[ \t]*(.+?)[ \t]*\1[ \t]*$", re.M)
TABLE_RE = re.compile(r"\{\|.*?\|\}", re.S)
GALLERY_RE = re.compile(r"<gallery[^>]*>.*?</gallery>", re.S | re.I)


REF_RE = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", re.S | re.I)


def clean_title(s):
    """절 제목에서 참조와 틀, 태그, 굵은 글씨 표시를 뺀다"""
    return re.sub(r"\{\{[^{}]*\}\}|<[^>]+>|\[\d+\]|'{2,}|​", "", REF_RE.sub("", s or "")).strip()


def norm(s):
    """절 제목 견주기용: 참조와 태그를 빼고 소문자, 악센트 없이"""
    return unicodedata.normalize("NFD", clean_title(s).casefold()).encode("ascii", "ignore").decode().strip()


def find_section(wikitext, words, first=False):
    """제목에 words 가운데 하나가 낱말로 있는(first면 첫 낱말인) 첫 절의 (제목, 본문 원문). 없으면 None.
    낱말로 견주므로 "certámenes gastronómicos"나 "Comercio"는 잡지 않는다.
    본문은 그 절의 하위 절을 포함하고, 같은 수준이나 더 높은 수준의 다음 제목 앞에서 끝난다."""
    heads = [(m.start(), m.end(), len(m.group(1)), m.group(2)) for m in HEAD_RE.finditer(wikitext)]
    for i, (_, end, level, title) in enumerate(heads):
        ws = re.findall(r"[a-z0-9]+", norm(title))
        if any(w in words for w in (ws[:1] if first else ws)):
            stop = next((s for s, _, lv, _ in heads[i + 1:] if lv <= level), len(wikitext))
            return clean_title(title), wikitext[end:stop]
    return None


def section_plain(body, limit=TEXT_LIMIT):
    """절 원문 → 줄글. 표와 사진 모음을 먼저 빼고 가이드와 같은 정리를 한다."""
    return plain(GALLERY_RE.sub("", TABLE_RE.sub("", body)), limit)


def targets(cities, skip_ids=()):
    """[(id, {src: 문서 제목})] 대상 여행지와 출처별 문서 제목. ID 순."""
    skip, out = set(skip_ids), []
    for c in sorted(cities, key=lambda c: c["id"]):
        if not c.get("dest") or c["id"] in skip:
            continue
        n, w = c.get("n") or {}, c.get("wiki") or {}
        titles = {"eswiki": w.get("es"), "esvoy": n.get("es") or w.get("es")}
        out.append((c["id"], {k: v for k, v in titles.items() if v}))
    return out


def parse_revisions(data):
    """API 응답 → {요청한 제목: (실제 제목, revid, 원문)}. 정규화·넘겨주기로 바뀐 제목을 요청 제목으로 되돌린다. 없는 문서는 빠진다."""
    q = data.get("query") or {}
    back = {}
    for m in (q.get("normalized") or []) + (q.get("redirects") or []):
        back[m["to"]] = back.get(m["from"], m["from"])
    out = {}
    for page in (q.get("pages") or {}).values():
        revs = page.get("revisions") or []
        if not revs:
            continue
        text = ((revs[0].get("slots") or {}).get("main") or {}).get("*")
        if text is None:
            continue
        t = page["title"]
        while t in back and back[t] != t:
            t = back[t]
        out[t] = (page["title"], revs[0].get("revid"), text)
    return out


def fetch(host, titles):
    """{요청한 제목: (실제 제목, revid, 원문)}"""
    import requests
    out = {}
    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        for _ in range(40):
            r = requests.get(f"https://{host}/w/api.php", headers={"User-Agent": UA}, timeout=120,
                             params={"action": "query", "prop": "revisions", "rvprop": "ids|content", "rvslots": "main", "redirects": 1, "titles": "|".join(chunk), "format": "json"})
            if r.status_code != 429:
                break
            time.sleep(min(int(r.headers.get("Retry-After") or 30), 300))
        r.raise_for_status()
        out.update(parse_revisions(r.json()))
        print(f"  {host}: {min(i + BATCH, len(titles))}/{len(titles)}", flush=True)
        time.sleep(DELAY)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cities"); ap.add_argument("out"); ap.add_argument("--skip")
    a = ap.parse_args()
    cities = json.load(gzip.open(a.cities, "rt", encoding="utf-8"))
    skip = [r["id"] for r in (json.loads(l) for l in open(a.skip, encoding="utf-8") if l.strip()) if (r.get("src") or "wv_en") == "wv_en"] if a.skip else []
    want = targets(cities, skip)
    rows = []
    for src, spec in SOURCES.items():
        titles = sorted({t[src] for _, t in want if src in t})
        got = fetch(spec["host"], titles)
        hit = 0
        for cid, t in want:
            page = got.get(t.get(src))
            sec = find_section(page[2], spec["words"], spec["first"]) if page else None
            text = section_plain(sec[1]) if sec else ""
            if text:
                rows.append({"id": cid, "src": src, "title": page[0], "section": sec[0], "revid": page[1], "text": text}); hit += 1
        print(f"  {src}: 대상 {len(want)}곳, 문서 {len(got)}건, 절 있음 {hit}곳", flush=True)
    rows.sort(key=lambda r: (r["id"], r["src"]))
    with open(a.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"끝: {len(rows)}줄 → {a.out}")


if __name__ == "__main__":
    main()
