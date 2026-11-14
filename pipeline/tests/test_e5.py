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
