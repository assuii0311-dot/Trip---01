# 파이프라인 (E1 데이터 수집·정규화, 이후 E3 사전 계산·E5 생성 보조)

설계 기준: `docs/engines/E1-data-pipeline.md`(설계 동의 D-023). 실행 환경은 저장소 밖 Python 3.13 가상환경이며 패키지는 `pipeline/requirements.txt`.

## 실행 순서 (E1)

원시 데이터는 저장소 밖 `<데이터 루트>`에 둔다(D-016). PoC 단계의 수집 결과(`poc/` 스크립트 산출)를 그대로 쓴다.

```
# 0) 원시 데이터: <루트>/wikidata/*.jsonl, P1435.jsonl, sitelinks.jsonl (poc/wikidata_*.py), <루트>/osm/out/pois.jsonl (poc/osm_extract.py)
#    OSM은 스페인 추출본과 카나리아 추출본 두 개다(D-031). 카나리아는 poc/osm_extract.py <canarias.osm.pbf> <루트>/osm_canarias/out 으로 따로 뽑는다
# 1) Wikivoyage 전체 필드 추출 (약 2분)
<venv>/bin/python -I pipeline/run.py e1.wikivoyage en <enwikivoyage 덤프.bz2> <루트>/e1/wv_en
<venv>/bin/python -I pipeline/run.py e1.wikivoyage es <eswikivoyage 덤프.bz2> <루트>/e1/wv_es
# 2) 행정 경계 (약 4분, 메모리 1GB)
<venv>/bin/python -I pipeline/e1/osm_boundaries.py <spain.osm.pbf> <루트>/e1/boundaries.jsonl
<venv>/bin/python -I pipeline/e1/osm_boundaries.py <canarias.osm.pbf> <루트>/e1/boundaries_canarias.jsonl
# 3) 라벨·설명·위키 제목 (SPARQL, 100개 묶음 초당 1회, 약 25분. 중단 후 재개 가능)
<venv>/bin/python -I pipeline/e1/wikidata_labels.py <루트>/wikidata <루트>/e1/labels.jsonl
# 4) 공항(D-029)과 섬(D-030). 섬 폴리곤은 스페인 추출본과 카나리아 추출본에서 따로 뽑는다(openstreetmap.fr 스페인 추출본에 카나리아 제도가 없다)
<venv>/bin/python -I pipeline/run.py e1.airports <루트>/e1/airports_wd.jsonl
<venv>/bin/python -I pipeline/e1/osm_islands.py <spain.osm.pbf> <루트>/e1/islands_osm.jsonl            # 약 2분 30초
<venv>/bin/python -I pipeline/e1/osm_islands.py <canarias.osm.pbf> <루트>/e1/islands_osm_canarias.jsonl
<venv>/bin/python -I pipeline/run.py e1.islands <루트>/e1/islands_wd.jsonl <루트>/e1/islands_osm.jsonl <루트>/e1/islands_osm_canarias.jsonl
# 5) 페이지뷰 월평균 (월간 덤프 하나당 약 20분). 섬 문서 제목(islands_wd.jsonl)도 함께 넣는다
<venv>/bin/python -I pipeline/run.py e1.pageviews <루트>/e1/views.jsonl <루트>/wikidata/sitelinks.jsonl <루트>/e1/labels.jsonl <루트>/e1/islands_wd.jsonl -- <덤프1.bz2> <덤프2.bz2> ...
# 6) 통합과 파일 생성 (전체 약 5분). --bbox S,W,N,E 로 범위를 줄여 시험할 수 있다
<venv>/bin/python -I pipeline/run.py e1.build <루트> data --labels <루트>/e1/labels.jsonl --views <루트>/e1/views.jsonl \
  --boundaries <루트>/e1/boundaries.jsonl <루트>/e1/boundaries_canarias.jsonl --osm-extra <루트>/osm_canarias/out/pois.jsonl \
  --airports <루트>/e1/airports_wd.jsonl --islands <루트>/e1/islands_osm.jsonl <루트>/e1/islands_osm_canarias.jsonl --islands-wd <루트>/e1/islands_wd.jsonl
# 7) 여행지 목록 검수표(D-030). 검수 결과는 pipeline/e1/config.py의 DEST_OVERRIDES에 반영하고 6)을 다시 돌린다
python3 -I scripts/destinations_report.py data/cities.json.gz data/regions.json.gz data/airports.json.gz <출력.md> [data/e5/destinations.json.gz]
```

`pipeline/run.py`는 격리 모드(`-I`)에서 패키지를 찾기 위한 실행기다.

## 실행 순서 (E3 도보 쌍)

경로 타일은 추출본별로 만든다(`poc/README.md`의 로컬 경로 엔진 실행 방법). 도보 쌍은 타일마다 지역을 나눠 계산한다.

```
# 본토·발레아레스: 스페인 추출본 타일. 일부 도시만 다시 계산하려면 --cities ID,ID,...
<venv>/bin/python -I pipeline/run.py e3.intracity <스페인 타일> data/places_tier1.json.gz --out data/travel --bbox 35,-10,44.5,5
# 카나리아: 카나리아 추출본 타일
<venv>/bin/python -I pipeline/run.py e3.intracity <카나리아 타일> data/places_tier1.json.gz --out data/travel --bbox 27,-19,30,-13
```

대상 장소가 2곳 미만이 된 도시는 건너뛰되, 예전 파일이 남아 있으면 빈 쌍으로 다시 쓴다.

## 실행 순서 (E5 여행지 한국어 소개)

생성은 개발 세션에서 하고(E5 4절 2항) 결과를 `pipeline/e5/content/destinations_ko.jsonl`에 둔다. 아래 명령은 검증과 내보내기만 한다.

```
# 새로 생성했거나 출처와 다시 대조한 뒤에는 --stamp로 출처 해시를 적는다. 검증 실패나 낡은 항목이 있으면 종료 코드 1
<venv>/bin/python -I pipeline/run.py e5.destinations pipeline/e5/content/destinations_ko.jsonl data/cities.json.gz <루트>/e1/wv_en/pages.jsonl --out data/e5/destinations.json.gz [--stamp]
```

## 실행 순서 (E5 장소 한국어 설명)

생성은 개발 세션에서 하고 결과를 `pipeline/e5/content/places_ko.jsonl`에 둔다(E5 4절 9항, D-033). 위키백과 머리 문단은 저장소 밖에 받는다.

```
# 1) 대표 모수(층화 표본 30곳) 선정
<venv>/bin/python -I pipeline/run.py e5.sample data/places_tier1.json.gz data/cities.json.gz <루트>/e5/sample.json
# 2) 위키백과 머리 문단 받기(이어받기 가능)
<venv>/bin/python -I pipeline/run.py e1.wikipedia_extracts <루트>/e5/sample.json data/places_tier1.json.gz <루트>/e5/wiki_extracts.jsonl
# 3) 생성에 쓸 출처 묶음 만들기
<venv>/bin/python -I pipeline/run.py e5.places dump <루트>/e5/sample.json data/places_tier1.json.gz data/sources <루트>/e5/wiki_extracts.jsonl <루트>/e5/sample_sources.json
# 4) 검증과 내보내기. 새로 생성했거나 다시 대조한 뒤에는 --stamp로 출처 해시를 적는다. 검증 실패나 낡은 항목이 있으면 종료 코드 1
<venv>/bin/python -I pipeline/run.py e5.places build pipeline/e5/content/places_ko.jsonl data/places_tier1.json.gz data/sources <루트>/e5/wiki_extracts.jsonl --out data/e5 [--stamp]
# 전수 생성(D-038): 대상 고르기 → 발췌 받기 → 묶음 나누기 → (작업자가 GUIDE.md를 따라 부분 파일 작성) → 검사 → 병합 → 내보내기
<venv>/bin/python -I pipeline/run.py e5.scope data/places_tier1.json.gz data/cities.json.gz <루트>/e5/gen/scope.json --top 10 --text-only --exclude pipeline/e5/content/places_ko.jsonl
<venv>/bin/python -I pipeline/run.py e1.wikipedia_extracts <루트>/e5/gen/scope.json data/places_tier1.json.gz <루트>/e5/wiki_extracts.jsonl
<venv>/bin/python -I pipeline/run.py e5.places chunks <루트>/e5/gen/scope.json data/places_tier1.json.gz data/cities.json.gz data/sources <루트>/e5/wiki_extracts.jsonl <루트>/e5/gen/chunks
<venv>/bin/python -I pipeline/run.py e5.places check pipeline/e5/content/parts/chunk_001.jsonl <루트>/e5/gen/chunks/chunk_001.json
<venv>/bin/python -I pipeline/run.py e5.places merge pipeline/e5/content/places_ko.jsonl pipeline/e5/content/parts
# 검수표(생성본과 출처 원문을 나란히)
python3 -I scripts/places_review.py pipeline/e5/content/places_ko.jsonl <루트>/e5/sample_sources.json <루트>/e5/sample.json data/cities.json.gz <출력.md>
```

## 산출물 (`data/`)

| 파일 | 내용 |
|---|---|
| cities.json.gz | 지자체 8,000여 건과 섬 여행지(kind island, 소속 지자체 members): 명칭, 좌표, 인구, 층, 행정 소속, 가이드 문서와 소개 문장·개요, 장소 수, 숙박 밀도, 구역, 가격대 분포, 교통 피드, 택시 요금표. 여행지 필드(D-030): dest(참고 등급·순위·선정 근거), focus(취향 중심 범주), hl(대표 명소), island(소속 섬) |
| regions.json.gz | 자치주·주(OSM 행정 경계)와 Wikivoyage 지역 문서 |
| categories.json.gz | 상위 범주 12개와 대응표, 범주별 1등급 수와 예시 |
| places_tier1.json.gz | 1등급 장소 전체 |
| places_tier2/<city>.json.gz | 2등급 장소를 도시별로 |
| sources/<xx>.json.gz | Wikivoyage 목록 본문(설명 출처). 키 `장소ID|언어|문서|목록번호`, 샤드는 md5(장소ID)의 앞 두 자리 |
| e5/destinations.json.gz | 여행지 한국어 요약과 생성한 한글 이름(D-032). 출처 문서, 신뢰도, 생성일 포함 |
| e5/places/<xx>.json.gz | 장소 한국어 설명(D-033): 요약, 상세 단락, 생성한 한글 이름, 신뢰도, 출처 목록, 표기 문구. 샤드는 md5(장소ID)의 앞 두 자리 |
| e5/index.json | 장소 설명이 있는 샤드 목록과 생성한 한글 이름(앱이 시작할 때 읽는다) |
| e5/lines.json.gz | 장소의 한 줄 설명(요약의 첫 문장, D-039). 앱이 시작할 때 읽어 목록 카드에 쓴다 |
| airports.json.gz | IATA 코드가 있는 공항(D-029): 영문·현지어·한국어 이름, 소속 도시, 좌표, 연 이용객 |
| attribution.json | 출처·라이선스·생성일·건수 |
| crossval_report.json | 입력 건수, 매칭 통계, 교차검증·검증·좌표 출처·도시 귀속 분포, 필드 보유율, 파일 크기 |

레코드 필드는 `docs/02-data-model.md`. 라이선스는 `data/LICENSE-DATA.md`.

## 테스트

`<venv>/bin/python -I -m pytest -q pipeline/tests`
