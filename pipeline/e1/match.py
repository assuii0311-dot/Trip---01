"""세 소스의 교차 매칭 (E1 4절 4항, C 단계 규칙). QID 키 → 좌표 150m + 명칭 유사도 0.6 → 불일치 500m/0.4.

규칙 M1 ~ M8(2026-11-22, D-066)은 이름으로 켜고 끌 수 있다(build_groups의 rules). 기본은 모두 켠 것이다."""
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
# 세분한 종류 낱말(M5): 거리·문·기념물을 종류 낱말로 더하고, "civic" 한 계열이던 광장·다리·분수·박물관 등을 낱말마다의 계열로 나눈다
TYPE_SYN_FINE = dict(TYPE_SYN, **{
    "calle": "street", "carrer": "street", "rua": "street", "kalea": "street", "avenida": "street", "avinguda": "street", "paseo": "street", "passeig": "street", "avenue": "street",
    "puerta": "gate", "porta": "gate", "portal": "gate", "arco": "gate", "arc": "gate", "arch": "gate",
    "monumento": "monument", "memorial": "monument", "estatua": "monument", "statue": "monument", "escultura": "monument", "sculpture": "monument", "busto": "monument", "homenaje": "monument", "plaque": "monument",
})
TYPE_FAMILY_FINE = dict(TYPE_FAMILY, **{t: t for t in "museum theatre townhall library university fountain lighthouse bridge square street gate monument".split()}, market="square")  # 시장과 광장은 한 계열로 둔다("Plaza de Abastos"는 시장이다)
HEAD_ONLY = {"street", "gate", "monument"}  # 이름의 첫 낱말일 때만 종류로 센다. 지명과 상호에 흔히 들어가는 낱말이다("La Puerta de Segura"는 마을, "Virgen de la Calle"는 성모의 이름, "Hotel Avenida"는 상호)
# 부속물(M4): 다른 대상에 딸린 작은 것. OSM 주 태그 → 그 종류의 계열. 이름이 거의 같을 때만 다른 항목에 묶는다
ACCESSORY = {"tourism=artwork": "monument", "historic=memorial": "monument", "historic=monument": "monument", "amenity=fountain": "fountain"}
ALL_RULES = frozenset({"M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"})
ROMAN = {"ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15, "xvi": 16, "xvii": 17, "xviii": 18, "xix": 19, "xx": 20, "xxi": 21}
COMMERCE_CATS = {"restaurant", "cafe", "lodging", "market"}  # 고유한 상호가 이름의 전부인 범주. 이름 일치를 엄격하게 본다
COMMERCE_WV = {"eat", "drink", "sleep", "buy"}


@functools.lru_cache(maxsize=None)
def name_parts(name, fine=False):
    """이름을 (종류 계열 집합, 종류가 아닌 낱말 튜플)로 나눈다. fine이면 세분한 종류 낱말(M5)을 쓴다."""
    syn, family = (TYPE_SYN_FINE, TYPE_FAMILY_FINE) if fine else (TYPE_SYN, TYPE_FAMILY)
    toks = norm(name).split()
    raw = [x for x in re.split(r"[^a-z0-9]+", strip_accents((name or "").lower())) if x and x not in STOP]
    head = raw[0] if len(raw) >= 2 else None  # 낱말이 하나뿐인 이름("Avenida")은 종류 낱말로 보지 않는다
    fams, rest = set(), []
    for t in toks:
        ty = syn.get(t, t)
        if ty in family and not (family[ty] in HEAD_ONLY and t != head):
            fams.add(family[ty])
        else:
            rest.append(t)
    return frozenset(fams), tuple(rest)


@functools.lru_cache(maxsize=None)
def name_numbers(name):
    """이름에 든 번호(아라비아 숫자 4자리 이하, 로마 숫자 II 이상)의 집합. 한 글자 I는 카탈루냐어의 "i"(그리고)와 구별되지 않아 세지 않는다."""
    toks = re.split(r"[^a-z0-9]+", strip_accents((name or "").lower()))
    return frozenset({int(t) for t in toks if t.isdigit() and len(t) <= 4} | {ROMAN[t] for t in toks if t in ROMAN})


def number_conflict(names_a, names_b):
    """두 이름 묶음의 번호가 서로 다른가(M6). 번호가 양쪽에 다 있는 쌍이 있고, 그런 쌍 모두에서 번호가 겹치지 않을 때만 참(Cap de Barbaria II ↔ III)."""
    seen = False
    for a in names_a:
        na = name_numbers(a) if a else None
        if not na:
            continue
        for b in names_b:
            nb = name_numbers(b) if b else None
            if not nb:
                continue
            if na & nb:
                return False
            seen = True
    return seen


def kind_in_names(family, names):
    """이름들 가운데 그 종류(계열)의 낱말이 든 것이 있는가(부속물 규칙 M4에서 쓴다)."""
    return any(family in name_parts(n, True)[0] for n in names if n)


def accessory_agrees(family, acc_names, other_names, weights):
    """부속물(조형물·기념물·기념 명판·분수)의 이름이 상대의 이름과 엄격하게 맞는가(M4). 맞지 않으면 부속물은 묶음의 대표(이름·좌표)가 되지 못한다.
    - 분수: 분수 이름에만 분수 낱말이 있으면 맞지 않는다(광장의 분수 "Font de la Plaça de l'Ajuntament" ↔ 광장).
    - 그 밖: 정규화한 이름이 같거나, 종류 낱말을 뺀 낱말이 양쪽 모두에서 대부분 겹쳐야 한다("Monument a Àngel Guimerà" ↔ "A Àngel Guimerà"는 맞고,
      "Placa a la Construcción del Puente de los Alemanes" ↔ "puente de los Alemanes"는 맞지 않는다)."""
    if family == "fountain" and kind_in_names("fountain", acc_names) and not kind_in_names("fountain", other_names):
        return False
    return any(sim(a, b) >= 1.0 or token_score(a, b, weights, True, True) >= C.TOKEN_AGREE_STRICT for a in acc_names if a for b in other_names if b)


def type_conflict(names_a, names_b, fine=False):
    """두 이름 묶음이 서로 다른 종류를 가리키는가. 종류 낱말이 양쪽에 다 있는 쌍이 있고, 그런 쌍 모두에서 계열이 겹치지 않을 때만 참."""
    seen = False
    for a in names_a:
        fa = name_parts(a, fine)[0] if a else None
        if not fa:
            continue
        for b in names_b:
            fb = name_parts(b, fine)[0] if b else None
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


def token_score(a, b, weights, strict=False, fine=False):
    """두 이름에서 종류 낱말을 뺀 나머지 낱말이 겹치는 정도(0~1, 무게 기준).
    철자 차이는 긴 낱말에서만 같은 낱말로 본다(보통 5자 이상·유사도 0.75, 엄격 6자 이상·0.85).
    보통은 양쪽을 합친 비율, 엄격(상업 시설)은 양쪽 각각의 비율 중 작은 값이다(한쪽에만 있는 고유 낱말이 있으면 낮아진다)."""
    A, B = name_parts(a, fine)[1], name_parts(b, fine)[1]
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


def shared_token(a, b, fine=False):
    """고유 낱말(종류 낱말과 힘이 약한 낱말을 뺀 것) 가운데 같은 것이 하나라도 있는가(5자 이상은 유사도 0.75 이상의 철자 차이 허용).
    흔한 낱말(도시 이름 등)을 빼고 세는 안은 시험해 보니 맞는 묶음이 1,000곳 넘게 더 풀려 쓰지 않는다(2026-11-16). 그래서 도시 이름만 같은 두 박물관이 묶일 수 있다(알려진 한계)."""
    A = [t for t in name_parts(a, fine)[1] if t not in LOW_INFO]
    B = [t for t in name_parts(b, fine)[1] if t not in LOW_INFO]
    return any(x == y or (min(len(x), len(y)) >= 5 and difflib.SequenceMatcher(None, x, y).ratio() >= 0.75) for x in A for y in B)


def names_agree(names_a, names_b, weights, strict=False, rules=ALL_RULES):
    """같은 곳의 이름으로 볼 수 있는가(D-043). 글자 유사도(SIM_MATCH)를 통과한 후보에 한 번 더 건다.
    - 종류 계열이 서로 다르면 다른 대상이다.
    - 상업 시설(strict: 식당·카페·숙소·가게): 정규화한 이름이 같거나, 종류 낱말을 뺀 낱말이 양쪽 모두에서 대부분 겹쳐야 한다(TOKEN_AGREE_STRICT).
    - 그 밖: 정규화한 이름이 같거나, 글자 유사도가 SIM_STRONG 이상이거나, 고유 낱말이 하나 이상 같거나, 한쪽이 종류 낱말뿐인 이름("Catedral")이고 종류가 같으면 된다.
    - rules에 M5가 있으면 세분한 종류 낱말을 쓰고, M6이 있으면 번호가 서로 다른 이름을 다른 대상으로 본다."""
    A = [x for x in names_a if x]
    B = [x for x in names_b if x]
    fine = "M5" in rules
    if not A or not B or type_conflict(A, B, fine) or ("M6" in rules and number_conflict(A, B)):
        return False
    for a in A:
        for b in B:
            s = sim(a, b)
            if s >= 1.0:
                return True
            if strict:
                if token_score(a, b, weights, True) >= C.TOKEN_AGREE_STRICT:  # 상호에는 거리·문 같은 낱말이 이름의 일부로 쓰인다(Hotel Avenida). 낱말 겹침은 세분 전의 종류 낱말로 센다
                    return True
                continue
            if s >= C.SIM_STRONG or shared_token(a, b, fine):
                return True
            pa, pb = name_parts(a, fine), name_parts(b, fine)
            if pa[0] and pa[0] & pb[0] and (not pa[1] or not pb[1]):
                return True
    return False


def compatible(cats_a, cats_b):
    """범주 호환: 한쪽이 비어 있거나 교집합이 있으면 호환. 식당과 성당처럼 전혀 다른 범주는 매칭하지 않는다."""
    return not cats_a or not cats_b or bool(set(cats_a) & set(cats_b))


def best(cands, lat, lon, names, radius=C.R_MATCH_M, min_sim=C.SIM_MATCH, cats=None, weights=None, strict=False, other_qid=False, rules=ALL_RULES):
    """반경 안 후보 중 명칭 유사도가 가장 높은 것. (후보, 거리, 유사도) 또는 None. weights를 주면 이름 일치(names_agree)까지 통과한 후보만 본다.
    other_qid: 찾는 쪽이 우리 목록에 없는 Wikidata 항목을 가리킨다. Wikidata 항목 후보와는 이름이 거의 같을 때(SIM_STRONG 이상)만 묶는다(중복 항목으로 본다).
    M7: 후보가 상업 시설이면 찾는 쪽이 무엇이든 엄격한 이름 일치를 건다.
    M4: 후보가 부속물(c["acc"])이면 이름이 엄격하게 맞을 때만 묶는다(가이드 목록이 조형물에 붙는 것을 막는다). 찾는 쪽이 부속물인 경우는 build_groups가 다룬다.
    M1: 태그로 묶인 요소가 이미 있는 항목(c["strong"])에는 이름이 거의 같을 때(SIM_STRONG 이상)만 더 묶는다."""
    names = [n for n in names if n]
    bestc = None
    for c in cands:
        if cats is not None and not compatible(cats, c.get("cats") or []):
            continue
        d = hav(lat, lon, c["lat"], c["lon"])
        if d > radius:
            continue
        s = max((sim(n, cn) for n in names for cn in c["names"] if cn), default=0.0)
        st = strict or ("M7" in rules and bool(c.get("cats")) and set(c["cats"]) <= COMMERCE_CATS)
        if s >= min_sim and weights is not None and not names_agree(names, c["names"], weights, st, rules):
            continue
        if "M4" in rules and c.get("acc") and not accessory_agrees(c["acc"], c["names"], names, weights):
            continue
        if c.get("strong") and s < C.SIM_STRONG:
            continue
        if other_qid and c.get("wd") and s < C.SIM_STRONG:
            continue
        if s >= min_sim and (bestc is None or s > bestc[2] or (s == bestc[2] and d < bestc[1])):
            bestc = (c, d, s)
    return bestc


def build_groups(wd_items, osm_places, wv_listings, rules=ALL_RULES):
    """매칭 그룹을 만든다. 그룹: {key, wd, osm:[], wv:[], flags:set}
    rules: 켤 규칙 이름(M1 ~ M8, E1 4절 4항). 기본은 전부. 시험과 진단에서 일부만 켤 수 있다."""
    from .categories import osm_categories, wd_categories, wv_categories
    rules = frozenset(rules)
    fine = "M5" in rules
    groups, by_qid = {}, {}

    def new_group(key, wd=None):
        g = {"key": key, "wd": wd, "osm": [], "wv": [], "flags": set()}
        groups[key] = g
        return g

    for q, it in wd_items.items():
        if it["classes"] & C.WD_SETTLEMENT_CLASSES and not (it["classes"] - C.WD_SETTLEMENT_CLASSES):
            continue  # 지자체·도시는 장소가 아니다
        if "M3" in rules and not wd_categories(it["classes"], bool(it["heritage"])):
            continue  # 관광 범주가 없는 항목(역·공항이고 유산 지정이 없음)은 묶음의 중심이 되지 않는다(M3). 가까운 공원·상가를 끌어와 장소가 되던 것을 막는다
        by_qid[q] = new_group(q, it)
    # 좌표 격자: Wikidata, OSM
    gw = Grid()
    for q, g in by_qid.items():
        c = g["wd"]["coord"]
        if c:
            gw.add(c[0], c[1], {"key": q, "wd": True, "lat": c[0], "lon": c[1], "names": list(g["wd"]["labels"].values()), "cats": wd_categories(g["wd"]["classes"], bool(g["wd"]["heritage"]))})
    go = Grid()
    stats = {"osm_by_qid": 0, "osm_by_geo": 0, "osm_alone": 0, "wv_by_qid": 0, "wv_by_geo": 0, "wv_alone": 0, "wv_nocoord": 0, "mismatch": 0, "osm_qid_detached": 0, "osm_qid_wdname": 0, "osm_other_qid": 0, "wv_other_qid": 0, "osm_qid_moved": 0, "osm_acc_wdname": 0}
    OSM_NAME_KEYS = ("name", "name:es", "name:en", "name:ca", "name:eu", "name:gl")
    weights = NameWeights([l for g in by_qid.values() for l in g["wd"]["labels"].values()] + [o.get(k) for o in osm_places for k in OSM_NAME_KEYS] + [w.get(k) for w in wv_listings for k in ("name", "alt")])
    # M1: 태그로 묶이는 요소를 먼저 모두 붙인다(안정 정렬이라 두 무리 안의 순서는 입력 순서 그대로다). 읽는 순서에 따라 태그 없는 요소가 먼저 붙던 것을 없앤다.
    # 그 대신 태그로 묶인 요소가 있는 항목에도, 이름이 거의 같은 요소는 더 묶는다(같은 대상의 점과 면이 따로 장소가 되는 것을 줄인다. 대표는 태그로 묶인 요소다, M2)
    order = sorted(osm_places, key=lambda o: 0 if o.get("wikidata") in by_qid else 1) if "M1" in rules else osm_places
    for o in order:
        ocats = osm_categories(o["key"], o["value"])
        if not ocats:
            stats["osm_noise"] = stats.get("osm_noise", 0) + 1
            continue  # 잡음 태그(관광안내판, 길가 십자가 등)는 장소도 매칭 후보도 아니다
        q = o.get("wikidata")
        g = by_qid.get(q) if q else None
        names = [o.get("name"), o.get("name:es"), o.get("name:en"), o.get("name:ca"), o.get("name:eu"), o.get("name:gl")]
        acc = ACCESSORY.get(f"{o['key']}={o['value']}") if "M4" in rules else None
        if g is not None:
            # 태그로 묶인 요소라도 그 항목에 딸린 다른 시설일 수 있다(역 건물의 술집, 성 안의 호텔). D-043:
            # 이름의 종류가 서로 다르거나(계열 충돌), 상업 시설인데 이름이 맞지 않으면 다른 대상으로 본다.
            labels = list(g["wd"]["labels"].values())
            wdcats = wd_categories(g["wd"]["classes"], bool(g["wd"]["heritage"]))
            nm = [n for n in names if n]
            c = g["wd"]["coord"]
            dist = hav(o["lat"], o["lon"], c[0], c[1]) if c else None
            moved = None
            if "M8" in rules and dist is not None and dist > C.R_MISMATCH_M and nm and labels and not names_agree(nm, labels, weights, rules=rules):
                # M8: 태그가 가리키는 항목에서 멀고 이름도 다른데, 가까이에 이름이 거의 같은 다른 항목이 있으면 그 항목의 것으로 본다(지도 쪽 태그 오류).
                # 그런 항목이 없으면 태그를 따른다: 멀고 이름이 달라도 같은 대상의 다른 언어 이름인 경우가 많다(Aranomendi ↔ Monte Arano)
                moved = best([x for x in gw.near(o["lat"], o["lon"]) if x["key"] != q], o["lat"], o["lon"], names, cats=ocats, weights=weights, strict=set(ocats) <= COMMERCE_CATS, other_qid=True, rules=rules)
            if moved:
                g = by_qid[moved[0]["key"]]; stats["osm_qid_moved"] += 1
                g["osm"].append(o); go.add(o["lat"], o["lon"], {"key": g["key"], "lat": o["lat"], "lon": o["lon"], "names": names, "cats": ocats, "acc": acc})
                continue
            else:
                commerce = set(ocats) <= COMMERCE_CATS and not (set(wdcats) & COMMERCE_CATS)
                # 범주가 겹치지 않는다는 것만으로는 떼지 않는다. 시험해 보니 문화재로만 분류된 수도원·성당 같은 맞는 묶음이 700곳 넘게 갈라졌다(2026-11-16)
                # M4: 태그로 묶인 부속물(조형물·기념 명판·분수)은 이름 일치를 통과하지 못하면 다른 대상으로 본다(성당의 식별자가 붙은 조형물)
                differs = bool(nm and labels) and (type_conflict(nm, labels, fine) or (commerce and not names_agree(nm, labels, weights, True, rules)) or (acc is not None and not names_agree(nm, labels, weights, rules=rules)))
                if differs and (not wdcats or not (set(ocats) & set(wdcats))):
                    g = None; stats["osm_qid_detached"] += 1  # 범주도 맞지 않는다: 묶지 않고 독립 장소로 둔다
                else:
                    stats["osm_by_qid"] += 1; g["flags"].add("osm_qid")
                    if differs:
                        o = dict(o, _wdname=True); stats["osm_qid_wdname"] += 1  # 범주는 맞는다: 묶되 이름과 좌표는 Wikidata 것을 쓴다(merge)
                    if "M2" in rules:
                        o = dict(o, _by_qid=True)  # M2: 대표 요소는 태그로 묶인 요소 가운데에서 고른다(merge)
                    if c and (dist > C.R_MISMATCH_M or max((sim(n, l) for n in names if n for l in labels), default=1.0) < C.SIM_MISMATCH):
                        g["flags"].add("mismatch"); stats["mismatch"] += 1
        if g is None:
            # QID로 이미 OSM 객체가 붙은 Wikidata 항목에는 좌표·명칭 매칭으로 다른 OSM 객체를 더 붙이지 않는다(투우장 ↔ 알칼라 문 같은 오합 방지)
            # 태그가 다른 항목을 가리키는 요소(우리 목록에 없는 항목. Wikidata의 중복 항목이 많다)와 위에서 떼어 낸 요소는 이름이 거의 같을 때만 다른 항목에 묶는다(best의 other_qid). 떼어 낸 요소는 그 항목에 다시 붙이지 않는다
            if q and q not in by_qid:
                stats["osm_other_qid"] += 1
            cands = []
            for c in gw.near(o["lat"], o["lon"]):
                if c["key"] == q:
                    continue
                if "osm_qid" in by_qid[c["key"]]["flags"]:
                    if "M1" not in rules:
                        continue
                    c = dict(c, strong=True)
                cands.append(c)
            b = best(cands, o["lat"], o["lon"], names, cats=ocats, weights=weights, strict=set(ocats) <= COMMERCE_CATS, other_qid=bool(q), rules=rules)
            if b:
                g = by_qid[b[0]["key"]]; stats["osm_by_geo"] += 1
                if acc and not accessory_agrees(acc, names, b[0]["names"], weights):
                    o = dict(o, _wdname=True); stats["osm_acc_wdname"] += 1  # M4: 묶음에는 남지만 대표가 되면 이름과 좌표는 Wikidata 것을 쓴다(merge)
            else:
                g = new_group("osm:" + o["id"]); stats["osm_alone"] += 1
        g["osm"].append(o)
        go.add(o["lat"], o["lon"], {"key": g["key"], "lat": o["lat"], "lon": o["lon"], "names": names, "cats": ocats, "acc": acc})
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
            b = best(cands, w["lat"], w["lon"], names, cats=wcats, weights=weights, strict=w["type"] in COMMERCE_WV, other_qid=bool(q), rules=rules)
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
