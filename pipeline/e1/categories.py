"""소스별 분류 값을 상위 범주 12개로 대응한다 (E1 4절 3항). 복수 범주 허용."""
from . import config as C


def osm_categories(key, value):
    """OSM 주 태그 하나를 범주로. None이면 장소에서 제외."""
    kv = f"{key}={value}"
    if kv in C.OSM_TAG_CATEGORY:
        cat = C.OSM_TAG_CATEGORY[kv]
    else:
        cat = C.OSM_KEY_DEFAULT.get(key)
    return [cat] if cat else []


def wv_categories(ltype, raw_type):
    """Wikivoyage 목록 유형과 type 필드를 범주로."""
    raw = (raw_type or "").lower()
    for needle, cat in C.WV_RAW_TYPE_CATEGORY:
        if needle in raw:
            return [cat]
    if ltype == "see":
        return []  # 유형 없는 see는 약한 신호. 다른 소스에 범주가 없을 때만 merge에서 heritage로 둔다
    cat = C.WV_TYPE_CATEGORY.get(ltype)
    return [cat] if cat else []


def wd_categories(classes, has_heritage):
    """Wikidata 클래스 집합을 범주로. 유산 지정만 있는 항목은 heritage."""
    cats = []
    for q in classes:
        cat = C.WD_CLASS_CATEGORY.get(q)
        if cat and cat not in cats:
            cats.append(cat)
    if not cats and has_heritage and not (classes & C.WD_SETTLEMENT_CLASSES):
        cats.append("heritage")
    return cats


def merge_categories(*lists):
    """소스별 범주 목록을 합쳐 순서를 유지한 고유 목록으로."""
    out = []
    for lst in lists:
        for c in lst:
            if c in C.CATEGORIES and c not in out:
                out.append(c)
    return out
