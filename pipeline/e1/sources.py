"""소스별 원시 파일을 공통 레코드로 읽는다 (E1 4절 2항 정규화)."""
import glob
import json
import pathlib
import re
import unicodedata

from . import config as C

POINT_RE = re.compile(r"Point\(([-\d.]+) ([-\d.]+)\)")


def norm_text(s):
    if not s:
        return None
    s = unicodedata.normalize("NFC", str(s))
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def parse_point(s):
    m = POINT_RE.match(s or "")
    return (round(float(m.group(2)), 6), round(float(m.group(1)), 6)) if m else None


def load_wikidata(wd_dir, labels_path=None, mul_path=None):
    """클래스 파일 + 유산 지정 + 사이트링크·라벨 조회 결과를 QID별 하나로 합친다.
    mul_path(e1.wikidata_mul의 출력)를 주면 스페인어·영어 라벨이 없는 항목을 공통 라벨(mul)로 채운다(E1 4절 1항, D-066)."""
    items = {}
    for f in sorted(glob.glob(f"{wd_dir}/Q*.jsonl")):
        cls = pathlib.Path(f).stem
        for line in open(f, encoding="utf-8"):
            r = json.loads(line); q = r["qid"]
            it = items.setdefault(q, {"qid": q, "classes": set(), "coord": None, "pop": None, "sitelinks": 0, "p131": None, "labels": {}, "desc": {}, "wiki": {}, "heritage": [], "wv_en": None})
            it["classes"].add(cls)
            it["coord"] = it["coord"] or parse_point(r.get("coord"))
            if r.get("pop"):
                try: it["pop"] = int(float(r["pop"]))
                except ValueError: pass
            try: it["sitelinks"] = max(it["sitelinks"], int(r.get("sitelinks") or 0))
            except ValueError: pass
            it["p131"] = it["p131"] or r.get("p131")
            for l in ("es", "en", "ko"):
                if r.get(f"label_{l}") and not it["labels"].get(l):
                    it["labels"][l] = norm_text(r[f"label_{l}"])
            if r.get("wv_en") and r["wv_en"] is not False:
                it["wv_en"] = r["wv_en"] if isinstance(r["wv_en"], str) else it["wv_en"]
    for line in open(f"{wd_dir}/P1435.jsonl", encoding="utf-8"):
        r = json.loads(line); q = r["qid"]
        it = items.setdefault(q, {"qid": q, "classes": set(), "coord": None, "pop": None, "sitelinks": 0, "p131": None, "labels": {}, "desc": {}, "wiki": {}, "heritage": [], "wv_en": None})
        it["coord"] = it["coord"] or parse_point(r.get("coord"))
        try: it["sitelinks"] = max(it["sitelinks"], int(r.get("sitelinks") or 0))
        except ValueError: pass
        it["heritage"] = sorted(set(it["heritage"]) | set(r.get("designations") or []))
    for path in [f"{wd_dir}/sitelinks.jsonl"] + ([labels_path] if labels_path and pathlib.Path(labels_path).exists() else []):
        for line in open(path, encoding="utf-8"):
            r = json.loads(line); it = items.get(r["qid"])
            if not it or r.get("missing"):
                continue
            for l in ("es", "en", "ko", "ca", "eu", "gl"):
                if r.get(f"label_{l}"):
                    it["labels"][l] = norm_text(r[f"label_{l}"])
            for l in ("es", "en", "ko"):
                if r.get(f"desc_{l}"):
                    it["desc"][l] = norm_text(r[f"desc_{l}"])
                if r.get(f"{l}wiki"):
                    it["wiki"][l] = r[f"{l}wiki"]
            if r.get("sitelinks") is not None and str(r["sitelinks"]).isdigit():
                it["sitelinks"] = max(it["sitelinks"], int(r["sitelinks"]))
            if r.get("wv_en"):
                it["wv_en"] = r["wv_en"]
    if mul_path and pathlib.Path(mul_path).exists():
        for line in open(mul_path, encoding="utf-8"):
            r = json.loads(line); it = items.get(r["qid"])
            fill_mul(it["labels"] if it else None, r.get("label_mul"))
    return items


def fill_mul(labels, mul):
    """라벨 사전의 스페인어·영어 빈칸을 공통 라벨로 채운다. 이미 있는 라벨은 건드리지 않는다. Wikidata는 언어마다 같은 라벨을 공통 라벨(mul) 하나로 합치고 있다."""
    mul = norm_text(mul)
    if labels is None or not mul:
        return labels
    for l in ("es", "en"):
        if not labels.get(l):
            labels[l] = mul
    return labels


OSM_KEEP_FIELDS = ("name", "name:es", "name:en", "name:ko", "name:ca", "name:eu", "name:gl", "wikidata", "wikipedia", "opening_hours", "fee", "charge", "website", "phone", "cuisine", "description", "population", "reservation", "addr:city")


def iter_osm(paths):
    """추출 결과 파일 여러 개를 순서대로 읽는다. 같은 OSM ID는 먼저 나온 것만 쓴다(추출본 경계에 걸친 객체가 양쪽에 들어 있다)."""
    seen = set()
    for path in ([paths] if isinstance(paths, (str, pathlib.Path)) else list(paths)):
        for line in open(path, encoding="utf-8"):
            o = json.loads(line)
            if o["id"] in seen:
                continue
            seen.add(o["id"])
            yield o


def load_osm(pois_paths):
    """OSM 장소를 장소·정착지·구역·교통·공항으로 나눈다. pois_paths는 파일 하나 또는 여러 개(스페인 추출본 + 카나리아 추출본, D-031)."""
    places, settlements, districts, transit, airports = [], [], [], [], []
    for o in iter_osm(pois_paths):
        key, val = o["key"], o["value"]
        rec = {"id": o["id"], "lat": round(float(o["lat"]), 6), "lon": round(float(o["lon"]), 6), "key": key, "value": val}
        for f in OSM_KEEP_FIELDS:
            if o.get(f):
                rec[f] = norm_text(o[f])
        if key == "place" and val in C.OSM_SETTLEMENT:
            settlements.append(rec)
        elif key == "place" and val in C.OSM_DISTRICT:
            districts.append(rec)
        elif key in C.OSM_TRANSIT_KEYS:
            transit.append(rec)
        elif (key, val) == C.OSM_AIRPORT:
            airports.append(rec)
        else:
            if not rec.get("name"):
                continue
            places.append(rec)
    return places, settlements, districts, transit, airports


def load_wikivoyage(wv_dir, lang):
    pages = [json.loads(l) for l in open(f"{wv_dir}/pages.jsonl", encoding="utf-8")]
    listings = [json.loads(l) for l in open(f"{wv_dir}/listings.jsonl", encoding="utf-8")]
    for r in listings:
        r["lang"] = lang
    return pages, listings


def load_pageviews(path):
    out = {}
    if path and pathlib.Path(path).exists():
        for line in open(path, encoding="utf-8"):
            r = json.loads(line); out[r["qid"]] = {"en": r.get("en", 0), "es": r.get("es", 0), "ko": r.get("ko", 0), "months": r.get("months", 1)}
    return out
