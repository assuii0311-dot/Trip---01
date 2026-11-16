"""세 소스의 교차 매칭 (E1 4절 4항, C 단계 규칙). QID 키 → 좌표 150m + 명칭 유사도 0.6 → 불일치 500m/0.4."""
import collections
import difflib
import functools
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


@functools.lru_cache(maxsize=None)
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


# ── 이름 일치(강화 규칙, E1 4절 4항, D-043) ─────────────────────────────────────
# 종류 낱말: 이름에서 "무엇인지"를 가리키는 낱말(norm 뒤의 꼴). SYN이 영어로 바꾼 낱말(church, museum 등)은 그대로 쓰고, 그 밖의 낱말은 여기서 종류로 옮긴다
TYPE_SYN = {
    "ermita": "hermitage", "capilla": "chapel", "capella": "chapel", "capela": "chapel", "santuario": "sanctuary", "santuari": "sanctuary", "convento": "convent", "abadia": "abbey",
    "parroquia": "church", "parroquial": "church", "parish": "church", "mezquita": "mosque", "sinagoga": "synagogue",
    "alcazar": "castle", "alcazaba": "castle", "fortaleza": "castle", "fortress": "castle", "muralla": "wall", "murallas": "wall", "muralles": "wall", "walls": "wall",
    "estacion": "station", "estacio": "station", "geltokia": "station", "aeropuerto": "airport", "aeroport": "airport",
    "hostal": "hotel", "hostel": "hotel", "pension": "hotel", "pensio": "hotel", "albergue": "hotel", "alberg": "hotel", "apartamentos": "hotel", "apartments": "hotel", "camping": "hotel",
    "restaurante": "restaurant", "cafe": "bar", "cafeteria": "bar", "taberna": "bar", "taverna": "bar", "cerveceria": "bar",
    "teatro": "theatre", "teatre": "theatre", "theater": "theatre", "ayuntamiento": "townhall", "ajuntament": "townhall", "udaletxea": "townhall", "concello": "townhall",
    "biblioteca": "library", "universidad": "university", "universitat": "university", "fuente": "fountain", "font": "fountain", "fonte": "fountain", "faro": "lighthouse",
    "cueva": "cave", "cuevas": "cave", "cova": "cave", "monte": "mountain", "montana": "mountain", "muntanya": "mountain", "mirador": "viewpoint",
}
# 종류 낱말 → 계열. 두 이름의 계열이 겹치지 않으면 서로 다른 대상으로 본다(역 ↔ 술집, 시청 ↔ 성)
TYPE_FAMILY = {t: fam for fam, ts in {
    "religious": "church cathedral basilica chapel hermitage sanctuary monastery convent abbey mosque synagogue",
    "fort": "castle palace tower wall",
    "nature": "beach mountain cave park garden viewpoint",
    "transport": "station airport",
    "lodging": "hotel",
    "food": "restaurant bar",
    "civic": "museum theatre townhall library university fountain lighthouse bridge square market",
}.items() for t in ts.split()}
COMMERCE_CATS = {"restaurant", "cafe", "lodging", "market"}  # 고유한 상호가 이름의 전부인 범주. 이름 일치를 엄격하게 본다
COMMERCE_WV = {"eat", "drink", "sleep", "buy"}


@functools.lru_cache(maxsize=None)
def name_parts(name):
    """이름을 (종류 계열 집합, 종류가 아닌 낱말 튜플)로 나눈다."""
    fams, rest = set(), []
    for t in norm(name).split():
        ty = TYPE_SYN.get(t, t)
        if ty in TYPE_FAMILY:
            fams.add(TYPE_FAMILY[ty])
        else:
            rest.append(t)
    return frozenset(fams), tuple(rest)


def type_conflict(names_a, names_b):
    """두 이름 묶음이 서로 다른 종류를 가리키는가. 종류 낱말이 양쪽에 다 있는 쌍이 있고, 그런 쌍 모두에서 계열이 겹치지 않을 때만 참."""
    seen = False
    for a in names_a:
        fa = name_parts(a)[0] if a else None
        if not fa:
            continue
        for b in names_b:
            fb = name_parts(b)[0] if b else None
            if not fb:
                continue
            if fa & fb:
                return False
            seen = True
    return seen


class NameWeights:
    """낱말의 무게: 이름 전체에서 드문 낱말일수록 무겁다(호텔·바르셀로나 같은 흔한 낱말은 가볍다). 이름 목록이 없으면 모든 낱말이 1."""

    def __init__(self, names=()):
        self.df = collections.Counter()
        self.n = 0
        for nm in names:
            if nm:
                self.n += 1
                self.df.update(set(norm(nm).split()))

    def w(self, t):
        return math.log((self.n + 1) / (self.df.get(t, 0) + 1)) if self.n else 1.0


LOW_INFO = {"san", "santa", "sant", "santo", "santos", "saint", "st", "nuestra", "senora", "mare", "virgen", "gran", "grand", "nuevo", "nueva", "new", "viejo", "vieja", "old", "real", "royal"}  # 이름을 가르는 힘이 약한 낱말. 무게를 4분의 1로 친다


def token_score(a, b, weights, strict=False):
    """두 이름에서 종류 낱말을 뺀 나머지 낱말이 겹치는 정도(0~1, 무게 기준).
    철자 차이는 긴 낱말에서만 같은 낱말로 본다(보통 5자 이상·유사도 0.75, 엄격 6자 이상·0.85).
    보통은 양쪽을 합친 비율, 엄격(상업 시설)은 양쪽 각각의 비율 중 작은 값이다(한쪽에만 있는 고유 낱말이 있으면 낮아진다)."""
    A, B = name_parts(a)[1], name_parts(b)[1]
    if not A or not B:
        return 0.0
    minlen, ratio = (6, 0.85) if strict else (5, 0.75)

    def eq(x, y):
        return x == y or (min(len(x), len(y)) >= minlen and difflib.SequenceMatcher(None, x, y).ratio() >= ratio)

    def wt(t):
        return weights.w(t) * (0.25 if t in LOW_INFO else 1.0)
    ma = sum(wt(x) for x in A if any(eq(x, y) for y in B))
    mb = sum(wt(y) for y in B if any(eq(y, x) for x in A))
    ta, tb = sum(wt(x) for x in A), sum(wt(y) for y in B)
    if not ta or not tb:
        return 0.0
    return min(ma / ta, mb / tb) if strict else (ma + mb) / (ta + tb)


def shared_token(a, b):
    """고유 낱말(종류 낱말과 힘이 약한 낱말을 뺀 것) 가운데 같은 것이 하나라도 있는가(5자 이상은 유사도 0.75 이상의 철자 차이 허용).
    흔한 낱말(도시 이름 등)을 빼고 세는 안은 시험해 보니 맞는 묶음이 1,000곳 넘게 더 풀려 쓰지 않는다(2026-11-16). 그래서 도시 이름만 같은 두 박물관이 묶일 수 있다(알려진 한계)."""
    A = [t for t in name_parts(a)[1] if t not in LOW_INFO]
    B = [t for t in name_parts(b)[1] if t not in LOW_INFO]
    return any(x == y or (min(len(x), len(y)) >= 5 and difflib.SequenceMatcher(None, x, y).ratio() >= 0.75) for x in A for y in B)


def names_agree(names_a, names_b, weights, strict=False):
    """같은 곳의 이름으로 볼 수 있는가(D-043). 글자 유사도(SIM_MATCH)를 통과한 후보에 한 번 더 건다.
    - 종류 계열이 서로 다르면 다른 대상이다.
    - 상업 시설(strict: 식당·카페·숙소·가게): 정규화한 이름이 같거나, 종류 낱말을 뺀 낱말이 양쪽 모두에서 대부분 겹쳐야 한다(TOKEN_AGREE_STRICT).
    - 그 밖: 정규화한 이름이 같거나, 글자 유사도가 SIM_STRONG 이상이거나, 고유 낱말이 하나 이상 같거나, 한쪽이 종류 낱말뿐인 이름("Catedral")이고 종류가 같으면 된다."""
    A = [x for x in names_a if x]
    B = [x for x in names_b if x]
    if not A or not B or type_conflict(A, B):
        return False
    for a in A:
        for b in B:
            s = sim(a, b)
            if s >= 1.0:
                return True
            if strict:
                if token_score(a, b, weights, True) >= C.TOKEN_AGREE_STRICT:
                    return True
                continue
            if s >= C.SIM_STRONG or shared_token(a, b):
                return True
            pa, pb = name_parts(a), name_parts(b)
            if pa[0] and pa[0] & pb[0] and (not pa[1] or not pb[1]):
                return True
    return False


def compatible(cats_a, cats_b):
    """범주 호환: 한쪽이 비어 있거나 교집합이 있으면 호환. 식당과 성당처럼 전혀 다른 범주는 매칭하지 않는다."""
    return not cats_a or not cats_b or bool(set(cats_a) & set(cats_b))


def best(cands, lat, lon, names, radius=C.R_MATCH_M, min_sim=C.SIM_MATCH, cats=None, weights=None, strict=False, other_qid=False):
    """반경 안 후보 중 명칭 유사도가 가장 높은 것. (후보, 거리, 유사도) 또는 None. weights를 주면 이름 일치(names_agree)까지 통과한 후보만 본다.
    other_qid: 찾는 쪽이 우리 목록에 없는 Wikidata 항목을 가리킨다. Wikidata 항목 후보와는 이름이 거의 같을 때(SIM_STRONG 이상)만 묶는다(중복 항목으로 본다)."""
    names = [n for n in names if n]
    bestc = None
    for c in cands:
        if cats is not None and not compatible(cats, c.get("cats") or []):
            continue
        d = hav(lat, lon, c["lat"], c["lon"])
        if d > radius:
            continue
        s = max((sim(n, cn) for n in names for cn in c["names"] if cn), default=0.0)
        if s >= min_sim and weights is not None and not names_agree(names, c["names"], weights, strict):
            continue
        if other_qid and c.get("wd") and s < C.SIM_STRONG:
            continue
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
            gw.add(c[0], c[1], {"key": q, "wd": True, "lat": c[0], "lon": c[1], "names": list(g["wd"]["labels"].values()), "cats": wd_categories(g["wd"]["classes"], bool(g["wd"]["heritage"]))})
    go = Grid()
    stats = {"osm_by_qid": 0, "osm_by_geo": 0, "osm_alone": 0, "wv_by_qid": 0, "wv_by_geo": 0, "wv_alone": 0, "wv_nocoord": 0, "mismatch": 0, "osm_qid_detached": 0, "osm_qid_wdname": 0, "osm_other_qid": 0, "wv_other_qid": 0}
    OSM_NAME_KEYS = ("name", "name:es", "name:en", "name:ca", "name:eu", "name:gl")
    weights = NameWeights([l for g in by_qid.values() for l in g["wd"]["labels"].values()] + [o.get(k) for o in osm_places for k in OSM_NAME_KEYS] + [w.get(k) for w in wv_listings for k in ("name", "alt")])
    for o in osm_places:
        ocats = osm_categories(o["key"], o["value"])
        if not ocats:
            stats["osm_noise"] = stats.get("osm_noise", 0) + 1
            continue  # 잡음 태그(관광안내판, 길가 십자가 등)는 장소도 매칭 후보도 아니다
        q = o.get("wikidata")
        g = by_qid.get(q) if q else None
        names = [o.get("name"), o.get("name:es"), o.get("name:en"), o.get("name:ca"), o.get("name:eu"), o.get("name:gl")]
        if g is not None:
            # 태그로 묶인 요소라도 그 항목에 딸린 다른 시설일 수 있다(역 건물의 술집, 성 안의 호텔). D-043:
            # 이름의 종류가 서로 다르거나(계열 충돌), 상업 시설인데 이름이 맞지 않으면 다른 대상으로 본다.
            labels = list(g["wd"]["labels"].values())
            wdcats = wd_categories(g["wd"]["classes"], bool(g["wd"]["heritage"]))
            nm = [n for n in names if n]
            commerce = set(ocats) <= COMMERCE_CATS and not (set(wdcats) & COMMERCE_CATS)
            # 범주가 겹치지 않는다는 것만으로는 떼지 않는다. 시험해 보니 문화재로만 분류된 수도원·성당 같은 맞는 묶음이 700곳 넘게 갈라졌다(2026-11-16)
            differs = bool(nm and labels) and (type_conflict(nm, labels) or (commerce and not names_agree(nm, labels, weights, strict=True)))
            if differs and (not wdcats or not (set(ocats) & set(wdcats))):
                g = None; stats["osm_qid_detached"] += 1  # 범주도 맞지 않는다: 묶지 않고 독립 장소로 둔다
            else:
                stats["osm_by_qid"] += 1; g["flags"].add("osm_qid")
                if differs:
                    o = dict(o, _wdname=True); stats["osm_qid_wdname"] += 1  # 범주는 맞는다: 묶되 이름과 좌표는 Wikidata 것을 쓴다(merge)
                c = g["wd"]["coord"]
                if c and (hav(o["lat"], o["lon"], c[0], c[1]) > C.R_MISMATCH_M or max((sim(n, l) for n in names if n for l in labels), default=1.0) < C.SIM_MISMATCH):
                    g["flags"].add("mismatch"); stats["mismatch"] += 1
        if g is None:
            # QID로 이미 OSM 객체가 붙은 Wikidata 항목에는 좌표·명칭 매칭으로 다른 OSM 객체를 더 붙이지 않는다(투우장 ↔ 알칼라 문 같은 오합 방지)
            # 태그가 다른 항목을 가리키는 요소(우리 목록에 없는 항목. Wikidata의 중복 항목이 많다)와 위에서 떼어 낸 요소는 이름이 거의 같을 때만 다른 항목에 묶는다(best의 other_qid). 떼어 낸 요소는 그 항목에 다시 붙이지 않는다
            if q and q not in by_qid:
                stats["osm_other_qid"] += 1
            cands = [c for c in gw.near(o["lat"], o["lon"]) if "osm_qid" not in by_qid[c["key"]]["flags"] and c["key"] != q]
            b = best(cands, o["lat"], o["lon"], names, cats=ocats, weights=weights, strict=set(ocats) <= COMMERCE_CATS, other_qid=bool(q))
            if b:
                g = by_qid[b[0]["key"]]; stats["osm_by_geo"] += 1
            else:
                g = new_group("osm:" + o["id"]); stats["osm_alone"] += 1
        g["osm"].append(o)
        go.add(o["lat"], o["lon"], {"key": g["key"], "lat": o["lat"], "lon": o["lon"], "names": names, "cats": ocats})
    for w in wv_listings:
        if w["type"] in ("marker", "go") and not w.get("wikidata"):
            continue
        q = w.get("wikidata")
        g = by_qid.get(q) if q else None
        names = [w.get("name"), w.get("alt")]
        if g is not None:
            stats["wv_by_qid"] += 1
            c = g["wd"]["coord"]
            if c and w.get("lat") is not None and w.get("lon") is not None and hav(w["lat"], w["lon"], c[0], c[1]) > C.R_MISMATCH_M:
                g["flags"].add("mismatch"); stats["mismatch"] += 1
        elif w.get("lat") is not None and w.get("lon") is not None:
            wcats = wv_categories(w["type"], w.get("raw_type"))
            cands = list(gw.near(w["lat"], w["lon"])) + list(go.near(w["lat"], w["lon"]))
            if q:
                stats["wv_other_qid"] += 1  # 우리 목록에 없는 항목을 가리키는 목록. 같은 규칙으로 본다
            b = best(cands, w["lat"], w["lon"], names, cats=wcats, weights=weights, strict=w["type"] in COMMERCE_WV, other_qid=bool(q))
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
