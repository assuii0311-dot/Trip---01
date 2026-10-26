# 데이터 모델 초안

2단계 PoC 결과(`docs/02-poc-results.md`, `docs/02-poc-classification.md`)를 바탕으로 앱이 다룰 데이터의 개체, 필드, 출처를 정리한 초안이다. 확정은 E1 설계 문서(T-011)와 5단계 기술 설계에서 한다. "결정 필요"는 사용자 결정이 필요한 항목이다. 작성일 2026-10-21.

## 1. 구성 원칙

- 두 층으로 나눈다. 기준 데이터(개발 시점에 E1이 생성하는 읽기 전용 파일)와 여행 데이터(사용자가 만들고 E7이 여행 저장소에 동기화하는 파일, D-011).
- 기준 데이터의 모든 레코드는 출처와 라이선스를 갖는다(P-13). 같은 장소의 출처별 원본 값은 보존하고, 통합 값은 우선순위 규칙으로 고른다(P-14).
- 좌표 우선순위: OSM·Wikidata > Wikivoyage. 단일 출처 값은 신뢰도 표시를 둔다(review 6절).
- 분류는 복수 태그다(겸업 장소, review 6절).
- 한국어 명칭·설명은 데이터가 없으면 E5가 생성하고 생성 여부를 표시한다.

## 2. 기준 데이터 개체

### Region (지역)

| 필드 | 설명 | 출처 | 커버리지(사실) |
|---|---|---|---|
| region_id | 내부 ID | | |
| name_en, name_es, name_ko | 명칭 | Wikivoyage 지역 문서, Wikidata 라벨 | 영문 Wikivoyage 지역 59, 상위 8 |
| parent_region_id | 계층 | Wikivoyage isPartOf | 깊이 최대 5 |
| wikidata_qid, wikivoyage_page | 출처 키 | | |
| summary_sources | 요약 출처 텍스트 참조(Understand 절) | Wikivoyage | 지역·도시 491건 중 429건 |

### City (도시, 지자체)

| 필드 | 설명 | 출처 | 커버리지(사실) |
|---|---|---|---|
| city_id, wikidata_qid | 키 | Wikidata 지자체 | 8,414건 |
| name_local, name_es, name_en, name_ko | 명칭 | Wikidata 라벨, OSM place | es 99.5%, en 98.5%, ko 4.6%(인구 상위 50 도시 100%) |
| lat, lon | 중심 좌표 | Wikidata | 99.5% |
| population | 인구 | Wikidata | 8,213건 |
| region_id | 소속 지역 | Wikidata P131, Wikivoyage | 98.2% |
| wikivoyage_en, wikivoyage_es | 가이드 문서 | 사이트링크 | 영문 432 도시 중 359 연결 |
| stratum | 대도시 / 중소 관광 도시 / 데이터 빈약 소도시 / 기타 | 인구와 목록 수 기준 | 67 / 229 / 7,652 / 466 |
| lodging_density | 중심 3km 숙박 수, 구역별 숙박 수 | OSM | 중앙값 11곳 |
| price_profile | 숙박·식당 가격대 분포(저가·중가·고가 비율, 중앙값) | Wikivoyage Sleep·Eat | sleep 49%, eat 등급 56% |
| transit_feeds | 이용 가능한 GTFS 피드 목록 | Mobility Database, Renfe | 주요 도시 18건 |
| taxi_fare | 기본요금, km당, 최소 요금 | 도시 요금표(수동 입력) | 바르셀로나만 확인 |
| pageviews | 언어별 월평균 조회수 | Wikimedia 월간 덤프 | 도시 문서 대부분 |

### Place (장소)

| 필드 | 설명 | 출처 | 커버리지(사실) |
|---|---|---|---|
| place_id | 내부 ID | | 통합 후 규모는 E1에서 산정. 원천 Wikidata 133,362, OSM 646,875, Wikivoyage 목록 11,626 |
| source_keys | {wikidata: QID, osm: 유형+ID, wikivoyage: 언어+문서+목록 번호} | | |
| crossval_status | 일치 / 불일치 / 단일 출처 | C 단계 규칙 | 검수 좌표 정확도 23/36 |
| verified | 검증 여부(단일 출처이고 사이트링크·조회수 없음이면 false) | 규칙 | 구글 미존재 5/36 |
| city_id, region_id | 소속 | 좌표 → 지자체 | |
| name_local, name_es, name_ca, name_eu, name_gl, name_en | 명칭 | OSM name·name:*, Wikidata 라벨, Wikivoyage | OSM name 87.9%, en 라벨 77.9% |
| name_ko, name_ko_source | 한국어 명칭과 출처(wikidata / kowiki / generated) | Wikidata ko, 한국어 위키백과, E5 | ko 라벨 0.7% |
| lat, lon, coord_source, coord_confidence | 좌표와 출처, 신뢰도 | 우선순위 규칙 | Wikidata 94.9% |
| categories[] | 상위 범주 태그(복수) | OSM 태그·Wikivoyage 유형·Wikidata 클래스 대응표(E1) | 분류 정확도 29/36 |
| heritage | 문화유산 지정 종류 | Wikidata P1435 | 26.5% |
| opening_hours, hours_source, hours_reference_only | 영업시간(참고값) | OSM, Wikivoyage | 박물관 21.6%, 식당 15.3%, 명소 5.5% |
| price_eur, price_raw, is_free, price_tier, price_source | 입장료·가격 | Wikivoyage price, OSM fee·charge | see 31.2% 숫자, 무료 17.9% |
| description_sources[] | {출처, 언어, 텍스트 또는 참조, 라이선스} | Wikivoyage content(CC BY-SA), 위키백과 발췌, Wikidata 설명 | see 87.6% |
| description_ko_summary, description_ko_detail, generated_from | 한국어 설명(E5 생성)과 생성 근거 | E5 | 생성 전 0 |
| reservation_hint, reservation_rule | 예약 필요 추정과 적용 규칙 | E2 규칙 | 직접 데이터 2.6% |
| popularity | 사이트링크 수, 언어별 월평균 조회수, 해외 대표 명소 점수(P-17) | Wikidata, 페이지뷰 | 조회수 있는 문서 19,049 |
| links | 구글맵 좌표 링크, 명칭 검색 링크, 공식 웹사이트 | 생성, OSM website 6.8% | |
| attribution | 출처 표기 문자열 | P-13 | 전 레코드 |

### Transit (대중교통, 사다리 B 단계)

| 개체 | 필드 | 출처 | 비고 |
|---|---|---|---|
| Feed | feed_id, 운영사, 라이선스·표기 문구, 유효 기간, 요금 파일 유무, 다운로드 주소 | Mobility Database, Renfe, NAP | 복사본 유효 기간 만료 주의 |
| Stop | stop_id, 명칭, 좌표, 수단 | GTFS stops | |
| Route | route_id, 명칭, 수단(route_type), 정류장 순서, 평균 속도 | GTFS routes·trips·stop_times | 시간표 자체는 보관하지 않음(결정 필요: A 단계 채택 시 보관) |
| Fare | 요금 구간과 금액 | GTFS fare_attributes(CRTM, 메트로 빌바오) | 7/26 피드 |

### Travel (이동 시간, E3)

| 개체 | 필드 | 출처 | 비고 |
|---|---|---|---|
| RouteCache | 출발·도착 place_id, 수단(도보·차량·자전거), 거리, 시간, 계산 시점 | 로컬 경로 엔진(개발 시점 사전 계산) | 결정 필요: 사전 계산 범위(도시 안 후보 쌍 전부 vs 선택 장소만 실행 시 계산). 60×60 도보 행렬 2.2초 |
| IntercityMatrix | 도시 쌍별 차량 시간·거리, 기차 소요 시간(Renfe GTFS 최단 운행) | 로컬 엔진, GTFS | 25×25 차량 5초 |
| IslandLink | 섬 구간의 항공·페리 존재 여부와 외부 링크 | OpenFlights, OSM ferry | 시간표 없음 |

## 3. 여행 데이터 개체 (E7 동기화 대상)

| 개체 | 필드 | 비고 |
|---|---|---|
| Trip | 기간, 도시 목록, 공항, 출발·도착 시각, 인원, 여행 형태(R-02), 취향(R-03), 버전, Key 해시 | R-01 ~ R-03 |
| Selection | 선택 장소 place_id 목록, 직접 추가 장소(명칭·좌표) | R-07 |
| Day / Item | 날짜, 순서, place_id, 시작·종료 예정 시각, 이동 수단, 확인 상태(영업시간 확인 등), 메모 | R-08, R-14 |
| Lodging | 도시, 일수, 지역, 예약 정보 | R-10, R-19 |
| Proposal | 제안자, 대상, 내용, 상태(대기·승인·거절) | R-23 |
| CostEstimate | 항목별 범위와 근거 | R-26 |
| Export | KML·CSV·경로 링크 생성 기록 | R-27 |

암호화 단위와 파일 분할은 E7 설계에서 정한다(D-011).

## 4. 규모와 배포 방식 (결정 필요)

- 사실: 원천 장소 수는 통합 전 약 79만 건이다. 브라우저 앱이 전체를 한 번에 읽는 것은 비현실적이다(추정).
- 제안: 장소를 등급으로 나눈다. 1등급은 Wikivoyage 수록 또는 문화유산 지정 또는 사이트링크 보유(추정 약 6만 건), 2등급은 나머지 OSM 장소(식당·카페·상점 등)로 도시별 파일로 분할해 필요할 때 읽는다. 등급 기준과 파일 크기는 E1 설계에서 산정한다.
- 기준 데이터는 앱 저장소(GitHub Pages)에 정적 파일로 두고, 여행 데이터만 여행 저장소에 둔다(D-011).

## 5. 라이선스와 표기

| 데이터 | 라이선스 | 표기 방식(앱) |
|---|---|---|
| Wikidata | CC0 | 출처 표기 권장 |
| Wikivoyage | CC BY-SA 4.0 | 출처 링크. 파생 설명은 동일 라이선스 공유 조건 검토 필요(결정 필요) |
| OSM | ODbL | "© OpenStreetMap contributors". 파생 DB 공개 조건 검토 필요 |
| Renfe | CC BY 4.0 | 출처 표기 |
| MITRAMS(NAP) 피드 | MITRAMS 공개 데이터 라이선스 | 출처 표기 + "Powered by MITRAMS" 링크 |
| CRTM | CRTM 라이선스 | 출처 표기 |
| Wikimedia 페이지뷰 | CC0 | |
| OpenFlights | ODbL | 출처 표기 |

## 6. 미확정 사항

- 통합 장소 수와 등급 기준(E1).
- 경로 사전 계산 범위와 실행 시 계산 여부(E3). 로컬 엔진은 개발 환경에서만 돌고 앱에는 결과 파일만 들어간다(추정).
- 대중교통 A 단계 채택 여부(Transitous 결정).
- 파생 데이터의 공유 조건(Wikivoyage CC BY-SA, OSM ODbL) 적용 방식.
- 여행 데이터의 암호화 단위와 파일 분할(E7).
