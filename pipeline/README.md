# 파이프라인 (E1 데이터 수집·정규화, 이후 E3 사전 계산·E5 생성 보조)

설계 기준: `docs/engines/E1-data-pipeline.md`(설계 동의 D-023). 실행 환경은 저장소 밖 Python 3.13 가상환경이며 패키지는 `pipeline/requirements.txt`.

## 실행 순서 (E1)

원시 데이터는 저장소 밖 `<데이터 루트>`에 둔다(D-016). PoC 단계의 수집 결과(`poc/` 스크립트 산출)를 그대로 쓴다.

```
# 0) 원시 데이터: <루트>/wikidata/*.jsonl, P1435.jsonl, sitelinks.jsonl (poc/wikidata_*.py), <루트>/osm/out/pois.jsonl (poc/osm_extract.py)
# 1) Wikivoyage 전체 필드 추출 (약 2분)
<venv>/bin/python -I pipeline/run.py e1.wikivoyage en <enwikivoyage 덤프.bz2> <루트>/e1/wv_en
<venv>/bin/python -I pipeline/run.py e1.wikivoyage es <eswikivoyage 덤프.bz2> <루트>/e1/wv_es
# 2) 행정 경계 (약 4분, 메모리 1GB)
<venv>/bin/python -I pipeline/e1/osm_boundaries.py <spain.osm.pbf> <루트>/e1/boundaries.jsonl
# 3) 라벨·설명·위키 제목 (SPARQL, 100개 묶음 초당 1회, 약 25분. 중단 후 재개 가능)
<venv>/bin/python -I pipeline/e1/wikidata_labels.py <루트>/wikidata <루트>/e1/labels.jsonl
# 4) 페이지뷰 월평균 (월간 덤프 하나당 약 40분)
<venv>/bin/python -I pipeline/run.py e1.pageviews <루트>/e1/views.jsonl <루트>/wikidata/sitelinks.jsonl <루트>/e1/labels.jsonl -- <덤프1.bz2> <덤프2.bz2> ...
# 5) 통합과 파일 생성 (전체 약 10분, 추정). --bbox S,W,N,E 로 범위를 줄여 시험할 수 있다
<venv>/bin/python -I pipeline/run.py e1.build <루트> data --labels <루트>/e1/labels.jsonl --boundaries <루트>/e1/boundaries.jsonl --views <루트>/e1/views.jsonl
```

`pipeline/run.py`는 격리 모드(`-I`)에서 패키지를 찾기 위한 실행기다.

## 산출물 (`data/`)

| 파일 | 내용 |
|---|---|
| cities.json.gz | 지자체 8,000여 건: 명칭, 좌표, 인구, 층, 행정 소속, 가이드 문서와 개요, 장소 수, 숙박 밀도, 구역, 가격대 분포, 교통 피드, 택시 요금표 |
| regions.json.gz | 자치주·주(OSM 행정 경계)와 Wikivoyage 지역 문서 |
| categories.json.gz | 상위 범주 12개와 대응표, 범주별 1등급 수와 예시 |
| places_tier1.json.gz | 1등급 장소 전체 |
| places_tier2/<city>.json.gz | 2등급 장소를 도시별로 |
| sources/<xx>.json.gz | Wikivoyage 목록 본문(설명 출처). 키 `장소ID|언어|문서|목록번호`, 샤드는 md5(장소ID)의 앞 두 자리 |
| airports.json.gz | OSM 공항 |
| attribution.json | 출처·라이선스·생성일·건수 |
| crossval_report.json | 입력 건수, 매칭 통계, 교차검증·검증·좌표 출처·도시 귀속 분포, 필드 보유율, 파일 크기 |

레코드 필드는 `docs/02-data-model.md`. 라이선스는 `data/LICENSE-DATA.md`.

## 테스트

`<venv>/bin/python -I -m pytest -q pipeline/tests`
