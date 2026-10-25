"""세 소스의 교차 매칭 (E1 4절 4항, C 단계 규칙). QID 키 → 좌표 150m + 명칭 유사도 0.6 → 불일치 500m/0.4."""
import difflib
import math
import re
import unicodedata

from . import config as C

SYN = [("iglesia", "church"), ("catedral", "cathedral"), ("museo", "museum"), ("castillo", "castle"), ("palacio", "palace"), ("plaza", "square"), ("parque", "park"),
       ("puente", "bridge"), ("torre", "tower"), ("playa", "beach"), ("monasterio", "monastery"), ("mercado", "market"), ("jardín", "garden"), ("jardin", "garden"),
       ("basílica", "basilica"), ("basilica", "basilica"), ("esglèsia", "church"), ("església", "church"), ("eliza", "church"), ("museu", "museum"), ("castell", "castle"),
       ("palau", "palace"), ("plaça", "square"), ("parc", "park"), ("pont", "bridge"), ("platja", "beach"), ("mercat", "market"), ("jardí", "garden"), ("eleiza", "church")]
STOP = {"de", "la", "el", "los", "las", "del", "y", "the", "of", "and", "en", "a", "d", "l", "le", "des", "da", "do", "dos", "das", "i"}


def strip_accents(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


SYN_NORM = [(strip_accents(a), b) for a, b in SYN]


def norm(s):
    """소문자, 악센트 제거, 동의어(스페인어·카탈루냐어·바스크어 → 영어) 치환, 불용어 제거, 토큰 정렬."""
    if not s:
        return ""
    s = strip_accents(s.lower())
    for a, b in SYN_NORM:
        s = re.sub(rf"\b{re.escape(a)}\b", b, s)
    toks = sorted(t for t in re.split(r"[^a-z0-9]+", s) if t and t not in STOP)
    return " ".join(toks)


def sim(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= 4 and short in long_ and len(short) >= 0.75 * len(long_):
        return 1.0  # 짧은 쪽이 긴 쪽의 75% 이상일 때만 포함 관계를 인정
    return difflib.SequenceMatcher(None, a, b).ratio()


def hav(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    dlat, dlon = (lat2 - lat1) * p, (lon2 - lon1) * p
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dlon / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(min(1.0, a)))


class Grid:
    """약 0.005도(500m 안팎) 격자 색인."""
    def __init__(self, cell=0.005):
        self.cell = cell; self.cells = {}

    def key(self, lat, lon):
        return (int(lat / self.cell), int(lon / self.cell))

    def add(self, lat, lon, item):
        self.cells.setdefault(self.key(lat, lon), []).append(item)

    def near(self, lat, lon):
        kx, ky = self.key(lat, lon)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for it in self.cells.get((kx + dx, ky + dy), ()):
                    yield it


def compatible(cats_a, cats_b):
    """범주 호환: 한쪽이 비어 있거나 교집합이 있으면 호환. 식당과 성당처럼 전혀 다른 범주는 매칭하지 않는다."""
    return not cats_a or not cats_b or bool(set(cats_a) & set(cats_b))


def best(cands, lat, lon, names, radius=C.R_MATCH_M, min_sim=C.SIM_MATCH, cats=None):
    """반경 안 후보 중 명칭 유사도가 가장 높은 것. (후보, 거리, 유사도) 또는 None."""
    names = [n for n in names if n]
    bestc = None
    for c in cands:
        if cats is not None and not compatible(cats, c.get("cats") or []):
            continue
        d = hav(lat, lon, c["lat"], c["lon"])
        if d > radius:
            continue
        s = max((sim(n, cn) for n in names for cn in c["names"] if cn), default=0.0)
        if s >= min_sim and (bestc is None or s > bestc[2] or (s == bestc[2] and d < bestc[1])):
            bestc = (c, d, s)
    return bestc


def build_groups(wd_items, osm_places, wv_listings):
    """매칭 그룹을 만든다. 그룹: {key, wd, osm:[], wv:[], flags:set}"""
    groups, by_qid = {}, {}

    def new_group(key, wd=None):
        g = {"key": key, "wd": wd, "osm": [], "wv": [], "flags": set()}
        groups[key] = g
        return g

    for q, it in wd_items.items():
        if it["classes"] & C.WD_SETTLEMENT_CLASSES and not (it["classes"] - C.WD_SETTLEMENT_CLASSES):
            continue  # 지자체·도시는 장소가 아니다
        by_qid[q] = new_group(q, it)
    # 좌표 격자: Wikidata, OSM
    from .categories import osm_categories, wd_categories, wv_categories
    gw = Grid()
    for q, g in by_qid.items():
        c = g["wd"]["coord"]
        if c:
            gw.add(c[0], c[1], {"key": q, "lat": c[0], "lon": c[1], "names": list(g["wd"]["labels"].values()), "cats": wd_categories(g["wd"]["classes"], bool(g["wd"]["heritage"]))})
    go = Grid()
    stats = {"osm_by_qid": 0, "osm_by_geo": 0, "osm_alone": 0, "wv_by_qid": 0, "wv_by_geo": 0, "wv_alone": 0, "wv_nocoord": 0, "mismatch": 0}
    for o in osm_places:
        q = o.get("wikidata")
        g = by_qid.get(q) if q else None
        names = [o.get("name"), o.get("name:es"), o.get("name:en"), o.get("name:ca"), o.get("name:eu"), o.get("name:gl")]
        if g is not None:
            stats["osm_by_qid"] += 1
            c = g["wd"]["coord"]
            if c and (hav(o["lat"], o["lon"], c[0], c[1]) > C.R_MISMATCH_M or max((sim(n, l) for n in names if n for l in g["wd"]["labels"].values()), default=1.0) < C.SIM_MISMATCH):
                g["flags"].add("mismatch"); stats["mismatch"] += 1
        else:
            ocats = osm_categories(o["key"], o["value"])
            b = best(gw.near(o["lat"], o["lon"]), o["lat"], o["lon"], names, cats=ocats)
            if b:
                g = by_qid[b[0]["key"]]; stats["osm_by_geo"] += 1
            else:
                g = new_group("osm:" + o["id"]); stats["osm_alone"] += 1
        g["osm"].append(o)
        go.add(o["lat"], o["lon"], {"key": g["key"], "lat": o["lat"], "lon": o["lon"], "names": names, "cats": osm_categories(o["key"], o["value"])})
    for w in wv_listings:
        if w["type"] in ("marker", "go") and not w.get("wikidata"):
            continue
        q = w.get("wikidata")
        g = by_qid.get(q) if q else None
        names = [w.get("name"), w.get("alt")]
        if g is not None:
            stats["wv_by_qid"] += 1
            c = g["wd"]["coord"]
            if c and w.get("lat") is not None and hav(w["lat"], w["lon"], c[0], c[1]) > C.R_MISMATCH_M:
                g["flags"].add("mismatch"); stats["mismatch"] += 1
        elif w.get("lat") is not None and w.get("lon") is not None:
            wcats = wv_categories(w["type"], w.get("raw_type"))
            b = best(list(gw.near(w["lat"], w["lon"])) + list(go.near(w["lat"], w["lon"])), w["lat"], w["lon"], names, cats=wcats)
            if b:
                g = groups[b[0]["key"]] if b[0]["key"] in groups else by_qid.get(b[0]["key"]); stats["wv_by_geo"] += 1
            else:
                g = new_group(f"wv:{w['lang']}:{w['page']}:{w['idx']}"); stats["wv_alone"] += 1
        else:
            if w["type"] in ("see", "do", "eat", "drink", "sleep", "buy"):
                stats["wv_nocoord"] += 1
            continue
        g["wv"].append(w)
    return groups, stats
