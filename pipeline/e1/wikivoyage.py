"""Wikivoyage 덤프에서 스페인 하위 문서와 목록을 전체 필드로 추출한다 (E1 2절). PoC의 poc/wikivoyage_parse.py를 재사용한다.

출력: pages.jsonl {lang, title, kind, parent, depth, understand, sleep_tiers, eat_tiers}
      listings.jsonl {lang, page, idx, type, raw_type, section, tier, name, alt, lat, lon, wikidata, content, price, hours, url, phone, address}
실행: python -I -m pipeline.e1.wikivoyage <lang> <덤프.bz2> <출력 디렉터리>
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "poc"))
import wikivoyage_parse as W  # noqa: E402

TIER_WORDS = {"budget": "저가", "mid-range": "중가", "splurge": "고가", "económico": "저가", "medio": "중가", "lujo": "고가", "barato": "저가", "caro": "고가"}
UNDERSTAND = {"en": ("understand",), "es": ("comprender", "entender")}
FILE_RE = re.compile(r"\[\[(?:File|Image|Archivo|Imagen|Fichero):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]", re.I)
LINK_RE = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")
TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
REF_RE = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
BOLD_RE = re.compile(r"'{2,}")


def plain(wikitext, limit=4000):
    """위키텍스트를 읽을 수 있는 평문으로. 템플릿·참조·태그 제거, 링크는 표시 글자만."""
    t = REF_RE.sub("", wikitext)
    t = FILE_RE.sub("", t)
    for _ in range(3):
        t = TEMPLATE_RE.sub("", t)
    t = LINK_RE.sub(r"\1", t)
    t = TAG_RE.sub("", t)
    t = BOLD_RE.sub("", t)
    t = re.sub(r"^=+\s*(.*?)\s*=+\s*$", r"\1.", t, flags=re.M)  # 소제목은 문장처럼 마침표로 끝낸다
    t = re.sub(r"^[*#:;]+\s*", "", t, flags=re.M)
    t = re.sub(r"\n{2,}", "\n", t).strip()
    return t[:limit]


def section_text(text, names):
    h2 = [(m.start(), m.end(), m.group(1).strip().lower()) for m in W.H2_RE.finditer(text)] + [(len(text), len(text), "")]
    for (a, e, n), (b, _, _) in zip(h2, h2[1:]):
        if n in names:
            return text[e:b]
    return ""


def clean_name(s):
    s = LINK_RE.sub(r"\1", s or "")
    s = BOLD_RE.sub("", s)
    return TAG_RE.sub("", s).strip()


def parse_coord(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def main():
    lang, dump, out = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    W.CFG = W.LANG[lang]
    ispartof_re = re.compile(W.CFG["ispartof"])
    root = W.CFG.get("root", "Spain" if lang == "en" else "España")
    texts, parents = {}, {}
    for ns, title, redirect, text in W.iter_pages(dump):
        if ns != "0" or redirect:
            continue
        texts[title] = text
        m = ispartof_re.search(text)
        if m:
            parents[title] = W.norm_title(m.group(1))
    children = {}
    for c, p in parents.items():
        children.setdefault(p, []).append(c)
    order, depth, queue, seen = [], {root: 0}, [root], {root}
    while queue:
        cur = queue.pop(0); order.append(cur)
        for ch in children.get(cur, []):
            if ch not in seen:
                seen.add(ch); depth[ch] = depth[cur] + 1; queue.append(ch)
    n_pages = n_list = 0
    with open(out / "pages.jsonl", "w", encoding="utf-8") as fp, open(out / "listings.jsonl", "w", encoding="utf-8") as fl:
        for title in order:
            text = texts.get(title)
            if text is None:
                continue
            kind = (W.page_status(text) or ("", ""))[1] if hasattr(W, "page_status") else ""
            und = plain(section_text(text, UNDERSTAND[lang]))
            h2 = [(m.start(), m.group(1).strip().lower()) for m in W.H2_RE.finditer(text)]
            h3 = [(m.start(), m.group(1).strip().lower()) for m in W.H3_RE.finditer(text)]
            tiers = {"sleep": False, "eat": False}
            pos = idx = 0
            for inner in W.find_templates(text):
                at = text.find("{{" + inner[:40], pos)
                if at >= 0:
                    pos = at
                parsed = W.parse_listing(inner)
                if not parsed:
                    continue
                ltype, params = parsed
                sec = next((n for p, n in reversed(h2) if p <= at), "")
                sec_start = max([p for p, _ in h2 if p <= at] or [0])
                sub = next((n for p, n in reversed(h3) if sec_start < p <= at), "")
                tier = next((v for k, v in TIER_WORDS.items() if k in sub), None)
                if tier and ltype in tiers:
                    tiers[ltype] = True
                rec = {"lang": lang, "page": title, "idx": idx, "type": ltype, "raw_type": (params.get("type") or "").strip().lower(), "section": sec, "tier": tier,
                       "name": clean_name(params.get("name")), "alt": clean_name(params.get("alt")), "lat": parse_coord(params.get("lat")), "lon": parse_coord(params.get("long")),
                       "wikidata": (params.get("wikidata") or "").strip() or None, "content": plain(params.get("content") or "", 2000), "price": clean_name(params.get("price")) or None,
                       "hours": clean_name(params.get("hours")) or None, "url": (params.get("url") or "").strip() or None, "phone": (params.get("phone") or "").strip() or None,
                       "address": clean_name(params.get("address")) or None}
                if rec["name"]:
                    fl.write(json.dumps(rec, ensure_ascii=False) + "\n"); n_list += 1; idx += 1
            fp.write(json.dumps({"lang": lang, "title": title, "kind": kind, "parent": parents.get(title), "depth": depth.get(title, 0), "understand": und, "sleep_tiers": tiers["sleep"], "eat_tiers": tiers["eat"]}, ensure_ascii=False) + "\n")
            n_pages += 1
    print(f"  {lang}: 문서 {n_pages}건, 목록 {n_list}건 → {out}", flush=True)


if __name__ == "__main__":
    main()
