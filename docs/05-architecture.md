# 5단계 아키텍처와 기술 스택

- 작성일: 2026-10-25
- 상태: 기술 설계 동의 (2026-10-25, D-026). 11절 (a)~(g) 제안값 확정
- 근거: D-011(GitHub Pages 앱 + 여행별 저장소), D-012(엔진 분리), 엔진 설계 문서 7개(설계 동의), `docs/02-data-model.md`, `docs/03-mvp-scope.md`
- 제약(사실): 서버 비용 0, 유료·한도형 무료 플랜 미사용(D-001, 요구사항 9절). 개발은 이 클로드 코드 환경(Linux, Python 3.13, Node 22)에서 하고 사용자는 아이패드에서 확인한다. iOS 네이티브 빌드는 불가.

## 1. 플랫폼

- 웹 앱. GitHub Pages로 제공하고 iOS Safari와 Android Chrome에서 홈 화면에 추가할 수 있게 매니페스트를 둔다(설치형 PWA. 오프라인은 후속 범위라 서비스 워커의 캐시 범위는 앱 파일만).
- 대상 브라우저: iOS 17 이상 Safari, Android Chrome 최신 2버전, 데스크톱 Chrome·Safari·Firefox 최신. 근거: WebCrypto, ES 모듈, DecompressionStream, Web Speech API를 모두 지원하는 범위(추정. 기기 확인 필요).

## 2. 기술 스택 (결정 필요, 제안값)

| 영역 | 제안 | 이유 | 대안 |
|---|---|---|---|
| 언어 | JavaScript(ES2022 모듈) + JSDoc 타입 주석. `tsc --noEmit`로 타입 검사만 | 빌드 없이 그대로 배포. 아이패드에서 소스를 열어 읽기 쉬움 | TypeScript 빌드(번들러 필요, 배포 단계 추가) |
| UI | Preact + htm (빌드 없이 템플릿 리터럴로 컴포넌트). 두 라이브러리 파일을 저장소에 넣어 사용(vendor) | 화면 8개와 상태 공유에 컴포넌트 모델이 필요. 합계 약 15KB. 외부 CDN 의존 없음 | 프레임워크 없음(상태 관리 코드가 늘어남), Lit |
| 지도 | MapLibre GL JS(vendor) + OpenFreeMap 벡터 타일 | 사실: OpenFreeMap은 무료, 요청 수 제한 없음, 등록·API 키 없음, 상업 사용 허용(openfreemap.org 확인 2026-10-25). 후원 기반 운영 | Leaflet + OSM 래스터 타일(사용 정책상 대량·앱 배포 사용 제약, 폴백으로만) |
| 암호화 | WebCrypto(PBKDF2-SHA-256, AES-GCM 256) | 브라우저 내장, 의존성 없음(E7) | 외부 라이브러리(불필요) |
| 저장(로컬) | localStorage(Key, 토큰, 버전 SHA), IndexedDB(draft, 1등급 데이터 캐시) | D-011 로컬 최소 저장 | |
| 데이터 파일 | JSON을 gzip으로 저장(.json.gz)하고 브라우저 DecompressionStream으로 푼다 | 사실(2026-10-25 확인): GitHub Pages는 텍스트를 gzip으로 전송한다(pages.github.com 응답 content-encoding: gzip). 그래도 미리 압축해 두면 IndexedDB 캐시 크기와 전송량을 확정할 수 있다. 1등급 20MB → 약 4MB(추정) | 평문 JSON(Pages 압축에 의존. 캐시는 평문 크기) |
| 파이프라인(E1, E3 사전 계산, E5 생성 보조) | Python 3.13, 가상환경은 저장소 밖. pyosmium, pyvalhalla, requests | PoC 스크립트 재사용 | |
| 테스트 | 앱: Node 22 내장 `node --test`. 파이프라인: pytest. 흐름: Playwright(이 환경의 Chromium) | 추가 설치 최소. Playwright는 PoC에서 동작 확인 | Vitest(npm 의존) |
| 배포 | GitHub Actions의 Pages 워크플로로 `app/`와 `data/`를 올린다 | 저장소 루트를 앱으로 쓰지 않아도 됨. 공개 저장소는 Actions 무료 | 브랜치 루트 배포(저장소 구조 제약) |
| 음성 | Web Speech API(speechSynthesis, ko-KR) | R-17 요구 그대로 | |

- 외부 실행 시 호출은 세 곳뿐이다. GitHub API(E7), OpenFreeMap 타일, 구글맵 링크(사용자가 열 때). 그 외 모든 데이터는 앱 저장소의 정적 파일이다.

## 3. 저장소 구조

```
Trip---01/                       앱 저장소 (공개, GitHub Pages)
├─ app/                          정적 웹 앱 (그대로 배포)
│  ├─ index.html, manifest.json, sw.js
│  ├─ src/
│  │  ├─ engines/  e2.js e3.js e4.js e6.js  e7/{crypto,github,sync,roles}.js   엔진별 독립 모듈
│  │  ├─ data/     loader.js (gz 해제, 캐시), schema.js
│  │  ├─ ui/       screens/{s1..s8}.js  components/{card,chip,map,sheet}.js
│  │  └─ state/    store.js draft.js
│  ├─ vendor/      preact, htm, maplibre-gl (라이선스 파일 포함)
│  └─ styles/
├─ data/                         E1·E3·E5 산출 정적 파일 (.json.gz). LICENSE-DATA.md(D-025)
│  ├─ regions.json.gz cities.json.gz categories.json.gz attribution.json
│  ├─ places_tier1.json.gz  places_tier2/<city_id>.json.gz
│  ├─ travel/intercity.json.gz  travel/<city_id>.json.gz (도보 2km 쌍, 차량)
│  ├─ transit/<city_id>.json.gz (노선·정류장 요약, 1회권 요금)
│  └─ descriptions/<shard>.json.gz (E5 생성본, 순서대로 채움)
├─ pipeline/                     Python. e1/ e3/ e5/ 와 tests/
├─ poc/                          2단계 PoC (유지)
├─ docs/
├─ tests/app/                    node --test
└─ .github/workflows/pages.yml
```

- 여행 저장소(사용자가 만듦): `meta.json`, `trip.json.enc`, `proposals/*.json.enc`(E7 3절).
- 파일 크기: GitHub 파일 100MB, 저장소 권장 1GB 이하(사실). 2등급 도시별 분할과 설명 샤딩으로 파일 하나 10MB 이하를 목표로 한다(결정 필요).

## 4. 모듈 구조와 엔진 경계

- 엔진 모듈은 DOM을 모르는 순수 함수 묶음이다. 입력은 기준 데이터와 여행 데이터 객체, 출력은 설계 문서 3절의 구조. UI는 엔진을 호출만 한다.
- 의존 방향: ui → state → engines → data. engines끼리는 E4 → E3, E6 → E3·E4 결과만 참조하고 역방향은 없다.
- E1, E3 사전 계산, E5 생성은 파이프라인(Python)이고 앱에는 결과 파일만 들어간다. 앱 쪽 e3.js는 사전 계산 조회와 직선 추정만 한다.
- 각 엔진 모듈은 자체 테스트 파일과 PoC 표본에서 뽑은 고정 입력(fixture)을 가진다(D-012).

## 5. 데이터 적재와 캐싱

| 데이터 | 적재 시점 | 캐시 | 크기(추정) |
|---|---|---|---|
| regions, cities, categories, attribution | 앱 시작 | HTTP 캐시 + IndexedDB(버전 키) | 1~2MB gz |
| places_tier1 | 앱 시작 뒤 배경 로드 | IndexedDB. 데이터 갱신 버전이 바뀌면 교체 | 약 4MB gz |
| places_tier2/<city> | 도시 선택 시 | IndexedDB 도시별 | 도시당 0.1~3MB gz |
| travel, transit | 도시 선택 시 | 동일 | 도시당 1MB 안팎 |
| descriptions | 장소 상세 열 때 샤드 단위 | IndexedDB | 샤드당 1MB 이하 |
| 지도 타일 | 화면 이동 시 | 브라우저 캐시(OpenFreeMap 응답 헤더) | |

- 데이터 버전은 `attribution.json`의 갱신일로 하고, 바뀌면 IndexedDB를 비우고 다시 받는다.
- 오프라인 열람은 후속 범위다. 다만 IndexedDB 캐시 덕에 한 번 연 도시는 네트워크 없이도 목록이 보일 수 있다(보장하지 않음).

## 6. 외부 호출 계층과 폴백

| 호출 | 한도(사실) | 전략 | 폴백 |
|---|---|---|---|
| GitHub API 읽기(최신 커밋, 파일) | 사실(GitHub 문서 2026-10-25 확인): 비인증 IP당 시간 60회, 인증 5,000회, 별도로 분당 300회(비인증)·3,000회(인증) | 열 때 2회. 응답의 ETag로 조건부 요청(304의 한도 산입 여부는 문서에서 확인 못 함. 미확인) | 마지막 버전 표시 + "확인 실패", 1분 뒤 재시도 |
| GitHub API 쓰기 | 인증 5,000회 | 저장·제안·승인 때만. 유휴 2분 자동 저장 | draft 보존, 재시도 안내 |
| OpenFreeMap 타일 | 제한 없음(운영자 고지). 가용성 보장 없음 | 기본 | OSM 래스터 타일(정책: 식별 UA·Referer, 대량 금지)로 전환하고 출처 표기 교체 |
| 구글맵 링크 | 해당 없음 | 사용자가 열 때만 | 없음 |

- 완료 기준 대응: 앱이 호출하는 외부 서비스는 위 셋뿐이며, 한도가 있는 GitHub API는 열 때 2회·저장 때 1회로 제한한다. 사용자 한 명이 하루 100회를 열어도 비인증 한도 안이다(추정).

## 7. 보안

- Key와 토큰은 기기 localStorage에만 둔다. 공유 링크에 Key를 넣지 않는다(E7).
- 콘텐츠 보안 정책(CSP) 메타로 스크립트 출처를 자기 출처로 제한하고, 연결 대상은 api.github.com, raw.githubusercontent.com, tiles.openfreemap.org, tile.openstreetmap.org만 허용한다.
- 외부 스크립트 CDN을 쓰지 않는다(vendor). 라이브러리 라이선스 파일을 함께 둔다(Preact MIT, htm MIT, MapLibre BSD-3).

## 8. 테스트 전략

| 수준 | 대상 | 도구 | 기준 |
|---|---|---|---|
| 단위 | 엔진 모듈(e2, e3, e4, e6, e7 crypto·sync), 데이터 로더 | node --test, fixture는 PoC 표본 | 설계 문서 6절 품질 기준 중 자동화 가능한 것 전부 |
| 파이프라인 | E1 정규화·매칭·등급, E3 사전 계산, 파일 생성 | pytest, 소형 표본 추출본 | 재현성(두 번 실행 동일), 표본 검수 통과 |
| 흐름 | S1→S5 생성, 저장·충돌, 공유자 열람 | Playwright(이 환경 Chromium), 모의 GitHub API | 와이어프레임 검증 항목 4개 |
| 기기 | 구글맵 링크, My Maps, WebCrypto, 음성, 터치 | 사용자 기기 | 사용자 행동. 체크리스트 제공 |

## 9. 배포와 브랜치

- 개발은 지정 브랜치에서 하고, 배포 워크플로는 기본 브랜치에 병합될 때 실행한다(결정 필요: 병합 시점과 방법. 제안: 묶음 단위로 사용자가 PR 병합).
- 워크플로는 `app/`와 `data/`를 합쳐 Pages 아티팩트로 올린다. 빌드 단계 없음. 테스트(node --test, pytest)를 배포 전에 실행한다.
- 미리 보기: 사용자가 기기에서 보려면 배포가 필요하므로, 묶음 2부터는 묶음마다 배포한다.

## 10. CLAUDE.md 반영 항목 (동의 뒤 T-023)

- 기술 스택 요약(2절), 저장소 구조(3절), 코드 규칙: 엔진 모듈은 순수 함수와 자체 테스트, 외부 CDN 금지, 식별자 영어·주석 한국어(규칙 10), 데이터 파일은 파이프라인이 생성하며 손으로 고치지 않음, 커밋 전 `node --test`와 `pytest` 통과.

## 11. 결정 (D-026으로 제안값 확정)

| 번호 | 항목 | 제안값 |
|---|---|---|
| (a) | UI 라이브러리 | Preact + htm(vendor, 빌드 없음) |
| (b) | 지도 | MapLibre GL + OpenFreeMap, 폴백 OSM 래스터 |
| (c) | 언어·타입 | JavaScript + JSDoc, tsc --noEmit 검사 |
| (d) | 데이터 파일 형식 | .json.gz + DecompressionStream, 파일당 10MB 이하 |
| (e) | 테스트 도구 | node --test, pytest, Playwright |
| (f) | 배포 | Actions Pages 워크플로, 묶음마다 배포, 기본 브랜치 병합은 사용자 |
| (g) | 대상 브라우저 | iOS 17+, Android Chrome 최신 2버전 |

## 12. 미확인 사항

- GitHub API 조건부 요청(304)의 한도 미산입: 문서에서 확인하지 못했다. 구현 때 실측한다. 이 개발 환경의 API 응답 한도 헤더(15,000)는 프록시 인증 때문으로 추정되며 사용자 환경과 다르다.
- DecompressionStream과 WebCrypto의 iOS Safari 동작: 기기 확인.
- OpenFreeMap의 장기 가용성: 후원 기반. 폴백으로 대비.
- 1등급 파일 실제 크기: E1 실행 뒤 측정.
