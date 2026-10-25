"""E1 파이프라인 단위 테스트. 고정 입력은 D 단계 검수 표본과 PoC 수치를 축약한 것."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.e1 import categories as cat  # noqa: E402
from pipeline.e1 import config as C  # noqa: E402
from pipeline.e1.match import build_groups, hav, sim  # noqa: E402
from pipeline.e1.merge import parse_price, place_from_group  # noqa: E402


def wd_item(qid, lat, lon, label_es, label_en=None, classes=("Q33506",), sitelinks=3, heritage=()):
    return {"qid": qid, "classes": set(classes), "coord": (lat, lon), "pop": None, "sitelinks": sitelinks, "p131": "Q2807",
            "labels": {"es": label_es, "en": label_en or label_es}, "desc": {"es": "museo en Madrid"}, "wiki": {"es": label_es}, "heritage": list(heritage), "wv_en": None}


def osm_poi(oid, lat, lon, name, key="tourism", value="museum", **extra):
    return {"id": oid, "lat": lat, "lon": lon, "key": key, "value": value, "name": name, **extra}


def wv_listing(idx, name, lat, lon, ltype="see", **extra):
    return {"lang": "en", "page": "Madrid", "idx": idx, "type": ltype, "raw_type": extra.pop("raw_type", ""), "section": "see", "tier": None, "name": name, "alt": None,
            "lat": lat, "lon": lon, "wikidata": extra.pop("wikidata", None), "content": extra.pop("content", "A museum."), "price": extra.pop("price", None), "hours": extra.pop("hours", None), "url": None, "phone": None, "address": None}


def test_categories_mapping():
    assert cat.osm_categories("tourism", "museum") == ["museum"]
    assert cat.osm_categories("tourism", "information") == []  # 잡음 제외
    assert cat.osm_categories("historic", "wayside_cross") == []
    assert cat.osm_categories("shop", "clothes") == ["market"]  # 키 기본값
    assert cat.wv_categories("see", "church") == ["religious"]
    assert cat.wv_categories("eat", "") == ["restaurant"]
    assert cat.wd_categories({"Q2977"}, False) == ["religious"]
    assert cat.wd_categories(set(), True) == ["heritage"]  # 유산 지정만 있는 항목
    assert cat.wd_categories({"Q2074737"}, True) == []  # 지자체는 장소가 아님
    assert cat.merge_categories(["museum"], ["museum", "restaurant"], ["bogus"]) == ["museum", "restaurant"]


def test_similarity_synonyms_and_articles():
    assert sim("Iglesia de San Pedro", "Church of San Pedro") == 1.0
    assert sim("Museo del Prado", "Prado Museum") >= 0.6
    assert sim("Plaça Major", "Plaza Mayor") >= 0.6
    assert sim("Bar Manolo", "Catedral de Sevilla") < 0.4


def test_haversine():
    assert abs(hav(40.4138, -3.6921, 40.4138, -3.6921)) < 1e-6
    d = hav(40.4168, -3.7038, 40.4138, -3.6921)  # 솔 광장 ↔ 프라도 약 1.05km
    assert 950 < d < 1150


def test_parse_price():
    assert parse_price("€12, free on Sundays") == (12.0, False)  # 금액이 있으면 금액. 부분 무료는 무시
    assert parse_price("Adults €15, children €7.50") == (15.0, False)  # 첫 금액
    assert parse_price("15 euros") == (15.0, False)
    assert parse_price("see website") == (None, False)
    assert parse_price(None) == (None, False)


def test_match_by_qid_and_geo_and_single():
    wd = {"Q160112": wd_item("Q160112", 40.4138, -3.6921, "Museo del Prado", "Prado Museum", sitelinks=120, heritage=["Q23712"]),
          "Q999": wd_item("Q999", 40.4200, -3.7000, "Ermita Chica", classes=("Q16970",), sitelinks=0)}
    osm = [osm_poi("w1", 40.41385, -3.69205, "Museo del Prado", wikidata="Q160112", opening_hours="Mo-Su 10:00-20:00"),
           osm_poi("n2", 40.42005, -3.70005, "Ermita Chica", key="amenity", value="place_of_worship"),  # QID 없음 → 좌표·명칭 매칭
           osm_poi("n3", 40.4300, -3.7100, "Bar Pepe", key="amenity", value="bar")]  # 단일 출처
    wv = [wv_listing(0, "Prado Museum", 40.4139, -3.6920, wikidata="Q160112", price="€15, free Mon-Sat 18:00-20:00", hours="M-Sa 10:00-20:00"),
          wv_listing(1, "Church of Ermita Chica", 40.4201, -3.7001, raw_type="church")]
    groups, stats = build_groups(wd, osm, wv)
    assert stats["osm_by_qid"] == 1 and stats["osm_by_geo"] == 1 and stats["osm_alone"] == 1
    assert stats["wv_by_qid"] == 1 and stats["wv_by_geo"] == 1
    g = groups["Q160112"]
    assert len(g["osm"]) == 1 and len(g["wv"]) == 1 and not g["flags"]
    p = place_from_group(g, {"Q160112": {"en": 20000, "es": 9000, "ko": 300, "months": 1}})
    assert p["cv"] == "match" and p["ver"] is True and p["tier"] == 1
    assert p["cs"] == "osm" and p["cc"] == "high"
    assert p["cat"] == ["museum"] and p["her"] == ["Q23712"]
    assert p["hrs"] == "M-Sa 10:00-20:00" and p["hrs_src"] == "wikivoyage"  # Wikivoyage 우선
    assert p["price"]["eur"] == 15.0 and p["price"]["free"] is False  # 금액 우선
    assert p["pop"]["sl"] == 120 and abs(p["pop"]["en_share"] - 0.69) < 0.01
    assert p["n"]["local"] == "Museo del Prado" and p["n"]["en"] == "Prado Museum"
    p2 = place_from_group(groups["Q999"], {})
    assert p2["cv"] == "match" and p2["cat"] == ["religious"]
    p3 = place_from_group(groups["osm:n3"], {})
    assert p3["cv"] == "single" and p3["ver"] is False and p3["tier"] == 2 and p3["cat"] == ["cafe"]


def test_mismatch_flag_when_qid_coords_disagree():
    wd = {"Q1": wd_item("Q1", 40.0, -3.0, "Castillo Lejano", classes=("Q23413",))}
    osm = [osm_poi("w9", 40.1, -3.0, "Castillo Lejano", key="historic", value="castle", wikidata="Q1")]  # 11km 떨어짐
    groups, stats = build_groups(wd, osm, [])
    assert stats["mismatch"] == 1
    p = place_from_group(groups["Q1"], {})
    assert p["cv"] == "mismatch" and p["cc"] == "low"


def test_settlements_excluded_from_places():
    wd = {"Q2807": {"qid": "Q2807", "classes": {"Q2074737", "Q515"}, "coord": (40.4168, -3.7038), "pop": 3000000, "sitelinks": 300, "p131": None, "labels": {"es": "Madrid"}, "desc": {}, "wiki": {}, "heritage": [], "wv_en": "Madrid"}}
    groups, _ = build_groups(wd, [], [])
    assert "Q2807" not in groups


def test_build_determinism_on_fixture(tmp_path):
    """같은 입력에 같은 출력(E1 4절 12항). 축약 고정 입력으로 build 모듈의 통합 함수를 두 번 돌린다."""
    wd = {"Q160112": wd_item("Q160112", 40.4138, -3.6921, "Museo del Prado", "Prado Museum", sitelinks=120)}
    osm = [osm_poi("w1", 40.41385, -3.69205, "Museo del Prado", wikidata="Q160112")]
    out = []
    for _ in range(2):
        groups, _ = build_groups(wd, osm, [])
        out.append(json.dumps([place_from_group(g, {}) for g in groups.values()], sort_keys=True))
    assert out[0] == out[1]


def test_price_numeric_beats_partial_free():
    assert parse_price("€15 (adults), €7.50 (seniors), free (children)") == (15.0, False)
    assert parse_price("Free; €5 for special exhibits") == (0.0, True)  # 첫머리가 무료


def test_similarity_substring_needs_similar_length():
    assert sim("Catedral", "Mesón La Catedral") < 1.0
    assert sim("Museo del Prado", "Museo Nacional del Prado") >= 0.6


def test_geo_match_requires_compatible_category():
    wd = {"Q5": wd_item("Q5", 40.0, -3.0, "Catedral de Prueba", classes=("Q2977",))}
    osm = [osm_poi("n7", 40.0001, -3.0001, "Mesón Catedral de Prueba", key="amenity", value="restaurant")]
    groups, stats = build_groups(wd, osm, [])
    assert stats["osm_alone"] == 1 and stats["osm_by_geo"] == 0


def test_plain_drops_file_links():
    from pipeline.e1.wikivoyage import plain
    t = plain("[[File:Cibeles.jpg|thumb|right|Palacio de Cibeles, [[Madrid]]'s city hall]]\nMadrid has over 3.4 million residents. {{cite|x}} See [[Retiro Park|the park]].")
    assert t.startswith("Madrid has over 3.4 million residents.") and "the park" in t and "thumb" not in t
