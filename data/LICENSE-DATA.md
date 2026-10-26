# 기준 데이터 라이선스 (D-025)

이 디렉터리의 파일은 `pipeline/e1`이 공개 소스에서 생성한 파생 데이터다. 손으로 고치지 않는다. 소스별 라이선스와 표기 의무는 다음과 같고, 각 파일의 필드가 어느 소스에서 왔는지는 `attribution.json`과 레코드의 `src`, `*_src`, `desc[].src`에 적혀 있다.

| 소스 | 라이선스 | 적용 범위 | 표기 |
|---|---|---|---|
| OpenStreetMap | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) | OSM에서 온 장소·구역·공항 레코드와 좌표, 명칭, 태그. 이 데이터베이스의 OSM 파생 부분은 ODbL로 공개한다 | © OpenStreetMap contributors |
| Wikidata | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) | QID, 라벨, 설명, 분류, 유산 지정, 사이트링크 | 권장 |
| Wikivoyage (영어, 스페인어) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | `sources/` 샤드의 목록 본문, 도시 개요(`cities.json.gz`의 `wv.understand`), 영업시간·가격 참고값. 이 텍스트와 그 파생물은 CC BY-SA 4.0으로 공유한다 | Wikivoyage 기여자, 문서 링크 |
| Wikipedia | CC BY-SA 4.0 | 문서 제목(링크). 본문 발췌는 포함하지 않았다 | 위키백과 기여자 |
| Wikimedia 페이지뷰 | CC0 1.0 | 조회수 집계 | |
| Mobility Database 카탈로그 | 피드별(대부분 MITRAMS 공개 데이터 라이선스) | `cities.json.gz`의 `transit_feeds` 메타데이터 | Powered by MITRAMS |
| AMB 택시 요금표 | 공공 정보 | `cities.json.gz`의 `taxi_fare`(바르셀로나) | 출처 URL |

- 법률 자문이 아니다. 공개 서비스 단계에서 재검토한다(D-025).
- 데이터 생성일과 건수는 `attribution.json`에 있다. 생성 방법은 `pipeline/README.md`.
