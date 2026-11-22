"""E5 여행지 한국어 소개의 검증·내보내기 테스트(E5 4절 8항, D-032). 고정 입력은 2026-11-14 생성본의 모양을 축약한 것."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.e5 import destinations as e5  # noqa: E402

PAGE = {"lead": "Granada is a city in Granada Province in the Andalucia region of Spain.", "understand": "History. Granada has been inhabited for at least 2500 years."}
GOOD = {"id": "Q8810", "page": "Granada", "summary_ko": "그라나다는 스페인 안달루시아 지방 그라나다주에 있는 도시다. 알람브라(Alhambra)를 비롯한 유적이 있다.", "name_ko": None,
        "src_md5": e5.source_md5(PAGE), "generated": "2026-11-14"}
CITIES = [{"id": "Q8810", "n": {"ko": "그라나다", "en": "Granada"}, "dest": {"tier": 1, "rank": 6}},
          {"id": "Q492735", "n": {"ko": None, "en": "Fuengirola"}, "dest": {"tier": 3, "rank": 53}},
          {"id": "Qother", "n": {"ko": None, "en": "Other"}, "dest": None}]


def test_validate_rules():
    assert e5.validate(GOOD) == []
    assert any("200자" in p for p in e5.validate({**GOOD, "summary_ko": "가" * 199 + "다." + "다."}))
    assert "평서문으로 끝나지 않음" in e5.validate({**GOOD, "summary_ko": "그라나다는 도시입니다"})
    assert "금지어 '아름다'" in e5.validate({**GOOD, "summary_ko": "그라나다는 아름다운 도시다."})
    assert "금지어 '예약'" in e5.validate({**GOOD, "summary_ko": "알람브라는 예약이 필요하다."})
    assert "요약 없음" in e5.validate({**GOOD, "summary_ko": ""}) and "출처 문서 제목 없음" in e5.validate({**GOOD, "page": None})


def test_source_md5_changes_with_source_text():
    assert e5.source_md5(PAGE) == e5.source_md5(dict(PAGE)) and e5.source_md5(PAGE) != e5.source_md5({**PAGE, "lead": PAGE["lead"] + " New."})
    assert len(e5.source_md5({})) == 32


def test_build_exports_valid_current_destinations_only():
    fuen = {"id": "Q492735", "page": "Fuengirola", "summary_ko": "푸엔히롤라는 스페인 남부 코스타델솔(Costa del Sol)의 도시다.", "name_ko": "푸엔히롤라", "src_md5": e5.source_md5(PAGE), "generated": "2026-11-14"}
    content = [GOOD, fuen, {**GOOD, "id": "Qother"}, {**GOOD, "id": "Qgone"}]
    out, rep = e5.build(content, CITIES, {"Granada": PAGE, "Fuengirola": PAGE}, generated="2026-11-14")
    assert sorted(out["items"]) == ["Q492735", "Q8810"] and out["license"] == "CC BY-SA 4.0" and out["format"] == "trip01-e5-destinations"
    g = out["items"]["Q8810"]
    assert g["summary"].startswith("그라나다는") and g["name_ko"] is None and g["confidence"] == "보통" and g["basis"] == "text"
    assert g["sources"] == [{"title": "Granada", "lang": "en", "url": "https://en.wikivoyage.org/wiki/Granada", "license": "CC BY-SA 4.0"}]
    assert out["items"]["Q492735"]["name_ko"] == "푸엔히롤라"
    assert rep["not_destination"] == ["Qgone", "Qother"] and rep["count"] == 2 and rep["names"] == 1 and rep["missing"] == [] and rep["destinations"] == 2


def test_build_reports_stale_invalid_and_ignores_existing_names():
    stale = {**GOOD, "src_md5": "0" * 32}
    out, rep = e5.build([stale], CITIES, {"Granada": PAGE})
    assert out["items"] == {} and rep["stale"] == ["Q8810"] and rep["missing"] == ["Q492735", "Q8810"]
    out, rep = e5.build([{**GOOD, "summary_ko": "그라나다는 매력적인 도시다."}], CITIES, {"Granada": PAGE})
    assert out["items"] == {} and "금지어 '매력'" in rep["invalid"]["Q8810"]
    out, rep = e5.build([{**GOOD, "name_ko": "그라나다시"}], CITIES, {"Granada": PAGE})
    assert out["items"]["Q8810"]["name_ko"] is None and rep["name_ignored"] == ["Q8810"]  # 한국어 이름이 이미 있으면 생성 이름을 쓰지 않는다
    out, rep = e5.build([GOOD], CITIES, {})  # 출처 문서가 없어져도 낡음으로 본다
    assert rep["stale"] == ["Q8810"]


# --- 여행지 대표 음식(E5 4절 12항, D-046). 고정 입력은 2026-11-16 생성본(그라나다, 말라가)의 모양을 축약한 것.
EAT_PAGE = {**PAGE, "eat": "Granada is notable as most of its bars will serve free tapas with each drink. The most typical thing to eat is espetos, sardines grilled over a fire; and pescaíto frito."}
FOOD = {"id": "Q8810", "page": "Granada", "food_ko": "에스페토(정어리 꼬치구이), 페스카이토 프리토(생선 튀김)", "terms": ["espetos", "Pescaíto frito"], "src_md5": e5.food_md5(EAT_PAGE), "generated": "2026-11-16"}


def test_food_items_split_outside_parentheses():
    assert e5.food_items("타파스(토르티야, 감자 등), 하몬(햄)") == ["타파스(토르티야, 감자 등)", "하몬(햄)"]
    assert e5.food_items("핀초") == ["핀초"] and e5.food_items("") == []


def test_validate_food_rules():
    assert e5.validate_food(FOOD, EAT_PAGE) == [] and e5.validate_food(FOOD) == []
    assert any("60자 초과" in p for p in e5.validate_food({**FOOD, "food_ko": "가" * 61}))
    assert any("5개" in p for p in e5.validate_food({**FOOD, "food_ko": "가, 나, 다라, 마, 바"}))
    assert "문장으로 끝남(이름을 나열한 한 줄이어야 함)" in e5.validate_food({**FOOD, "food_ko": "에스페토가 알려져 있다"})
    assert "금지어 '추천'" in e5.validate_food({**FOOD, "food_ko": "에스페토 추천"})
    assert "출처 표기(terms) 없음" in e5.validate_food({**FOOD, "terms": []}) and "대표 음식 없음" in e5.validate_food({**FOOD, "food_ko": ""})
    assert "출처에 없는 표기 'paella'" in e5.validate_food({**FOOD, "terms": ["espetos", "paella"]}, EAT_PAGE)  # 출처에 없는 음식은 통과하지 못한다


def test_build_attaches_food_and_holds_back_stale_or_ungrounded_lines():
    pages = {"Granada": EAT_PAGE, "Fuengirola": PAGE}
    good = {**GOOD, "src_md5": e5.source_md5(EAT_PAGE)}
    out, rep = e5.build([good], CITIES, pages, food=[FOOD])
    assert out["items"]["Q8810"]["food"] == FOOD["food_ko"] and rep["food"] == 1 and rep["food_invalid"] == {} and rep["food_stale"] == []
    out, rep = e5.build([good], CITIES, pages, food=[{**FOOD, "src_md5": "0" * 32}])  # 먹거리 절이 바뀌면 대표 음식만 빠지고 소개는 남는다
    assert "food" not in out["items"]["Q8810"] and rep["food_stale"] == ["Q8810"] and rep["count"] == 1
    out, rep = e5.build([good], CITIES, pages, food=[{**FOOD, "terms": ["fabada"]}])
    assert "food" not in out["items"]["Q8810"] and rep["food_invalid"]["Q8810"] == ["출처에 없는 표기 'fabada'"]
    out, rep = e5.build([good], CITIES, pages, food=[{**FOOD, "id": "Q492735"}])  # 소개가 없는 여행지의 대표 음식은 붙이지 않는다
    assert rep["food_orphan"] == ["Q492735"] and rep["food"] == 0
    out, rep = e5.build([good], CITIES, pages)  # 대표 음식 파일이 없어도 예전과 같은 결과
    assert "food" not in out["items"]["Q8810"] and rep["food"] == 0


# --- 장소 설명(E5 4절 9항, D-033). 고정 입력은 2026-11-14 대표 모수(카사 바트요, 하우메 1세 기념비)의 모양을 축약한 것.
from pipeline.e1 import wikipedia_extracts as wx  # noqa: E402
from pipeline.e5 import places as pl  # noqa: E402
from pipeline.e5 import sample as sm  # noqa: E402

PLACE = {"id": "Q461371", "tier": 1, "city": "Q1492", "cat": ["heritage"], "n": {"local": "Casa Batlló", "ko": "카사 바트요"}, "pop": {"sl": 80, "en_share": 0.6},
         "desc": [{"src": "wikivoyage", "lang": "en", "page": "Barcelona/Eixample", "idx": 3, "lic": "CC BY-SA 4.0"},
                  {"src": "wikidata", "lang": "en", "text": "modernist building in Barcelona", "lic": "CC0"},
                  {"src": "wikipedia", "lang": "es", "title": "Casa Batlló", "lic": "CC BY-SA 4.0"},
                  {"src": "wikipedia", "lang": "ko", "title": "카사 바트요", "lic": "CC BY-SA 4.0"}]}
MONUMENT = {"id": "Q109983399", "tier": 1, "city": "Q662789", "cat": ["heritage"], "n": {"local": "Monument a Jaume I"},
            "desc": [{"src": "wikivoyage", "lang": "en", "page": "Salou", "idx": 1, "lic": "CC BY-SA 4.0"}]}
WV = {("Q461371", "en", "Barcelona/Eixample", 3): "Another Gaudi masterpiece.", ("Q109983399", "en", "Salou", 1): "A monument that commemorates the departure of King Jaume I's fleet."}
EXTRACTS = {("es", "Casa Batlló"): "La Casa Batlló es un edificio obra del arquitecto Antoni Gaudí."}
REC = {"id": "Q461371", "summary_ko": "카사 바트요는 안토니 가우디(Antoni Gaudí)가 고쳐 지은 건물이다.", "detail_ko": "공사는 1904년부터 1906년 사이에 이루어졌다.\n외벽은 물결처럼 굽어 있다.",
       "name_ko": None, "generated": "2026-11-14"}


def bundles():
    return {p["id"]: pl.source_bundle(p, WV, EXTRACTS) for p in (PLACE, MONUMENT)}


def test_place_source_bundle_keeps_desc_order_and_skips_missing_text():
    b = pl.source_bundle(PLACE, WV, EXTRACTS)
    assert [(s["kind"], s["lang"]) for s in b] == [("wikivoyage", "en"), ("wikidata", "en"), ("wikipedia", "es")]  # 발췌가 없는 ko 위키백과는 빠진다
    assert pl.confidence(b) == ("높음", 2) and pl.confidence(pl.source_bundle(MONUMENT, WV, EXTRACTS)) == ("보통", 1)
    assert pl.source_md5(b) == pl.source_md5(list(b)) and pl.source_md5(b) != pl.source_md5(b[:2]) and len(pl.shard_of("Q461371")) == 2


def test_place_validate_rules():
    assert pl.validate(REC) == [] and pl.validate({**REC, "detail_ko": ""}) == []
    assert any("단락 1개" in p for p in pl.validate({**REC, "detail_ko": "한 단락뿐이다."}))
    assert any("1200자 초과" in p for p in pl.validate({**REC, "detail_ko": "가" * 1199 + "다.\n둘째 단락이다."}))
    assert "상세 단락이 평서문으로 끝나지 않음" in pl.validate({**REC, "detail_ko": "첫 단락이다.\n둘째 단락"})
    assert "상세에 빈 단락" in pl.validate({**REC, "detail_ko": "첫 단락이다.\n\n셋째 단락이다."})
    assert "금지어 '입장료'" in pl.validate({**REC, "detail_ko": "입장료는 비싸다.\n둘째 단락이다."})
    assert "요약 없음" in pl.validate({**REC, "summary_ko": ""}) and any("200자 초과" in p for p in pl.validate({**REC, "summary_ko": "가" * 200 + "다."}))


def test_place_build_exports_shards_index_and_generated_names():
    b = bundles()
    content = [{**REC, "src_md5": pl.source_md5(b["Q461371"])},
               {"id": "Q109983399", "summary_ko": "하우메 1세 기념비는 함대의 출항을 기리는 기념물이다.", "detail_ko": "", "name_ko": "하우메 1세 기념비", "src_md5": pl.source_md5(b["Q109983399"]), "generated": "2026-11-14"}]
    shards, index, rep = pl.build(content, [PLACE, MONUMENT], b, generated="2026-11-14")
    item = shards[pl.shard_of("Q461371")]["Q461371"]
    assert item["detail"] == ["공사는 1904년부터 1906년 사이에 이루어졌다.", "외벽은 물결처럼 굽어 있다."] and item["confidence"] == "높음" and item["source_count"] == 2 and item["name_ko"] is None
    assert [s["url"] for s in item["sources"]] == ["https://en.wikivoyage.org/wiki/Barcelona/Eixample", None, "https://es.wikipedia.org/wiki/Casa_Batlló"]
    assert "Wikivoyage(CC BY-SA 4.0)" in item["attribution"] and "생성본" in item["attribution"]
    mon = shards[pl.shard_of("Q109983399")]["Q109983399"]
    assert mon["detail"] == [] and mon["confidence"] == "보통" and mon["name_ko"] == "하우메 1세 기념비"
    assert index["names"] == {"Q109983399": "하우메 1세 기념비"} and index["places"] == 2 and index["place_shards"] == sorted({pl.shard_of("Q461371"), pl.shard_of("Q109983399")})
    assert rep["count"] == 2 and rep["names"] == 1 and not rep["invalid"] and not rep["stale"]
    assert pl.one_liners(shards) == {"Q461371": "카사 바트요는 안토니 가우디(Antoni Gaudí)가 고쳐 지은 건물이다.", "Q109983399": "하우메 1세 기념비는 함대의 출항을 기리는 기념물이다."}
    assert pl.first_sentence("높이는 2,444m다. 돌출 높이는 995m다.") == "높이는 2,444m다." and pl.first_sentence("끝이 없는 글") == "끝이 없는 글" and pl.first_sentence("") == ""


def test_place_build_holds_back_stale_invalid_unknown_and_sourceless():
    b = bundles()
    good = {**REC, "src_md5": pl.source_md5(b["Q461371"])}
    shards, index, rep = pl.build([{**good, "src_md5": "0" * 32}], [PLACE], b)
    assert shards == {} and rep["stale"] == ["Q461371"] and index["places"] == 0
    shards, _, rep = pl.build([{**good, "summary_ko": "카사 바트요는 훌륭한 건물이다."}], [PLACE], b)
    assert shards == {} and "금지어 '훌륭'" in rep["invalid"]["Q461371"]
    shards, _, rep = pl.build([{**good, "id": "Qnone"}, good], [PLACE], {"Q461371": []})
    assert shards == {} and rep["unknown"] == ["Qnone"] and rep["no_source"] == ["Q461371"]
    shards, index, rep = pl.build([{**good, "name_ko": "바트요 저택"}], [PLACE], b)  # 한국어 이름이 이미 있으면 생성 이름을 쓰지 않는다
    assert index["names"] == {} and rep["name_ignored"] == ["Q461371"] and rep["count"] == 1


def test_sample_is_stratified_capped_and_deterministic():
    cities = [{"id": "big1", "stratum": "big"}, {"id": "big2", "stratum": "big"}, {"id": "g1", "stratum": "guide"}, {"id": "isl", "stratum": "big", "kind": "island"}]
    def place(i, city, cat="heritage", landmark=False, text=True, tier=1):
        return {"id": f"Q{i}", "tier": tier, "city": city, "cat": [cat], "pop": {"sl": 20, "en_share": 0.7} if landmark else {"sl": 2, "en_share": 0.1},
                "desc": [{"src": "wikipedia", "lang": "es", "title": f"T{i}"}] if text else [{"src": "wikidata", "lang": "es", "text": "x"}]}
    places = ([place(i, "big1", landmark=True) for i in range(5)] + [place(10 + i, "big2", cat="museum") for i in range(5)] + [place(20 + i, "g1", cat="beach") for i in range(8)]
              + [place(40, "g1", text=False), place(41, "g1", cat="cafe"), place(42, "g1", tier=2), place(43, "isl")])
    out = sm.select_sample(places, cities)
    assert out == sm.select_sample(list(reversed(places)), cities)  # 입력 순서와 무관
    by = {}
    for r in out:
        by.setdefault(r["stratum"], []).append(r["id"])
    assert len(by["big"]) == 4 and len(by["guide"]) == 2 and "small" not in by  # 도시당 2곳
    assert sum(1 for r in out if r["landmark"]) == 2 and not {"Q40", "Q41", "Q42", "Q43"} & {r["id"] for r in out}  # 글 출처 없음·비볼거리·2등급·섬 레코드는 후보가 아니다
    many = [place(100 + i, f"c{i}", cat="beach") for i in range(9)]
    out = sm.select_sample(many, [{"id": f"c{i}", "stratum": "guide"} for i in range(9)])
    assert len(out) == 4  # 한 층에서 같은 대표 범주는 4곳까지


def test_wikipedia_extract_titles_and_response_mapping():
    assert wx.titles_of([PLACE, MONUMENT], ["Q461371"]) == {"ko": ["카사 바트요"], "en": [], "es": ["Casa Batlló"]}
    data = {"query": {"normalized": [{"from": "casa batlló", "to": "Casa batlló"}], "redirects": [{"from": "Casa batlló", "to": "Casa Batlló"}],
                      "pages": {"1": {"title": "Casa Batlló", "extract": " La Casa Batlló es un edificio. "}, "-1": {"title": "Nada"}}}}
    assert wx.parse_response(data) == {"casa batlló": "La Casa Batlló es un edificio."} and wx.parse_response({}) == {}
    b = {**PLACE, "id": "Q2", "desc": [{"src": "wikipedia", "lang": "es", "title": "Alhambra"}, {"src": "wikipedia", "lang": "es", "title": "Casa Batlló"}]}
    assert wx.titles_of([PLACE, b], ["Q2", "Q461371"])["es"] == ["Alhambra", "Casa Batlló"]  # ID 목록의 순서, 중복 없음
    assert wx.next_delay(1.0, True) == 2.0 and wx.next_delay(8.0, True) == 10.0 and wx.next_delay(2.0, False) == 1.8 and wx.next_delay(1.0, False) == 1.0


# --- 전수 생성 도구(E5 4절 10항, D-038)
from pipeline.e5 import scope as sc  # noqa: E402


def test_scope_takes_top_places_per_destination_plus_highlights_once():
    def place(i, city, sl, cat="heritage", text=True, tier=1):
        return {"id": f"Q{i}", "tier": tier, "city": city, "cat": [cat], "pop": {"sl": sl, "pv": {"en": i, "es": 0}}, "desc": [{"src": "wikipedia", "lang": "es", "title": f"T{i}"}] if text else [{"src": "wikidata", "lang": "es", "text": "x"}]}
    cities = [{"id": "A", "dest": {"rank": 2}, "hl": [{"id": "Q5"}]}, {"id": "ISL", "kind": "island", "members": ["A", "B"], "dest": {"rank": 1}, "hl": []}, {"id": "B", "dest": None}, {"id": "C", "dest": None}]
    places = [place(1, "A", 50), place(2, "A", 40), place(3, "A", 30, text=False), place(4, "A", 20, cat="cafe"), place(5, "A", 1), place(6, "B", 45), place(7, "C", 99), place(8, "A", 60, tier=2)]
    out = sc.select_scope(places, cities, top=2)
    assert [(r["id"], r["dest"], r["rank"]) for r in out] == [("Q1", "ISL", 1), ("Q6", "ISL", 2), ("Q2", "A", 2), ("Q5", "A", 3)]  # 섬이 먼저 가져간 Q1은 도시 A에서 다시 나오지 않는다
    assert [r["hl"] for r in out] == [False, False, False, True] and out == sc.select_scope(list(reversed(places)), cities, top=2)
    assert [r["id"] for r in sc.select_scope(places, cities, top=3, text_only=True, exclude={"Q1"})] == ["Q6", "Q2", "Q5"]  # 글 출처 없는 Q3과 이미 만든 Q1 제외
    assert [r["id"] for r in sc.select_scope(places, cities, top=0, all_cats=True)] == ["Q1", "Q6", "Q2", "Q3", "Q5", "Q4"]  # 전부: 볼거리 먼저, 그 밖의 범주(Q4)는 뒤


def test_chunks_check_and_merge_for_bulk_generation():
    b = bundles()
    cities = [{"id": "Q1492", "n": {"ko": "바르셀로나"}}, {"id": "Q662789", "n": {"es": "Salou"}}]
    nosrc = {"id": "Qx", "tier": 1, "city": "Q1492", "cat": ["heritage"], "n": {"local": "X"}, "desc": [{"src": "wikidata", "lang": "en", "text": "building"}]}
    chunks = pl.make_chunks(["Q461371", "Qx", "Q109983399"], [PLACE, MONUMENT, nosrc], cities, {**b, "Qx": pl.source_bundle(nosrc, {}, {})}, size=1)
    assert [[c["id"] for c in ch] for ch in chunks] == [["Q461371"], ["Q109983399"]]  # 글 출처 없는 Qx는 빠지고 묶음 크기 1
    one = chunks[0][0]
    assert one["city"] == "바르셀로나" and one["name_ko_needed"] is False and one["src_md5"] == pl.source_md5(b["Q461371"]) and one["names"]["ko"] == "카사 바트요"
    assert chunks[1][0]["name_ko_needed"] is True and chunks[1][0]["city"] == "Salou"
    assert pl.is_ready(MONUMENT, set()) and not pl.is_ready(PLACE, {("es", "Casa Batlló")}) and pl.is_ready(PLACE, {("es", "Casa Batlló"), ("ko", "카사 바트요")})  # 위키백과 문서를 모두 받아 본 장소만 준비됨
    good = {**REC, "src_md5": one["src_md5"]}
    assert pl.check_part([good], chunks[0]) == []
    msgs = [m for _, m in pl.check_part([{**good, "summary_ko": "가우디가 고쳐 지은 건물이다.", "name_ko": "바트요 저택", "src_md5": "x"}, good], chunks[0])]
    assert any("이름(카사 바트요)으로 시작하지 않음" in m for m in msgs) and any("null이어야" in m for m in msgs) and any("src_md5" in m for m in msgs) and "같은 장소가 두 번 나옴" in msgs
    assert [m for _, m in pl.check_part([], chunks[1])] == ["결과가 없음(만들거나 skipped에 사유를 적어야 함)"] and pl.check_part([], chunks[1], skipped=["Q109983399"]) == []
    mon = {"id": "Q109983399", "summary_ko": "하우메 1세 기념비는 함대의 출항(1229년)을 기리는 기념물이다.", "detail_ko": "", "name_ko": None, "src_md5": chunks[1][0]["src_md5"], "generated": "2026-11-15"}
    assert [m for _, m in pl.check_part([mon], chunks[1])] == ["한글 이름 없음"]
    assert [m for _, m in pl.check_part([{**mon, "name_ko": "하우메 1세 기념비", "summary_ko": "하우메 1세 기념비는 (함대의 출항을 기리는 기념물이다."}], chunks[1])] == ["괄호 짝이 맞지 않음"]
    merged, added = pl.merge_parts([good], [("chunk_002.jsonl", [{**mon, "name_ko": "하우메 1세 기념비"}]), ("chunk_001.jsonl", [{**good, "summary_ko": "바뀐 요약이다."}])])
    assert added == 1 and [r["id"] for r in merged] == ["Q461371", "Q109983399"] and merged[0]["summary_ko"] == good["summary_ko"]  # 이미 있는 장소는 그대로


# --- 대표 음식의 다른 출처와 뜻풀이 근거(E5 4절 12항, D-061, D-062). 고정 입력은 2026-11-22 수집본(스페인어 위키백과 요리 절)의 모양을 축약한 것.
SEC_TEXT = "La gastronomía local tiene como plato más conocido el remojón granadino. También son típicas las habas con jamón y los piononos de Santa Fe."
SECTIONS = {("Q8810", "eswiki"): {"id": "Q8810", "src": "eswiki", "title": "Granada", "section": "Gastronomía", "revid": 1, "text": SEC_TEXT}}
FOOD_ES = {"id": "Q8810", "page": "Granada", "src": "eswiki", "food_ko": "레모혼 그라나디노(대구·오렌지 샐러드), 피오노노(크림 과자)", "terms": ["remojón granadino", "piononos"],
           "gloss": {"레모혼 그라나디노": "es:Remojón", "피오노노": "es:Pionono"}, "src_md5": e5.food_md5({"eat": SEC_TEXT}), "generated": "2026-11-22"}


def test_food_page_picks_the_text_by_source_kind():
    pages = {"Granada": EAT_PAGE}
    assert e5.food_page(FOOD, pages) is EAT_PAGE and e5.food_page({**FOOD, "src": "wv_en"}, pages, SECTIONS) is EAT_PAGE  # src가 없으면 영문 가이드
    assert e5.food_page(FOOD_ES, pages, SECTIONS) == {"eat": SEC_TEXT}
    assert e5.food_page(FOOD_ES, pages) is None and e5.food_page({**FOOD_ES, "src": "esvoy"}, pages, SECTIONS) is None  # 받아 둔 절이 없으면 출처 없음
    assert e5.food_page({**FOOD_ES, "page": "Granada (España)"}, pages, SECTIONS) is None  # 문서 제목이 다르면 같은 출처로 보지 않는다


def test_validate_food_source_kind_and_gloss_basis():
    page = {"eat": SEC_TEXT}
    assert e5.validate_food(FOOD_ES, page) == []
    assert "알 수 없는 출처 종류 'blog'" in e5.validate_food({**FOOD_ES, "src": "blog"}, page)
    assert "뜻풀이 근거의 음식 '하몽'이 한 줄에 없음" in e5.validate_food({**FOOD_ES, "gloss": {"하몽": "es:Jamón"}}, page)
    assert any("뜻풀이 근거 형식" in p for p in e5.validate_food({**FOOD_ES, "gloss": {"피오노노": "Pionono"}}, page))
    assert any("뜻풀이 근거 형식" in p for p in e5.validate_food({**FOOD_ES, "gloss": {"피오노노": "fr:Pionono"}}, page))
    assert "출처에 없는 표기 'paella'" in e5.validate_food({**FOOD_ES, "terms": ["paella"]}, page)  # 다른 출처에도 같은 대조를 한다


def test_build_attaches_food_from_other_sources_with_their_attribution():
    pages = {"Granada": EAT_PAGE, "Fuengirola": PAGE}
    good = {**GOOD, "src_md5": e5.source_md5(EAT_PAGE)}
    out, rep = e5.build([good], CITIES, pages, food=[FOOD_ES], sections=SECTIONS)
    it = out["items"]["Q8810"]
    assert it["food"] == FOOD_ES["food_ko"] and rep["food"] == 1 and rep["food_invalid"] == {}
    assert it["sources"][1] == {"title": "Granada", "lang": "es", "url": "https://es.wikipedia.org/wiki/Granada", "license": "CC BY-SA 4.0", "for": "food"}  # 음식의 출처 문서를 더한다
    assert "스페인어 위키백과" in out["attribution"]
    out, rep = e5.build([good], CITIES, pages, food=[FOOD], sections=SECTIONS)  # 영문 가이드에서 뽑은 음식은 출처 목록과 표기가 예전과 같다
    assert len(out["items"]["Q8810"]["sources"]) == 1 and "위키백과" not in out["attribution"]
    out, rep = e5.build([good], CITIES, pages, food=[FOOD_ES])  # 받아 둔 절이 없으면 내보내지 않는다
    assert "food" not in out["items"]["Q8810"] and rep["food_invalid"]["Q8810"] == ["출처 문서 없음"]
    changed = {("Q8810", "eswiki"): {**SECTIONS[("Q8810", "eswiki")], "text": SEC_TEXT + " Y la tortilla del Sacromonte."}}
    out, rep = e5.build([good], CITIES, pages, food=[FOOD_ES], sections=changed)  # 절이 바뀌면 그 줄만 빠진다
    assert "food" not in out["items"]["Q8810"] and rep["food_stale"] == ["Q8810"] and rep["count"] == 1
    out, rep = e5.build([good], CITIES, pages, food=[FOOD, FOOD_ES], sections=SECTIONS)  # 한 여행지에 두 줄이면 먼저 나온 줄만 쓴다
    assert out["items"]["Q8810"]["food"] == FOOD["food_ko"] and rep["food_invalid"]["Q8810"] == ["한 여행지에 대표 음식이 두 줄"]


# --- 표기 사전(E5 4절 13항, D-063). 고정 입력은 2026-11-22 조사에서 나온 사례를 축약한 것.
from pipeline.e5 import terms as tm  # noqa: E402
TERMS = tm.compile_terms({"keep": ["호안 미로", "몬주이크 공동묘지"], "terms": [
    {"to": "몬주익", "from": ["몬주이크"]}, {"to": "산츠몬주익", "from": ["산츠-몬주익"]}, {"to": "조안 ", "re": "(?<![가-힣])호안 "},
    {"to": "구시가지", "re": "구시가(?!지)"}, {"to": "주 의회", "re": "(?<![가-힣])(?:주의회|도의회)"},
    {"to": "로제스", "re": "(?<![가-힣])로사스", "city": ["Q11822"]},
    {"to": "모데르니스메", "from": ["모데르니스모", "모더니즘"], "community": ["Q5705"]}, {"to": "모데르니스모", "from": ["모데르니스메", "모더니즘"], "not_community": ["Q5705"]}]})


def test_terms_normalize_replaces_variants_and_is_idempotent():
    s = "산츠-몬주이크(Sants-Montjuïc) 지구의 구시가와 구시가지. 바르셀로나 도의회와 자치주의회. 호안 미로와 호안 로이그, 산트 호안 거리."
    out = tm.normalize(s, TERMS)
    assert out == "산츠몬주익(Sants-Montjuïc) 지구의 구시가지와 구시가지. 바르셀로나 주 의회와 자치주의회. 호안 미로와 조안 로이그, 산트 조안 거리."
    assert tm.normalize(out, TERMS) == out  # 두 번 적용해도 같다
    assert tm.normalize("몬주이크 공동묘지는 몬주이크 산에 있다.", TERMS) == "몬주이크 공동묘지는 몬주익 산에 있다."  # 보존 구절은 그대로
    assert tm.normalize("몬주이크성", TERMS, protect=["몬주이크성"]) == "몬주이크성" and tm.normalize("", TERMS) == "" and tm.normalize(None, TERMS) is None


def test_terms_fix_the_particle_when_the_final_consonant_changes():
    f = lambda s, ctx=None: tm.normalize(s, TERMS, ctx)
    assert f("몬주이크가 보인다. 몬주이크는 언덕이다. 몬주이크를 지나 몬주이크와 만나고 몬주이크로 간다.") == "몬주익이 보인다. 몬주익은 언덕이다. 몬주익을 지나 몬주익과 만나고 몬주익으로 간다."
    assert f("언덕 이름은 몬주이크다. 몬주이크라는 이름, 몬주이크였다.") == "언덕 이름은 몬주익이다. 몬주익이라는 이름, 몬주익이었다."
    assert f("몬주이크의 성, 몬주이크에 있는 몬주이크성, 몬주이크 가까이, 몬주이크(Montjuïc)") == "몬주익의 성, 몬주익에 있는 몬주익성, 몬주익 가까이, 몬주익(Montjuïc)"  # 받침과 무관한 조사와 이어지는 낱말은 그대로
    assert f("몬주이크가도, 몬주이크나무") == "몬주익가도, 몬주익나무"  # 조사처럼 보여도 낱말이 이어지면 건드리지 않는다
    cat = {"city": "Q1492", "community": "Q5705"}
    assert f("모더니즘은 양식이다. 모더니즘이 퍼졌고 모더니즘을 대표하며 모더니즘과 모더니즘으로, 이것이 모더니즘이다.", cat) == "모데르니스메는 양식이다. 모데르니스메가 퍼졌고 모데르니스메를 대표하며 모데르니스메와 모데르니스메로, 이것이 모데르니스메다."
    assert tm.josa_for("칼", "으로") == "로" and tm.josa_for("익", "로") == "으로" and tm.josa_for("Gaudí", "는") == "는" and tm.final_of("가") == 0 and tm.final_of("a") is None
    assert tm.changes_final(["몬주이크"], "몬주익") and not tm.changes_final(["에이샴플레"], "에이샴플라")


def test_terms_conditions_by_city_and_community():
    assert tm.normalize("로사스에 있는 모더니즘 건물", TERMS) == "로사스에 있는 모더니즘 건물"  # 도시·자치주를 모르면 조건이 붙은 항목은 적용하지 않는다
    assert tm.normalize("로사스에 있는 모더니즘 건물", TERMS, {"city": "Q11822", "community": "Q5705"}) == "로제스에 있는 모데르니스메 건물"
    assert tm.normalize("글로사스와 로사스, 모데르니스메", TERMS, {"city": "Q2807", "community": "Q5756"}) == "글로사스와 로사스, 모데르니스모"  # 다른 도시의 로사스는 그대로, 카탈루냐 밖은 모데르니스모
    assert tm.normalize("모데르니스메", TERMS, {"city": "Q1", "community": None}) == "모데르니스메"  # 자치주를 모르는 장소는 건드리지 않는다
    assert tm.applies({}, None) and not tm.applies({"city": {"Q1"}}, None)


def test_terms_record_changes_names_summary_and_detail_together():
    rec = {"id": "Q1", "name_ko": None, "summary_ko": "몬주이크는 바르셀로나의 언덕이다. 몬주이크성이 있다.", "detail_ko": "구시가에서 보인다."}
    fixed = tm.normalize_record(rec, TERMS)
    # 기준 데이터에 이름이 있는 장소도 요약 맨 앞의 이름까지 바뀐다(D-064). 받침이 달라지므로 조사도 맞춘다
    assert fixed["summary_ko"] == "몬주익은 바르셀로나의 언덕이다. 몬주익성이 있다." and fixed["detail_ko"] == "구시가지에서 보인다." and fixed["name_ko"] is None
    assert tm.violations(rec, TERMS) == ["summary_ko", "detail_ko"] and tm.violations(fixed, TERMS) == []
    assert tm.fixed_name("몬주이크", TERMS) == "몬주익" and tm.fixed_name("프라도 미술관", TERMS) == "프라도 미술관" and tm.fixed_name(None, TERMS) is None
    assert tm.fixed_name("몬주이크 공동묘지", TERMS) == "몬주이크 공동묘지"  # 보존 구절로 둔 이름은 그대로
    gen = tm.normalize_record({"id": "Q2", "name_ko": "지로나 몬주이크성", "summary_ko": "지로나 몬주이크성은 요새다.", "detail_ko": None}, TERMS)
    assert gen["name_ko"] == "지로나 몬주익성" and gen["summary_ko"].startswith(gen["name_ko"]) and gen["detail_ko"] is None  # 생성한 이름과 요약 첫머리는 함께 바뀐다


def test_terms_in_part_check_and_build_report():
    chunk = [{"id": "Q1", "names": {}, "name_ko_needed": True, "src_md5": "m"}]
    rec = {"id": "Q1", "name_ko": "몬주이크 탑", "summary_ko": "몬주이크 탑은 바르셀로나에 있는 탑이다.", "detail_ko": None, "src_md5": "m", "generated": "2026-11-22"}
    assert pl.check_part([rec], chunk) == []  # 사전을 주지 않으면 예전과 같다
    msgs = [m for _, m in pl.check_part([rec], chunk, (), TERMS)]
    assert len(msgs) == 2 and all(m.startswith("표기 사전과 다른 표기") for m in msgs) and "몬주익 탑" in msgs[0]
    assert pl.check_part([tm.normalize_record(rec, TERMS)], chunk, (), TERMS) == []
    # 기준 데이터에 이름이 있는 장소: 요약은 사전에 맞춘 이름으로 시작해야 한다(D-064)
    base = [{"id": "Q9", "names": {"ko": "몬주이크"}, "name_ko_needed": False, "src_md5": "m"}]
    ok = {"id": "Q9", "name_ko": None, "summary_ko": "몬주익은 바르셀로나의 언덕이다.", "detail_ko": None, "src_md5": "m", "generated": "2026-11-22"}
    assert pl.check_part([ok], base, (), TERMS) == []
    assert any("표기 사전과 다른 표기" in m for _, m in pl.check_part([{**ok, "summary_ko": "몬주이크는 바르셀로나의 언덕이다."}], base, (), TERMS))
    assert pl.check_part([{**ok, "summary_ko": "몬주이크는 바르셀로나의 언덕이다."}], base) == []  # 사전을 주지 않으면 기준 이름 그대로 본다
    assert pl.place_ctx({"city": "Q11822"}, {"Q11822": "Q5705"}) == {"city": "Q11822", "community": "Q5705"} and pl.place_ctx({}, None) == {"city": None, "community": None}


def test_place_build_reports_terms_violations_but_still_exports():
    b = bundles()
    content = [{**REC, "detail_ko": "에이샴플라의 모더니즘 건물이다.\n몬주이크가 보인다.", "src_md5": pl.source_md5(b["Q461371"])}]
    shards, index, rep = pl.build(content, [PLACE, MONUMENT], b, terms=TERMS, communities={"Q1492": "Q5705"})
    assert rep["terms"] == {"Q461371": ["detail_ko"]} and rep["count"] == 1  # 보고하되 내보내기는 한다
    fixed = [tm.normalize_record(content[0], TERMS, pl.place_ctx(PLACE, {"Q1492": "Q5705"}))]
    assert fixed[0]["detail_ko"] == "에이샴플라의 모데르니스메 건물이다.\n몬주익이 보인다."
    assert pl.build(fixed, [PLACE, MONUMENT], b, terms=TERMS, communities={"Q1492": "Q5705"})[2]["terms"] == {}
    assert pl.build(content, [PLACE, MONUMENT], b)[2]["terms"] == {}  # 사전을 주지 않으면 검사하지 않는다



def test_place_build_exports_name_fixes_for_base_names_that_differ_from_the_terms():
    hill = {**PLACE, "id": "Q1122701", "n": {"local": "Montjuïc", "ko": "몬주이크"}}
    b = {"Q1122701": pl.source_bundle(hill, {("Q1122701", "en", "Barcelona/Eixample", 3): "A hill."}, {}), **bundles()}
    rec = {"id": "Q1122701", "summary_ko": "몬주익은 바르셀로나의 언덕이다.", "detail_ko": "", "name_ko": None, "src_md5": pl.source_md5(b["Q1122701"]), "generated": "2026-11-22"}
    cat = {**REC, "src_md5": pl.source_md5(b["Q461371"])}
    shards, index, rep = pl.build([rec, cat], [hill, PLACE, MONUMENT], b, terms=TERMS, communities={"Q1492": "Q5705"})
    assert index["name_fixes"] == {"Q1122701": "몬주익"} and rep["name_fixes"] == 1 and rep["terms"] == {}  # 이름이 달라지는 곳만 적는다(카사 바트요는 없음)
    assert shards[pl.shard_of("Q1122701")]["Q1122701"]["name_ko"] is None and "Q1122701" not in index["names"]
    old = {**rec, "summary_ko": "몬주이크는 바르셀로나의 언덕이다."}
    assert pl.build([old], [hill], b, terms=TERMS)[2]["terms"] == {"Q1122701": ["summary_ko"]}  # 요약이 옛 이름으로 시작하면 알린다
    shards, index, rep = pl.build([old, cat], [hill, PLACE, MONUMENT], b)
    assert "name_fixes" not in index and rep["name_fixes"] == 0  # 사전을 주지 않으면 예전과 같은 색인
