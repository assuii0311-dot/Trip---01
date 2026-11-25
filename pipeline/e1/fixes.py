"""E1 보정 표(E1 4절 17항, D-066): 규칙으로 가릴 수 없는 개별 오류를 장소 ID별로 고친다.

파일(pipeline/e1/fixes.json): {"format": "trip01-e1-fixes", "version": 1, "fixes": [항목]}
항목: {"id": 장소 ID, "action": 조치, "why": 근거, "date": 확인한 날짜, ...}
- drop: 장소를 뺀다(없어진 곳, 장소가 아닌 것).
- detach: 설명의 출처를 뗀다. "src"(wikipedia | wikivoyage | wikidata)와 선택 "lang"에 맞는 desc 항목을 지운다. wikipedia를 떼면 links의 그 문서도 지운다.
  Wikidata 항목이 다른 대상의 글에 이어져 있을 때 쓴다(장소는 남는다).
- name: 이름을 바로잡는다. "set": {필드: 값 또는 null(지움)}. 필드는 local, es, en, ko, ca, eu, gl.
- coord: 좌표를 바로잡는다. "lat", "lon"과 그 좌표의 출처 "cs"(osm | wikidata | wikivoyage). 지도 요소의 태그가 같은 이름의 다른 곳을 가리킬 때 쓴다.
  도시 귀속 전에 적용한다(통합 생성이 그 순서로 부른다).
사람이 확인해 적는 표다. 줄마다 근거(why)와 날짜(date)가 있어야 한다. 순수 함수뿐이며 테스트는 pipeline/tests/test_e1.py.
"""
import copy

ACTIONS = ("drop", "detach", "name", "coord")
DETACH_SRC = ("wikipedia", "wikivoyage", "wikidata")
NAME_FIELDS = ("local", "es", "en", "ko", "ca", "eu", "gl")


def validate(fix):
    """항목의 문제 목록. 비어 있으면 쓸 수 있다."""
    out = []
    if not fix.get("id"):
        out.append("id 없음")
    if fix.get("action") not in ACTIONS:
        out.append(f"모르는 조치: {fix.get('action')}")
    if not fix.get("why") or not fix.get("date"):
        out.append("근거(why)나 날짜(date) 없음")
    if fix.get("action") == "detach" and fix.get("src") not in DETACH_SRC:
        out.append(f"모르는 출처: {fix.get('src')}")
    if fix.get("action") == "name" and (not isinstance(fix.get("set"), dict) or not fix["set"] or set(fix["set"]) - set(NAME_FIELDS)):
        out.append("set이 없거나 모르는 이름 필드가 있음")
    if fix.get("action") == "coord" and not (isinstance(fix.get("lat"), (int, float)) and isinstance(fix.get("lon"), (int, float)) and fix.get("cs") in ("osm", "wikidata", "wikivoyage")):
        out.append("lat, lon이 숫자가 아니거나 cs가 없음")
    return out


def apply(places, fixes):
    """보정 표를 적용한 (장소 목록, 보고). 입력 레코드는 바꾸지 않는다. 표에 있는데 장소 목록에 없는 ID는 보고의 unknown에 적는다."""
    report = {"drop": 0, "detach": 0, "name": 0, "coord": 0, "unknown": [], "invalid": []}
    by = {}
    for f in fixes:
        if validate(f):
            report["invalid"].append({"id": f.get("id"), "problems": validate(f)}); continue
        by.setdefault(f["id"], []).append(f)
    seen, out = set(), []
    for p in places:
        todo = by.get(p["id"])
        if not todo:
            out.append(p); continue
        seen.add(p["id"])
        if any(f["action"] == "drop" for f in todo):
            report["drop"] += 1; continue
        p = copy.deepcopy(p)
        for f in todo:
            if f["action"] == "detach":
                lang = f.get("lang")
                p["desc"] = [d for d in p.get("desc") or [] if not (d.get("src") == f["src"] and (not lang or d.get("lang") == lang))]
                if f["src"] == "wikipedia":
                    p["links"] = {k: v for k, v in (p.get("links") or {}).items() if not (k.endswith("wiki") and (not lang or k == f"{lang}wiki"))}
                report["detach"] += 1
            elif f["action"] == "name":
                for k, v in f["set"].items():
                    if v is None:
                        p["n"].pop(k, None)
                    else:
                        p["n"][k] = v
                if "ko" in f["set"]:
                    p["n"]["ko_src"] = "fix" if f["set"]["ko"] else None
                report["name"] += 1
            elif f["action"] == "coord":
                p["lat"], p["lon"], p["cs"] = round(float(f["lat"]), 6), round(float(f["lon"]), 6), f["cs"]
                report["coord"] += 1
        out.append(p)
    report["unknown"] = sorted(set(by) - seen)
    return out, report
