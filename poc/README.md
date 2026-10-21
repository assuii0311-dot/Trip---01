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
| crossval_match.py | C | Wikidata, Wikivoyage, OSM을 QID와 좌표·명칭으로 교차 매칭. 일치, 불일치, 단일 출처 판정과 숙박 밀도, 가이드 미수록 장소 |
| wikidata_sitelinks.py | C | 매칭 대상 QID의 언어별 위키 문서 존재, 라벨, 설명을 50건 묶음으로 조회. 중단 후 재개 가능 |
| crossval_sitelinks_report.py | C | 사이트링크 결과로 언어별 커버리지(P-03, P-08, P-10)와 D 단계 층별 도시 수 집계 |
| pageviews_extract.py | C | 월간 페이지뷰 덤프에서 대상 문서의 en, es, ko 조회수 추출 (P-17) |
| sample_review.py | D | 고정 난수로 층별 도시와 장소 표본을 뽑고 검수표 docs/02-review-sample.md 생성 |
| review_gmaps.py | D | 표본을 구글맵에서 이름 검색해 명칭, 좌표(플러스 코드 해독), 분류, 영업시간의 1차 판정 생성 (D-018). 허용 주소 형식만 사용, 장소당 1회 |
| routing_poc.py | E | 공개 경로 서버(OSRM 데모, FOSSGIS)에 도보·차량 표본 160건 요청. 성공률, 응답 시간, 직선 거리 대비 비율 |
| routing_local.py | E | pyvalhalla 로컬 타일로 같은 표본 쌍을 다시 계산해 공개 서버 결과와 비교. N×N 도보 행렬 성능 |
| gtfs_inspect.py | E | Renfe 정적 GTFS와 NAP 직접 다운로드 시험. 노선·정류장·운행 수, 요금 파일, 유효 기간 |
| gtfs_catalog.py | E | Mobility Database 카탈로그의 공개 주소(urls.latest)로 주요 운영사 GTFS를 받아 검사 |
| cost_poc.py | E | 비용 네 항목 확보율. Wikivoyage 가격 필드 숫자 추출과 저가·중가·고가 절, 교통 절의 금액 언급, OSM fee·charge, GTFS 요금 파일 |
| gmaps_links.py | E | 구글맵 장소·경로 링크(경유지 한도 분할)와 My Maps 가져오기용 CSV·KML 표본 생성 |

`poc/results/`에는 커밋하는 요약 수치 JSON을 둔다. `poc/results/gmaps_samples/`는 기기 확인용 링크·CSV·KML 표본이다.

## 로컬 경로 엔진(pyvalhalla) 실행 방법

- 패키지의 `valhalla_build_tiles` 파이썬 래퍼는 실행 파일을 PATH에서 찾기 때문에 실패한다. 패키지 안의 실행 파일을 직접 부른다.
  `B=<venv>/lib/python3.13/site-packages/valhalla/bin; export LD_LIBRARY_PATH=<venv>/lib/python3.13/site-packages/valhalla:<venv>/lib/python3.13/site-packages/valhalla.libs`
  `$B/valhalla_build_tiles -c valhalla.json <추출본.pbf>` (valhalla.json은 `valhalla.get_config(tile_dir=..., tile_extract="")`로 생성)
- 파이썬에서 쓸 때는 `Actor(get_config(tile_dir=<타일 디렉터리>, tile_extract=""))`. tile_extract 기본값은 tar 파일이라 비워야 한다.
