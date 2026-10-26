"""E1 파이프라인 단위 테스트. 고정 입력은 D 단계 검수 표본과 PoC 수치를 축약한 것."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.e1 import categories as cat  # noqa: E402
from pipeline.e1.airports import build_airports, parse_rows  # noqa: E402
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
    assert len(g["osm"]) == 1 and len(g["wv"]) == 1 and "mismatch" not in g["flags"]
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


def test_listing_with_lat_but_no_lon_does_not_crash():
    wd = {"Q7": wd_item("Q7", 40.0, -3.0, "Museo Medio", classes=("Q33506",))}
    wv = [wv_listing(0, "Museo Medio", 40.0, None, wikidata="Q7")]
    groups, stats = build_groups(wd, [], wv)
    assert stats["wv_by_qid"] == 1 and stats["mismatch"] == 0


def test_noise_osm_not_matched_and_no_second_geo_attach_when_qid_linked():
    wd = {"Q1": wd_item("Q1", 40.4155, -3.7074, "Plaza Mayor", "Plaza Mayor", classes=("Q174782",), sitelinks=50)}
    osm = [osm_poi("n1", 40.41551, -3.70741, "Centro de Turismo Plaza Mayor", key="tourism", value="information"),  # 잡음: 안내소
           osm_poi("w2", 40.41552, -3.70742, "Plaza Mayor", key="place", value="square", wikidata="Q1"),           # QID로 연결
           osm_poi("n3", 40.41560, -3.70750, "Bar Plaza Mayor", key="amenity", value="bar")]                     # 좌표·명칭은 비슷하지만 범주 불일치
    groups, stats = build_groups(wd, osm, [])
    g = groups["Q1"]
    assert stats.get("osm_noise") == 1 and [o["id"] for o in g["osm"]] == ["w2"]
    p = place_from_group(g, {})
    assert p["n"]["local"] == "Plaza Mayor"


def test_representative_osm_member_is_closest_name_to_label():
    wd = {"Q1": wd_item("Q1", 40.0, -3.0, "Puerta de Alcalá", "Alcalá Gate", classes=("Q4989906",), sitelinks=30)}
    osm = [osm_poi("n9", 40.0001, -3.0001, "Plaza de Toros de la Puerta de Alcalá", key="historic", value="yes", wikidata="Q1"),
           osm_poi("w1", 40.0002, -3.0002, "Puerta de Alcalá", key="historic", value="city_gate", wikidata="Q1")]
    groups, _ = build_groups(wd, osm, [])
    p = place_from_group(groups["Q1"], {})
    assert p["n"]["local"] == "Puerta de Alcalá" and p["src"]["osm"][0] == "w1" or p["n"]["local"] == "Puerta de Alcalá"


# --- 공항(E1 4절 13항, D-029). 고정 입력은 2026-10-26 SPARQL 결과를 축약한 것 ---
def _b(**kv):
    """SPARQL 바인딩 한 행"""
    return {k: {"value": v} for k, v in kv.items() if v is not None}


def test_airports_parse_rows_latest_pax_and_classes():
    rows = [
        _b(a="http://www.wikidata.org/entity/Q166276", iata="MAD", len="Madrid-Barajas Airport", les="aeropuerto Adolfo Suárez Madrid-Barajas", lko="마드리드 바라하스 국제공항",
           cls="http://www.wikidata.org/entity/Q644371", city="http://www.wikidata.org/entity/Q2807", cityEn="Madrid", coord="Point(-3.5676 40.4936)", pax="41833686", paxT="2014-01-01T00:00:00Z"),
        _b(a="http://www.wikidata.org/entity/Q166276", iata="MAD", cls="http://www.wikidata.org/entity/Q1248784", pax="66197066", paxT="2024-01-01T00:00:00Z"),
    ]
    out = parse_rows(rows)
    assert len(out) == 1 and out[0]["qid"] == "Q166276" and out[0]["classes"] == ["Q1248784", "Q644371"]
    assert out[0]["pax"] == {"value": 66197066, "year": 2024} and out[0]["coord"] == (40.4936, -3.5676) and out[0]["city"]["qid"] == "Q2807"


def _wd(qid, iata, en, lat, lon, classes=("Q1248784",), city=None, pax=None, es=None, ko=None):
    return {"qid": qid, "iata": iata, "icao": None, "labels": {"en": en, "es": es, "ko": ko}, "classes": list(classes), "city": city or {"qid": None, "en": None, "ko": None, "island": False}, "coord": (lat, lon), "pax": pax}


def test_build_airports_filter_dedupe_join_city():
    cities = [{"id": "Q2807", "n": {"en": "Madrid", "ko": "마드리드"}, "lat": 40.416944, "lon": -3.703333, "pop": 3506730},
              {"id": "Q943431", "n": {"en": "Granadilla de Abona", "ko": None}, "lat": 28.1186, "lon": -16.5756, "pop": 58752},
              {"id": "Qsmall", "n": {"en": "Tiny", "ko": None}, "lat": 28.04, "lon": -16.57, "pop": 500}]
    osm = [{"id": "w1", "lat": 40.4936, "lon": -3.5668, "name": "Aeropuerto Adolfo Suárez Madrid-Barajas", "name:en": "Adolfo Suárez Madrid-Barajas Airport", "wikidata": "Q166276"},
           {"id": "w2", "lat": 28.0445, "lon": -16.5725, "name": "Base Aérea de Son Sant Joan"}]  # QID 없는 3km 안 OSM 객체: 잇지 않는다(공군기지 오합 방지)
    wd = [_wd("Q166276", "MAD", "Madrid-Barajas Airport", 40.49, -3.57, ("Q644371",), {"qid": "Q2807", "en": "Madrid", "ko": "마드리드"}, {"value": 66197066, "year": 2024}, es="aeropuerto Adolfo Suárez Madrid-Barajas"),
          _wd("Q40", "TFS", "Tenerife South Airport", 28.0445, -16.5725, ("Q1248784",), {"qid": "Q40846", "en": "Tenerife", "ko": "테네리페", "island": True}, {"value": 10821703, "year": 2022}, es="aeropuerto de Tenerife Sur"),
          _wd("Qbase", "TOJ", "Torrejón Air Base", 40.49, -3.45, ("Q695850",)),  # 공군기지만: 제외
          _wd("Qtoj", "TOJ", "Madrid-Torrejón Airport", 40.4967, -3.56, ("Q1248784",), {"qid": "Qdistrict", "en": "Some District", "ko": None, "island": False}, pax={"value": 1970, "year": 2013}),
          _wd("Qrail", "XOC", "Madrid Atocha railway station", 40.4066, -3.6895, ("Q55488",)),  # 철도역: 제외
          _wd("Qheli", "JCU", "Ceuta Heliport", 35.8925, -5.3064, ("Q502074",))]
    out = build_airports(wd, osm, cities)
    assert [a["iata"] for a in out] == ["MAD", "TFS", "TOJ", "JCU"]  # 이용객 내림차순, 없으면 코드 순
    mad = out[0]
    assert mad["osm"] == "w1" and (mad["lat"], mad["lon"]) == (40.4936, -3.5668)  # 좌표는 OSM 우선
    assert mad["n"]["en"] == "Adolfo Suárez Madrid-Barajas Airport" and mad["n"]["local"].startswith("Aeropuerto") and mad["n"]["es"].startswith("Aeropuerto")
    assert mad["city"] == {"id": "Q2807", "en": "Madrid", "ko": "마드리드", "guess": False} and mad["heliport"] is False
    tfs = out[1]
    assert tfs["osm"] is None and tfs["n"]["local"] == "Aeropuerto de Tenerife Sur" and tfs["n"]["en"] == "Tenerife South Airport"  # OSM은 QID가 같을 때만
    assert tfs["city"] == {"id": "Q943431", "en": "Tenerife", "ko": "테네리페", "guess": True}  # P931이 섬 → 섬 이름, ID는 최근접 인구 2만 이상 도시
    assert out[2]["id"] == "Qtoj" and out[2]["city"] == {"id": "Q2807", "en": "Madrid", "ko": "마드리드", "guess": True}  # P931이 cities에 없고 섬도 아님 → 20km 안 도시
    jcu = out[3]
    assert jcu["heliport"] is True and jcu["city"]["en"] == "Madrid" and jcu["city"]["guess"] is True  # P931·근처 도시 없음 → 최근접(표본에는 마드리드뿐)
