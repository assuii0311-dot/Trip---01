"""E1 파이프라인 단위 테스트. 고정 입력은 D 단계 검수 표본과 PoC 수치를 축약한 것."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.e1 import categories as cat  # noqa: E402
from pipeline.e1.airports import build_airports, parse_rows  # noqa: E402
from pipeline.e1 import destinations as dest  # noqa: E402
from pipeline.e1 import islands as isl  # noqa: E402
from pipeline.e1 import sources  # noqa: E402
from pipeline.e1.geo import Boundaries, assign_city  # noqa: E402
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


# --- 여행지 목록(E1 4절 14~16항, D-030). 고정 입력은 2026-11-14 빌드 결과의 모양을 축약한 것 ---
def _place(pid, cats, sl=0, wv=False, en_share=None, her=(), tier=1, ko=None):
    return {"id": pid, "cat": list(cats), "tier": tier, "her": list(her), "n": {"local": pid, "en": pid.upper(), **({"ko": ko} if ko else {})},
            "src": {"wd": pid, "osm": [], "wv": [1] if wv else []}, "pop": {"sl": sl, "pv": None, "en_share": en_share}}


def _city(cid, en, pop, foreign=0, listings=0, pv=0, guide=True, lat=40.0, lon=-3.0, ko=None):
    return {"id": cid, "n": {"local": en, "es": en, "en": en, "ko": ko}, "lat": lat, "lon": lon, "pop": pop, "stratum": "other", "region": {"community": "Qc"},
            "wv": {"en": en if guide else None, "lead": None, "understand": None, "listings": listings, "pages": []}, "wiki": {}, "sl": 5, "pv": {"en": pv},
            "places": {"tier1": 0, "tier2": 0, "cat": {"heritage": 3}, "foreign": foreign}, "lodging_3km": 4, "districts": [{"id": "d-" + cid, "n": "Centro", "lat": lat, "lon": lon, "kind": "suburb", "lodging": pop // 1000}],
            "price_profile": None, "transit_feeds": [], "taxi_fare": None}


def test_first_sentences_and_weight():
    assert dest.first_sentences("Granada is a city in Granada Province. Rich in history, it is worthwhile. Third.\nNext line.") == "Granada is a city in Granada Province. Rich in history, it is worthwhile."
    assert dest.first_sentences("") is None and dest.first_sentences(None) is None
    assert dest.first_sentences("For the city in the United States, see Albuquerque\nAlburquerque is a town in Extremadura, Spain.") == "Alburquerque is a town in Extremadura, Spain."
    assert dest.first_sentences("It is 90&nbsp;km from the capital of the province.") == "It is 90 km from the capital of the province."
    long1 = "Zaragoza is the capital of Aragon. " + "It is one of the least known cities outside of Spain " * 8 + "indeed."
    assert dest.first_sentences(long1) == "Zaragoza is the capital of Aragon."  # 두 문장이 한도를 넘으면 한 문장만
    long2 = "Valencia " + "is a charming old city and the capital " * 12 + "of the region."
    out = dest.first_sentences(long2); assert out.endswith("…") and len(out) <= 321 and not out[:-1].endswith(" ")
    assert dest.place_weight(_place("a", ["museum"], sl=0, wv=False)) == 0
    assert round(dest.place_weight(_place("a", ["museum"], sl=9, wv=True)), 3) == round(2.302585 + 0.7, 3)


def test_taste_focus_overrepresented_categories_only():
    beach_town = [_place(f"b{i}", ["beach"], sl=5) for i in range(4)] + [_place(f"h{i}", ["heritage"], sl=5) for i in range(4)]
    w, n = dest.cat_profile(beach_town)
    base = {"heritage": 50.0, "beach": 6.0, "museum": 8.0}
    assert dest.taste_focus(w, n, base) == ["beach"]  # 유적 비중 0.5는 기준 0.78보다 낮아 빠진다
    one = [_place("m1", ["museum"], sl=50)] + [_place(f"h{i}", ["heritage"], sl=5) for i in range(6)]
    w, n = dest.cat_profile(one)
    assert "museum" not in dest.taste_focus(w, n, base)  # 상위 장소 안에 2곳 미만이면 표기하지 않는다
    assert dest.taste_focus({}, {}, base) == []


def test_highlights_foreign_landmarks_first():
    ps = [_place("big_local", ["heritage"], sl=40, en_share=0.2), _place("landmark", ["museum"], sl=30, en_share=0.7, ko="미술관"), _place("hotel", ["lodging"], sl=60, en_share=0.9), _place("minor", ["park"], sl=2)]
    hl = dest.highlights(ps, 3)
    assert [h["id"] for h in hl] == ["landmark", "big_local", "minor"] and hl[0]["n"]["ko"] == "미술관"
    # 볼거리 범주가 먼저, 경기장(체험만)은 뒤로, 역은 제외
    ps2 = [_place("stadium", ["activity"], sl=80, en_share=0.9), _place("cathedral", ["religious"], sl=20, en_share=0.3), _place("x", ["heritage"], sl=15, en_share=0.6)]
    ps2[2]["n"]["en"] = "Girona railway station"
    assert [h["id"] for h in dest.highlights(ps2, 3)] == ["cathedral", "stadium"]


def test_islands_assign_members_and_eligible(tmp_path):
    from shapely.geometry import box
    osm = [{"osm_id": "r1", "name": "Mallorca", "name_en": "Majorca", "wikidata": "Q8828", "wkb": box(2.3, 39.2, 3.5, 40.0).wkb_hex},
           {"osm_id": "r2", "name": "Sa Dragonera", "wikidata": "Q1", "wkb": box(2.30, 39.57, 2.34, 39.60).wkb_hex}]
    cities = [_city("Qpalma", "Palma", 430000, lat=39.57, lon=2.65), _city("Qsoller", "Sóller", 14000, lat=39.77, lon=2.71), _city("Qmad", "Madrid", 3000000)]
    mem = isl.assign_members(osm, cities)
    assert {i: [c["id"] for c in cs] for i, cs in mem.items()} == {0: ["Qpalma", "Qsoller"]}
    assert isl.eligible(osm[0], {"enwikivoyage": "Mallorca"}, {"Mallorca", "Palma"}) == "Mallorca"
    assert isl.eligible(osm[0], {}, {"Majorca"}) == "Majorca" and isl.eligible(osm[1], {}, {"Mallorca"}) is None
    # 같은 섬이 두 번 나오면(카나리아 추출본의 라팔마 사례) osm_id가 앞선 하나만 남긴다
    f1, f2 = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    f1.write_text(json.dumps({"osm_id": "r9", "name": "La Palma", "wikidata": "Q2"}) + "\n" + json.dumps({"osm_id": "r1", "name": "La Palma", "wikidata": "Q2"}) + "\n", encoding="utf-8")
    f2.write_text(json.dumps({"osm_id": "r5", "name": "Lobos", "wikidata": None}) + "\n", encoding="utf-8")
    assert [r["osm_id"] for r in isl.load_osm_islands([f1, f2])] == ["r1", "r5"]


def test_build_destinations_tiers_islands_unesco_overrides(monkeypatch):
    monkeypatch.setattr(C, "DEST_TIER_SIZES", (1, 1, 1))
    cities = [_city("A", "Alpha", 900000, foreign=9, listings=90, pv=900), _city("B", "Beta", 500000, foreign=5, listings=50, pv=500), _city("Cc", "Gamma", 100000, foreign=3, listings=30, pv=300),
              _city("D", "Delta", 50000, foreign=0, listings=9, pv=90), _city("E", "Epsilon", 40000, foreign=0, listings=8, pv=80), _city("N", "NoGuide", 800000, foreign=8, listings=0, pv=999, guide=False),
              _city("P", "Palma", 430000, foreign=4, listings=40, pv=400, ko="팔마"), _city("S", "Soller", 14000, foreign=0, listings=5, pv=50)]
    places = {"D": [_place("d1", ["heritage"], sl=20, her=["Q9259"]), _place("d2", ["heritage"], sl=3)], "E": [_place("e1", ["park"], sl=2)],
              "P": [_place("p1", ["museum"], sl=30, en_share=0.8), _place("p2", ["beach"], sl=6), _place("p3", ["beach"], sl=5)], "S": [_place("s1", ["nature"], sl=12, en_share=0.6), _place("s2", ["beach"], sl=4)],
              "A": [_place("a1", ["heritage"], sl=50), _place("a2", ["heritage"], sl=40), _place("a3", ["heritage"], sl=30)]}
    islands = [{"id": "ISL", "members": ["S", "P"], "n": {"local": "Mallorca", "es": "Mallorca", "en": "Mallorca", "ko": "마요르카섬"},
                "wv": {"en": "Mallorca", "lead": "Mallorca is an island.", "understand": "u", "listings": 2}, "wiki": {"en": "Mallorca"}, "pv": {"en": 50}}]
    recs, report = dest.build_destinations(cities, places, islands, overrides={"exclude": [], "include": {}, "tier": {}})
    by = {c["id"]: c for c in cities}
    assert [r["id"] for r in recs] == ["ISL"] and recs[0]["members"] == ["P", "S"] and recs[0]["capital"] == "P" and recs[0]["pop"] == 444000
    assert recs[0]["places"]["foreign"] == 2 and recs[0]["wv"]["listings"] == 2 and recs[0]["districts"][0]["id"] == "d-P"
    assert by["P"]["island"] == "ISL" and by["S"]["island"] == "ISL" and "dest" not in by["P"]  # 섬에 속한 지자체는 섬으로 대표된다
    assert by["A"]["dest"]["tier"] == 1 and by["B"]["dest"]["tier"] == 2 and by["Cc"]["dest"]["tier"] == 3 and by["A"]["dest"]["rank"] == 1
    assert by["D"]["dest"] == {"tier": 3, "rank": by["D"]["dest"]["rank"], "via": "unesco", "unesco": 1, "signals": {"foreign": 0, "listings": 9, "pv_en": 90}}
    assert by["E"]["dest"] is None and "dest" not in by["N"]  # 가이드 문서가 없으면 후보가 아니다
    assert recs[0]["dest"]["tier"] == 3 and recs[0]["dest"]["via"] in ("island", "rank")
    assert recs[0]["focus"] == ["beach"] and [h["id"] for h in recs[0]["hl"]] == ["p1", "s1", "p2"]
    assert report["islands"] == 1 and report["island_members"] == 2 and report["destinations"] == 5
    # 수동 보정: 제외하면 순위에서 빠지고, 포함·등급 고정이 적용된다
    cities2 = [_city("A", "Alpha", 900000, foreign=9, listings=90, pv=900), _city("B", "Beta", 500000, foreign=5, listings=50, pv=500), _city("E", "Epsilon", 40000, listings=8, pv=80), _city("F", "Phi", 30000, listings=7, pv=70), _city("G", "Chi", 20000, listings=6, pv=60)]
    _, rep2 = dest.build_destinations(cities2, {}, [], overrides={"exclude": ["A"], "include": {"G": 3}, "tier": {"B": 2}})
    by2 = {c["id"]: c for c in cities2}
    assert "dest" not in by2["A"] and by2["B"]["dest"]["tier"] == 2 and by2["B"]["dest"]["via"] == "manual" and by2["G"]["dest"]["via"] == "manual" and rep2["destinations"] == 4


# --- 카나리아 추출본 병합과 결정성(D-031) ---
def test_load_osm_multiple_extracts_skip_duplicate_ids(tmp_path):
    a, b = tmp_path / "spain.jsonl", tmp_path / "canarias.jsonl"
    a.write_text("\n".join(json.dumps(r) for r in [osm_poi("n1", 40.0, -3.0, "Museo A"), osm_poi("n2", 28.47, -16.24, "Terminal", key="amenity", value="ferry_terminal")]) + "\n", encoding="utf-8")
    b.write_text("\n".join(json.dumps(r) for r in [osm_poi("n2", 28.47, -16.24, "Terminal (중복)", key="amenity", value="ferry_terminal"), osm_poi("n3", 28.1, -15.4, "Museo Canario"),
                                                    osm_poi("n4", 28.05, -16.57, "Aeropuerto de Tenerife Sur", key="aeroway", value="aerodrome")]) + "\n", encoding="utf-8")
    places, settlements, districts, transit, airports = sources.load_osm([a, b])
    assert [p["id"] for p in places] == ["n1", "n2", "n3"] and places[1]["name"] == "Terminal" and [x["id"] for x in airports] == ["n4"]
    assert [p["id"] for p in sources.load_osm(a)[0]] == ["n1", "n2"]  # 파일 하나만 줘도 된다


def test_boundaries_overlap_is_deterministic_and_prefers_known_municipality(tmp_path):
    from shapely.geometry import box
    rows = [{"osm_id": "r1", "admin_level": "8", "name": "Segovia", "wikidata": "Qseg", "wkb": box(0, 0, 10, 10).wkb_hex},
            {"osm_id": "r2", "admin_level": "8", "name": "Revenga", "wikidata": "Qsub", "wkb": box(1, 1, 2, 2).wkb_hex},      # 지자체 안의 하위 행정 단위
            {"osm_id": "w3", "admin_level": "8", "name": None, "wikidata": None, "wkb": box(1.4, 1.4, 1.6, 1.6).wkb_hex},    # 이름도 태그도 없는 작은 경계
            {"osm_id": "r4", "admin_level": "8", "name": "Estavar", "wikidata": "Qfr", "wkb": box(20, 20, 21, 21).wkb_hex}]  # 국경 밖 지자체
    f1, f2 = tmp_path / "b1.jsonl", tmp_path / "b2.jsonl"
    f1.write_text("\n".join(json.dumps(r) for r in rows[:2]) + "\n", encoding="utf-8")
    f2.write_text("\n".join(json.dumps(r) for r in [rows[1]] + rows[2:]) + "\n", encoding="utf-8")  # r2는 두 파일에 다 있다
    class NoNear:
        def find(self, lat, lon): return None, None
    for paths in ([f1, f2], [f2, f1]):  # 파일 순서가 달라도 결과가 같다
        bd = Boundaries(paths)
        assert bd.count == 4 and [r["osm_id"] for r in bd.lookup_all("8", 1.5, 1.5)] == ["w3", "r2", "r1"]
        assert assign_city(bd, NoNear(), 1.5, 1.5, {}, {}, {"Qseg"}) == ("Qseg", "polygon")   # 지자체 목록에 있는 경계가 먼저
        assert assign_city(bd, NoNear(), 1.5, 1.5, {}, {}, None) == ("Qsub", "polygon")        # 목록을 안 주면 면적이 작은 순
        assert assign_city(bd, NoNear(), 20.5, 20.5, {}, {}, {"Qseg"}) == ("Qfr", "polygon")    # 목록에 없는 경계뿐이면 태그 값을 그대로(이전 동작)
        assert assign_city(bd, NoNear(), 50.0, 50.0, {}, {}, {"Qseg"}) == (None, "none")


def test_wd_categories_order_does_not_depend_on_set_order():
    expected = ["museum", "religious", "heritage"]  # 대응표(config)에 적힌 순서
    for classes in ({"Q839954", "Q16970", "Q33506"}, {"Q33506", "Q839954", "Q16970"}, set(reversed(["Q839954", "Q16970", "Q33506"]))):
        assert cat.wd_categories(classes, False) == expected
    assert cat.wd_categories({"Q2074737"}, True) == [] and cat.wd_categories(set(), True) == ["heritage"]


# ── 이름 일치 강화 규칙(D-043). 사례는 2026-11-15 장소 설명 생성 때 사람이 가려낸 틀린 묶음과 맞는 묶음이다
def test_names_agree_rejects_known_wrong_pairs_and_keeps_right_ones():
    from pipeline.e1.match import NameWeights, names_agree, type_conflict
    corpus = ["Hotel Granvia", "Gran Hotel Havana", "Hotel Barcelona Center", "Hotel Pelayo Barcelona", "Expo Hotel Barcelona", "Mercure Barcelona Condor", "Mercure Alberta Barcelona",
              "Hostal Live Barcelona", "Hotel Soho Barcelona", "Way Hostel", "Mad Hostel", "Bar Pepe", "Bar La Estación", "Restaurante Roma", "Restaurante Kogan", "SH Ifach", "Hotel SH Ifach",
              "Iglesia de San Pedro", "Iglesia de San Juan", "Iglesia de Santa María", "Catedral de Jaca", "Museo del Prado", "Citrus", "Vinitus", "La Fontana", "La Tavina"] * 3
    w = NameWeights(corpus)
    wrong = [("Gran Hotel Havana", "Hotel Granvia"), ("Way Hostel", "Mad Hostel"), ("Citrus", "Vinitus"), ("La Fontana", "La Tavina"), ("Hotel Pelayo Barcelona", "Expo Hotel Barcelona"),
             ("Mercure Barcelona Condor", "Mercure Alberta Barcelona"), ("Hostal Live Barcelona", "Hotel Soho Barcelona"), ("Kogan Restaurante", "Roma Restaurante"), ("La Caravana", "La Campana")]
    for a, b in wrong:
        assert not names_agree([a], [b], w, strict=True), (a, b)
    right_strict = [("SH Ifach", "Hotel SH Ifach"), ("Coscorrones", "Bar Coscorrones"), ("Bar Restaurant Santa Margarida", "Santa Margarita Restaurant"), ("Avenida", "Hotel Avenida")]
    for a, b in right_strict:
        assert names_agree([a], [b], w, strict=True), (a, b)
    # 볼거리: 철자 차이와 종류 낱말뿐인 이름은 같은 곳으로, 성인 이름이 다르면 다른 곳으로
    assert names_agree(["Castillo de Javier"], ["Castle of Xabier"], w)
    assert names_agree(["Catedral"], ["Catedral de Jaca"], w)
    assert names_agree(["Euskal Herriko Museoa"], ["Museo Euskal Herria"], w)
    assert not names_agree(["Iglesia de San Pedro"], ["Iglesia de San Juan"], w)
    assert not names_agree(["Iglesia de Santa María Reina y Madre"], ["iglesia de los Santos Mártires"], w)
    # 종류 계열이 다르면 이름이 겹쳐도 다른 대상
    assert type_conflict(["Ayuntamiento de Tarifa"], ["Castillo de Tarifa"]) and type_conflict(["Hotel Torre del Compte"], ["estación de Torre del Compte"]) is False  # 탑(tower)이 양쪽에 있어 계열로는 못 가른다
    assert not names_agree(["Bar La Estación"], ["estación de San Claudio"], w, strict=True)  # 역 건물의 술집: 고유 낱말이 겹치지 않는다
    assert type_conflict(["Mezquita de Torrevieja"], ["Estación de Torrevieja"]) and not type_conflict(["Capela do Santo André"], ["Catedral de Santiago de Compostela"])
    assert not names_agree(["Ayuntamiento de Tarifa"], ["Castillo de Tarifa"], w)


def test_qid_tagged_osm_of_other_kind_is_detached_or_keeps_wikidata_name():
    # 역 항목(관광 범주 없음)에 태그된 술집은 묶지 않는다. 역은 범주가 없어 장소가 되지 않고 술집은 독립 장소로 남는다
    wd = {"Q1": wd_item("Q1", 43.0, -5.0, "estación de San Claudio", classes=("Q55488",), sitelinks=2),
          "Q2": wd_item("Q2", 36.01, -5.60, "Castillo de Tarifa", "Castle of Tarifa", classes=("Q23413",), sitelinks=5)}
    osm = [osm_poi("n1", 43.0001, -5.0001, "Bar La Estación", key="amenity", value="bar", wikidata="Q1"),
           osm_poi("w2", 36.0101, -5.6001, "Ayuntamiento de Tarifa", key="historic", value="castle", wikidata="Q2")]
    groups, stats = build_groups(wd, osm, [])
    assert stats["osm_qid_detached"] == 1 and stats["osm_qid_wdname"] == 1
    assert groups["Q1"]["osm"] == [] and place_from_group(groups["Q1"], {}) is None
    bar = place_from_group(groups["osm:n1"], {}); assert bar["cat"] == ["cafe"] and bar["n"]["local"] == "Bar La Estación"
    castle = place_from_group(groups["Q2"], {})
    assert castle["n"]["local"] == "Castillo de Tarifa" and castle["cs"] == "wikidata" and castle["cat"] == ["heritage"]
    # 범주만 다르고(문화재로만 분류된 수도원) 이름의 종류가 같으면 그대로 묶는다
    wd2 = {"Q645157": wd_item("Q645157", 41.38, 1.08, "Monasterio de Poblet", classes=("Q4989906",), sitelinks=40)}
    osm2 = [osm_poi("w8", 41.3801, 1.0801, "Reial Monestir de Santa Maria de Poblet", key="amenity", value="place_of_worship", wikidata="Q645157")]
    groups2, stats2 = build_groups(wd2, osm2, [])
    assert len(groups2["Q645157"]["osm"]) == 1 and stats2["osm_qid_detached"] == 0


def test_osm_pointing_to_another_qid_matches_only_when_names_agree():
    # 이름이 맞지 않으면 가까이 있어도 묶지 않는다(말라가의 두 성당: 글자 유사도는 0.6을 넘지만 고유 낱말이 겹치지 않는다)
    wd = {"Q5912680": wd_item("Q5912680", 36.7227, -4.4236, "iglesia de los Santos Mártires", classes=("Q16970",), sitelinks=3)}
    osm = [osm_poi("w3", 36.72223, -4.424215, "Iglesia de los Santos Martires", key="amenity", value="place_of_worship", wikidata="Q20021492")]
    wv = [wv_listing(0, "Santos Mártires church", 36.7227, -4.4236, raw_type="church", wikidata="Q777")]
    groups, stats = build_groups(wd, osm, wv)
    assert stats["osm_other_qid"] == 1 and stats["wv_other_qid"] == 1
    # 이름이 거의 같으면 다른 번호를 가리켜도 같은 곳으로 본다(Wikidata에 중복 항목이 많다)
    assert len(groups["Q5912680"]["osm"]) == 1 and len(groups["Q5912680"]["wv"]) == 1
    osm2 = [osm_poi("w4", 36.72223, -4.424215, "Iglesia de Santa María Reina y Madre", key="amenity", value="place_of_worship", wikidata="Q20021492")]
    groups2, stats2 = build_groups(wd, osm2, [])
    assert groups2["Q5912680"]["osm"] == [] and "osm:w4" in groups2 and stats2["osm_by_geo"] == 0
    # 고유 낱말 하나만 같은 정도로는 묶지 않는다(산티아고 순례길 항목 ↔ 산티아고 사도 성당)
    wd3 = {"Q41150": wd_item("Q41150", 42.8806, -8.5446, "Camino de Santiago", "Way of St. James", classes=("Q4989906",), sitelinks=90)}
    osm3 = [osm_poi("w5", 42.8807, -8.5447, "Santiago Apóstolo", key="amenity", value="place_of_worship", wikidata="Q999999")]
    groups3, _ = build_groups(wd3, osm3, [])
    assert groups3["Q41150"]["osm"] == [] and "osm:w5" in groups3


def test_geo_match_needs_name_agreement_for_commerce_listing():
    osm = [osm_poi("n5", 41.3927, 2.1720, "Gran Hotel Havana", key="tourism", value="hotel"), osm_poi("n6", 41.3929, 2.1722, "Hotel Granvia", key="tourism", value="hotel")]
    wv = [wv_listing(0, "Hotel Granvia", 41.39272, 2.17202, ltype="sleep")]  # 좌표는 Havana 쪽에 더 가깝다
    groups, stats = build_groups({}, osm, wv)
    assert len(groups["osm:n6"]["wv"]) == 1 and groups["osm:n5"]["wv"] == []
    wv2 = [wv_listing(1, "Hotel Granvia", 41.39272, 2.17202, ltype="sleep")]
    groups2, stats2 = build_groups({}, osm[:1], wv2)  # 같은 이름의 장소가 없으면 목록은 따로 남는다
    assert groups2["osm:n5"]["wv"] == [] and stats2["wv_alone"] == 1


def test_boundary_fallback_hull_and_spanish_ine_only():
    # T-049: 다각형으로 조립되지 않은 스페인 지자체(세우타)는 경계선 점들의 볼록 껍질로 대신한다
    import importlib.util
    from shapely import wkb
    from shapely.geometry import Point
    spec = importlib.util.spec_from_file_location("osm_boundaries", str(ROOT / "pipeline/e1/osm_boundaries.py")); ob = importlib.util.module_from_spec(spec); spec.loader.exec_module(ob)
    w = ob.hull_wkb([(-5.38, 35.87), (-5.28, 35.87), (-5.28, 35.92), (-5.38, 35.92), (-5.33, 35.90)])
    g = wkb.loads(bytes.fromhex(w)); assert g.geom_type == "MultiPolygon" and g.contains(Point(-5.32, 35.89)) and not g.contains(Point(-5.50, 35.89))
    assert ob.hull_wkb([(0, 0), (1, 1)]) is None and ob.hull_wkb([(0, 0), (1, 1), (2, 2)]) is None
    assert ob.is_spanish_ine("51001000000") and ob.is_spanish_ine("28079") and not ob.is_spanish_ine("170601") and not ob.is_spanish_ine(None)


def test_wikidata_supplement_record_prefers_preferred_population():
    from pipeline.e1.wikidata_supplement import record_from_entity
    ent = {"labels": {"es": {"value": "Ceuta"}, "ko": {"value": "세우타"}}, "sitelinks": {"eswiki": {}, "enwikivoyage": {}},
           "claims": {"P625": [{"mainsnak": {"datavalue": {"value": {"latitude": 35.886667, "longitude": -5.3}}}}], "P131": [{"mainsnak": {"datavalue": {"value": {"id": "Q29"}}}}],
                      "P1082": [{"rank": "normal", "mainsnak": {"datavalue": {"value": {"amount": "+83229"}}}, "qualifiers": {"P585": [{"datavalue": {"value": {"time": "+2024-01-01T00:00:00Z"}}}]}},
                                {"rank": "preferred", "mainsnak": {"datavalue": {"value": {"amount": "+83595"}}}, "qualifiers": {"P585": [{"datavalue": {"value": {"time": "+2025-01-01T00:00:00Z"}}}]}}]}}
    r = record_from_entity("Q5823", ent)
    assert r == {"qid": "Q5823", "cls": "Q2074737", "coord": "Point(-5.3 35.886667)", "pop": "83595", "sitelinks": "2", "p131": "Q29", "label_es": "Ceuta", "label_en": None, "label_ko": "세우타", "n_heritage": 0, "wv_en": True}



# --- 음식 관련 절 수집(E5 4절 12항, D-062). 고정 입력은 2026-11-22에 받은 스페인어 위키백과·위키보이지 문서의 모양을 축약한 것.
def test_food_sections_find_and_clean_the_section():
    from pipeline.e1 import food_sections as fs
    wiki = ("Intro.\n== Historia ==\nTexto.\n== Cultura ==\nMuseos.\n=== Gastronomía<ref>x</ref> ===\nEl plato típico es el '''salmorejo''' {{cita|x}} y el [[rabo de toro]].\n"
            "{| class=\"wikitable\"\n| fila\n|}\n==== Dulces ====\nEl [[pastel cordobés|pastel]].\n<gallery>\nArchivo:Foto.jpg|pie\n</gallery>\n=== Fiestas ===\nLa feria.\n== Deporte ==\nFútbol.")
    title, body = fs.find_section(wiki, ("gastronomia", "cocina"))
    assert title == "Gastronomía" and "Dulces" in body and "Fiestas" not in body and "Deporte" not in body  # 하위 절은 품고, 같은 수준의 다음 절 앞에서 끝난다
    text = fs.section_plain(body)
    assert text == "El plato típico es el salmorejo y el rabo de toro.\nDulces.\nEl pastel."  # 틀·참조·표·사진 모음은 빠진다
    assert fs.find_section(wiki, ("comer",), first=True) is None
    voy = "== Comercio ==\nTiendas.\n== Comer y beber ==\nTapas en el centro.\n== Dormir ==\nHoteles."
    assert fs.find_section(voy, ("comer",), first=True) == ("Comer y beber", "\nTapas en el centro.\n")  # 낱말로 견주므로 "Comercio"는 잡지 않는다
    assert fs.find_section("== Dónde comer ==\nBares.", ("comer",), first=True) is None  # 가이드의 먹거리 절은 첫 낱말이 Comer다
    assert fs.find_section("== Economía ==\n=== Cocina tradicional ===\nMigas.", ("gastronomia", "cocina"))[0] == "Cocina tradicional"
    assert fs.find_section("== Cultura y gastronomía ==\nMigas.", ("gastronomia", "cocina"))[0] == "Cultura y gastronomía"
    assert fs.find_section("== Fiestas y certámenes gastronómicos ==\nFeria.", ("gastronomia", "cocina")) is None  # 축제 목록은 요리 절이 아니다
    assert fs.find_section("== Gastronomía{{Cita web|url=x}} ==\nPescado.", ("gastronomia", "cocina"))[0] == "Gastronomía"  # 제목에 붙은 틀은 뺀다
    assert fs.section_plain("x" * 9000, 8000) == "x" * 8000


def test_food_sections_targets_and_api_response():
    from pipeline.e1 import food_sections as fs
    cities = [{"id": "Q2", "dest": {"rank": 1}, "n": {"es": "Córdoba"}, "wiki": {"es": "Córdoba (España)"}}, {"id": "Q1", "dest": {"rank": 2}, "n": {"es": None}, "wiki": {"es": "Elche"}},
              {"id": "Q3", "dest": {"rank": 3}, "n": {"es": "Sevilla"}, "wiki": {"es": "Sevilla"}}, {"id": "Q4", "n": {"es": "Pueblo"}, "wiki": {"es": "Pueblo"}}, {"id": "Q5", "dest": {"rank": 9}, "n": {}, "wiki": {}}]
    assert fs.targets(cities, ["Q3"]) == [("Q1", {"eswiki": "Elche", "esvoy": "Elche"}), ("Q2", {"eswiki": "Córdoba (España)", "esvoy": "Córdoba"}), ("Q5", {})]  # 여행지만, 이미 있는 곳은 빼고 ID 순
    data = {"query": {"normalized": [{"from": "elche", "to": "Elche"}], "redirects": [{"from": "Elche", "to": "Elche/Elx"}],
                      "pages": {"1": {"title": "Elche/Elx", "revisions": [{"revid": 77, "slots": {"main": {"*": "== Comer ==\nArroz."}}}]}, "-1": {"title": "Nada", "missing": ""}}}}
    assert fs.parse_revisions(data) == {"elche": ("Elche/Elx", 77, "== Comer ==\nArroz.")}  # 요청한 제목으로 되돌린다. 없는 문서는 빠진다
    assert fs.parse_revisions({}) == {}
