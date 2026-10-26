#!/usr/bin/env python3
"""2단계 PoC B 단계: Wikivoyage 덤프에서 특정 국가 하위 문서와 목록(listing)을 추출한다.

- 문서 계층은 {{IsPartOf|상위}} 템플릿으로 복원하고 루트(예: Spain)에서 내려간다.
- 목록은 {{see}}, {{do}}, {{buy}}, {{eat}}, {{drink}}, {{sleep}}, {{go}}, {{listing}}, {{marker}} 템플릿이다.
- 출력: pages.jsonl(문서), listings.jsonl(목록), summary.json(요약). 원문은 저장하지 않는다.

실행: python -I poc/wikivoyage_parse.py <덤프.bz2> <루트 문서 제목> <출력 디렉터리> [언어 en|es]
언어별 템플릿과 매개변수 이름은 LANG 설정에 있다. 스페인어판은 {{estáEn}}, {{ver}}, {{dormir}}, {{listado}} 등을 쓴다.
"""
import bz2
import collections
import json
import pathlib
import re
import sys
import time
import xml.etree.ElementTree as ET

LISTING_NAMES = {"see", "do", "buy", "eat", "drink", "sleep", "go", "listing", "marker"}
LANG = {
    "en": {"ispartof": r"\{\{\s*[Ii]s[Pp]art[Oo]f\s*\|\s*([^}|]+)", "names": {}, "aliases": {},
           "status": None,
           "sections": {"understand": ("understand",), "sleep": ("sleep",), "eat": ("eat",), "get_around": ("get around",), "get_in": ("get in",)},
           "tiers": ("budget", "mid-range", "splurge")},
    "es": {"ispartof": r"\{\{\s*[Ee]st[áa][Ee]n\s*\|\s*([^}|]+)",
           "names": {"ver": "see", "hacer": "do", "comprar": "buy", "comer": "eat", "beber": "drink", "dormir": "sleep", "listado": "listing", "marcador": "marker", "ir": "go"},
           "aliases": {"nombre": "name", "dirección": "address", "direccion": "address", "indicaciones": "directions", "tlf": "phone",
                       "tlf_gratuito": "tollfree", "precio": "price", "horario": "hours", "descripción": "content", "descripcion": "content",
                       "imagen": "image", "hora_entrada": "checkin", "hora_salida": "checkout", "tipo": "type"},
           "status": re.compile(r"\{\{\s*estado art[íi]culo\s*\|([^}]*)\}\}", re.I),
           "sections": {"understand": ("comprender", "entender"), "sleep": ("dormir",), "eat": ("comer",), "get_around": ("desplazarse", "cómo desplazarse", "moverse"), "get_in": ("llegar", "cómo llegar")},
           "tiers": ("económico", "economico", "barato", "medio", "precio medio", "lujo", "caro")},
}
CFG = LANG["en"]
FIELDS = ["name", "alt", "url", "email", "address", "lat", "long", "directions", "phone", "tollfree",
          "hours", "price", "lastedit", "wikidata", "wikipedia", "image", "content", "checkin", "checkout"]
STATUS_RE = re.compile(r"\{\{\s*(outline|usable|guide|star|stub)\s*(city|region|district|park|itinerary|topic|airport|diveguide|phrasebook|country|continent)\s*\}\}", re.I)
BOOKING_RE = re.compile(r"\b(book(ed|ing)?|reserv|in advance|advance (booking|purchase|ticket)|reserva|antelaci[oó]n)", re.I)
PRICE_NUM_RE = re.compile(r"(€|\beur\b|\d)", re.I)
H2_RE = re.compile(r"^==\s*([^=].*?)\s*==\s*$", re.M)
H3_RE = re.compile(r"^===\s*([^=].*?)\s*===\s*$", re.M)


def norm_title(t):
    t = t.replace("_", " ").strip()
    return t[:1].upper() + t[1:] if t else t


def iter_pages(path):
    with bz2.open(path, "rb") as f:
        for _, elem in ET.iterparse(f, events=("end",)):
            if elem.tag.split("}")[-1] != "page":
                continue
            ns = elem.findtext("{*}ns")
            title = elem.findtext("{*}title") or ""
            redirect = elem.find("{*}redirect") is not None
            text = ""
            rev = elem.find("{*}revision")
            if rev is not None:
                text = rev.findtext("{*}text") or ""
            yield ns, title, redirect, text
            elem.clear()


def page_status(text):
    """(상태, 종류). 영문은 {{usablecity}}류, 스페인어는 {{estado artículo|tipo=|calidad=}}."""
    if CFG["status"] is None:
        m = STATUS_RE.search(text)
        return (m.group(1).lower(), m.group(2).lower()) if m else ("", "unknown")
    m = CFG["status"].search(text)
    if not m:
        return ("", "unknown")
    kv = dict((k.strip().lower(), v.strip().lower()) for k, v in (p.split("=", 1) for p in m.group(1).split("|") if "=" in p))
    kind_map = {"ciudad": "city", "región": "region", "region": "region", "distrito": "district", "parque": "park", "país": "country", "pais": "country",
                "itinerario": "itinerary", "tema": "topic", "aeropuerto": "airport", "continente": "continent"}
    return (kv.get("calidad", ""), kind_map.get(kv.get("tipo", ""), kv.get("tipo", "unknown") or "unknown"))


def find_templates(text):
    """최상위 템플릿 본문(이름 포함)을 순서대로 내놓는다. 중첩 템플릿은 상위 안에 포함된다."""
    i, n = 0, len(text)
    while True:
        s = text.find("{{", i)
        if s < 0:
            return
        depth, j = 0, s
        while j < n:
            if text.startswith("{{", j):
                depth += 1
                j += 2
            elif text.startswith("}}", j):
                depth -= 1
                j += 2
                if depth == 0:
                    break
            else:
                j += 1
        if depth != 0:
            return
        yield text[s + 2:j - 2]
        i = j


def split_params(inner):
    parts, depth_t, depth_l, cur = [], 0, 0, []
    i, n = 0, len(inner)
    while i < n:
        two = inner[i:i + 2]
        if two == "{{":
            depth_t += 1; cur.append(two); i += 2; continue
        if two == "}}":
            depth_t -= 1; cur.append(two); i += 2; continue
        if two == "[[":
            depth_l += 1; cur.append(two); i += 2; continue
        if two == "]]":
            depth_l -= 1; cur.append(two); i += 2; continue
        if inner[i] == "|" and depth_t == 0 and depth_l == 0:
            parts.append("".join(cur)); cur = []; i += 1; continue
        cur.append(inner[i]); i += 1
    parts.append("".join(cur))
    return parts


def parse_listing(inner):
    parts = split_params(inner)
    name = parts[0].strip().lower()
    name = CFG["names"].get(name, name)
    if name not in LISTING_NAMES:
        return None
    params = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            k = k.strip().lower()
            params[CFG["aliases"].get(k, k)] = v.strip()
    raw_type = params.get("type", "").strip().lower()
    if name == "listing":
        mapped = CFG["names"].get(raw_type, raw_type)
        ltype = mapped if mapped in LISTING_NAMES - {"listing", "marker"} else "listing"
    else:
        ltype = name
    params["_raw_type"] = raw_type
    return ltype, params


def sections(text):
    h2 = [(m.start(), m.group(1).strip()) for m in H2_RE.finditer(text)]
    out = {}
    for idx, (pos, title) in enumerate(h2):
        end = h2[idx + 1][0] if idx + 1 < len(h2) else len(text)
        body = text[pos:end]
        out[title] = {"len": len(body), "h3": [m.group(1).strip() for m in H3_RE.finditer(body)]}
    return out


def main():
    global CFG
    dump, root, outdir = sys.argv[1], norm_title(sys.argv[2]), pathlib.Path(sys.argv[3])
    CFG = LANG[sys.argv[4] if len(sys.argv) > 4 else "en"]
    ispartof_re = re.compile(CFG["ispartof"])
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    texts, parents, redirects = {}, {}, {}
    n_all = 0
    for ns, title, redirect, text in iter_pages(dump):
        if ns != "0":
            continue
        n_all += 1
        if redirect:
            redirects[title] = True
            continue
        texts[title] = text
        m = ispartof_re.search(text)
        if m:
            parents[title] = norm_title(m.group(1))
    print(f"  ns0 문서 {n_all}건, 본문 보유 {len(texts)}건, 리다이렉트 {len(redirects)}건 ({round(time.time()-t0)}초)")
    children = collections.defaultdict(list)
    for child, parent in parents.items():
        children[parent].append(child)
    # 루트에서 BFS
    order, depth = [], {root: 0}
    queue = [root]
    while queue:
        cur = queue.pop(0)
        order.append(cur)
        for ch in children.get(cur, []):
            if ch not in depth:
                depth[ch] = depth[cur] + 1
                queue.append(ch)
    print(f"  '{root}' 하위 문서 {len(order)}건 (본문 없는 참조 포함)")

    kinds = collections.Counter()
    ltype_counter = collections.Counter()
    field_cov = collections.defaultdict(collections.Counter)
    flags = collections.defaultdict(collections.Counter)
    pages_out = open(outdir / "pages.jsonl", "w", encoding="utf-8")
    list_out = open(outdir / "listings.jsonl", "w", encoding="utf-8")
    n_pages_with_text = 0
    sec_stats = collections.Counter()
    for title in order:
        text = texts.get(title)
        if text is None:
            continue
        n_pages_with_text += 1
        status, kind = page_status(text)
        kinds[kind] += 1
        secs = sections(text)
        sec_names = CFG["sections"]
        def find_sec(key):
            return next((v for k, v in secs.items() if any(k.lower().startswith(n) for n in sec_names[key])), None)
        understand, sleep, eat = find_sec("understand"), find_sec("sleep"), find_sec("eat")
        getaround, getin = find_sec("get_around") is not None, find_sec("get_in") is not None
        tiers = CFG["tiers"]
        if understand: sec_stats["understand"] += 1
        if sleep: sec_stats["sleep"] += 1
        if sleep and any(h.lower() in tiers for h in sleep["h3"]): sec_stats["sleep_tiers"] += 1
        if eat: sec_stats["eat"] += 1
        if eat and any(h.lower() in tiers for h in eat["h3"]): sec_stats["eat_tiers"] += 1
        if getaround: sec_stats["get_around"] += 1
        if getin: sec_stats["get_in"] += 1
        counts = collections.Counter()
        for inner in find_templates(text):
            parsed = parse_listing(inner)
            if not parsed:
                continue
            ltype, params = parsed
            counts[ltype] += 1
            ltype_counter[ltype] += 1
            present = {f: bool(params.get(f)) for f in FIELDS}
            for f, ok in present.items():
                if ok:
                    field_cov[ltype][f] += 1
            has_coords = present["lat"] and present["long"]
            content = params.get("content", "")
            booking = bool(BOOKING_RE.search(content + " " + params.get("hours", "") + " " + params.get("price", "")))
            price_num = bool(params.get("price")) and bool(PRICE_NUM_RE.search(params.get("price", "")))
            for k, v in (("coords", has_coords), ("booking_text", booking), ("price_numeric", price_num)):
                if v:
                    flags[ltype][k] += 1
            list_out.write(json.dumps({"page": title, "type": ltype, "raw_type": params.get("_raw_type") or None, "name": params.get("name", "")[:120],
                                       "wikidata": params.get("wikidata") or None, "has_coords": has_coords,
                                       "has_price": present["price"], "price_numeric": price_num, "has_hours": present["hours"],
                                       "booking_text": booking, "content_len": len(content), "lat": params.get("lat"), "long": params.get("long")},
                                      ensure_ascii=False) + "\n")
        pages_out.write(json.dumps({"title": title, "kind": kind, "status": status, "parent": parents.get(title), "depth": depth.get(title),
                                    "text_len": len(text), "listings": dict(counts), "understand_len": understand["len"] if understand else 0,
                                    "sleep_tiers": bool(sleep and sleep["h3"]), "get_around": getaround, "get_in": getin}, ensure_ascii=False) + "\n")
    pages_out.close(); list_out.close()
    total_l = sum(ltype_counter.values())
    summary = {
        "dump": pathlib.Path(dump).name, "root": root, "parsed_at": time.strftime("%Y-%m-%d %H:%M"), "seconds": round(time.time() - t0),
        "ns0_pages": n_all, "subtree_pages": len(order), "subtree_pages_with_text": n_pages_with_text,
        "pages_by_kind": dict(kinds), "sections": dict(sec_stats),
        "listings_total": total_l, "listings_by_type": dict(ltype_counter),
        "field_coverage_pct": {t: {f: round(100 * field_cov[t][f] / ltype_counter[t], 1) for f in FIELDS} for t in ltype_counter},
        "flags_pct": {t: {k: round(100 * flags[t][k] / ltype_counter[t], 1) for k in ("coords", "booking_text", "price_numeric")} for t in ltype_counter},
    }
    json.dump(summary, open(outdir / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  목록 {total_l}건: {dict(ltype_counter)}")
    print(f"  문서 종류: {dict(kinds)}")
    print(f"  절 통계: {dict(sec_stats)}")


if __name__ == "__main__":
    main()
