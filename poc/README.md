# PoC 스크립트

2단계 활용 가능한 데이터 정의(T-006)의 PoC 스크립트. 설계와 결과는 `docs/02-data-sources.md`, `docs/02-poc-results.md`에 있다.

## 실행 환경

- Python 3.13. 패키지는 저장소 밖의 가상환경에 설치한다. `python3 -m venv <경로> && <경로>/bin/pip install -r poc/requirements.txt`
- 스크립트는 `<경로>/bin/python -I poc/<스크립트>.py`로 격리 실행한다.
- 다운로드한 원시 데이터는 저장소 밖 전용 디렉터리에 둔다. 저장소에는 커밋하지 않는다(D-016). 커밋하는 것은 스크립트, 요약 수치, 검수 표본이다.

## 외부 호출 규칙

- User-Agent는 `Trip01-PoC/0.1 (https://github.com/assuii0311-dot/Trip---01)`.
- 동시 요청 1개. 초당 1회 이하. 429 응답은 Retry-After만큼 기다린 뒤 재시도.
- 경로 계산 공개 서버(OSRM, FOSSGIS, Transitous)는 합계 500건 이하의 표본 요청만.
- 대량 수집은 API가 아니라 덤프와 추출본 파일로 한다.

## 스크립트

| 파일 | 단계 | 내용 |
|---|---|---|
| check_sources.py | A | 후보 소스 접속과 크기 확인. 본문은 읽지 않는다 |
| wikidata_collect.py | B | Wikidata SPARQL 분할 조회. counts(건수), collect(수집), collect-one(단일 클래스) 모드 |
| wikidata_heritage.py | B | 문화유산 지정(P1435) 항목을 지정 종류와 위도 띠로 쪼개어 조회하고 라벨은 묶음 조회 |
| wikidata_coverage.py | B | Wikidata 수집 결과를 합쳐 중복 제거 후 필드 커버리지와 지자체 인구 분포 집계 |
| wikivoyage_parse.py | B | Wikivoyage 덤프에서 국가 하위 문서와 목록 추출. 영문과 스페인어 템플릿 설정 포함 |
| osm_extract.py | B | OSM 추출본에서 여행 관련 장소 추출과 필드 커버리지 집계 |
