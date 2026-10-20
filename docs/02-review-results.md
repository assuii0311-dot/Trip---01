# 2단계 D 단계 품질 검수 결과

- 작성일: 2026-10-20. 표본은 `docs/02-review-sample.md`(도시 6곳, 장소 36곳, P-17 장소 40곳).
- 방법(D-018): 클로드가 헤드리스 브라우저로 장소마다 구글맵 이름 검색을 1회 실행해 결과 패널의 명칭, 분류, 위치 부호(플러스 코드), 영업 상태를 읽고 자동 판정했다. 자동 판정이 ?나 X인 22곳은 저장한 화면을 클로드가 판독해 보정했다. 구글 콘텐츠는 저장하지 않았고 판정과 근거만 기록한다.
- 판정 기준: 명칭은 정규화한 유사도 0.6 이상(스페인어·카탈루냐어·바스크어와 영어의 동의어 보정), 좌표는 위치 부호 해독 좌표와 우리 좌표의 거리 150m 이하, 분류는 구글 분류어가 우리 유형(볼거리, 식당, 숙박, 자연)과 맞는지. 영업시간은 자동 판정하지 않았다.
- 사용자 확인: 아래 3절의 항목만 보시면 된다. 결과를 답장으로 주시면 이 문서에 반영한다.

## 1. 요약

| 항목 | 자동 판정 O | 판독 후 O | 판독 후 X | 판독 후 ? |
|---|---|---|---|---|
| 명칭 | 21/36 | 27/36 | 0 | 9 |
| 좌표 | 21/36 | 21/36 | 1 | 14 |
| 분류 | 20/36 | 27/36 | 0 | 9 |

- 명칭과 분류는 확인된 범위에서 틀린 것이 없다. 자동 판정의 ?는 대부분 데이터 오류가 아니라 검색 방식의 한계였다. 바스크어와 카탈루냐어 표기(Jauregia, Bergara), 목록 화면, 검색어 오해석, 구글에 없는 소규모 장소.
- 좌표는 거리가 측정된 22곳 중 21곳이 54m 이내(중앙값 11m)이고 1곳(4-2)이 3,561m 떨어져 불일치 후보다. 면적 장소(해변, 광장)와 목록 화면은 거리를 잴 수 없었다.
- 구글맵에 아예 없는 장소가 7곳(19%)이다. 대도시 2, 중소 관광 도시 2, 데이터 빈약 소도시 3. 모두 OSM에만 있거나 Wikidata와 OSM이 일치한 소규모 장소이며, 이 비율은 '가이드와 구글에 없는 현지 장소'의 규모를 보여 주지만 정확성은 확인할 수 없다.
- 영업시간은 자동 판정을 하지 않았고, 값이 있는 3곳 중 1곳(1-1)은 구글이 임시 휴업으로 표시해 우리 값이 최신이 아니다.

### 층별

| 층 | 장소 | 명칭 O | 좌표 O | 분류 O | 구글에 없음 |
|---|---|---|---|---|---|
| 대도시 | 12 | 9 | 8 | 8 | 2 |
| 중소 관광 도시 | 12 | 10 | 7 | 10 | 2 |
| 데이터 빈약 소도시 | 12 | 8 | 6 | 9 | 3 |

데이터 빈약 소도시는 명칭 O가 낮지만 틀려서가 아니라 구글에 없어서 확인하지 못한 경우가 많다.

## 2. 장소별 판정 (36곳)

| 번호 | 장소 | 층 | 유형 | 상태 | 명칭 | 좌표 | 분류 | 영업시간 | 구글 명칭 | 거리 | 비고 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1-1 | Museo de la Ciudad | 대도 | 볼거리 | 일치 | O | O | O | X | Museo de la Ciudad | 7m | 구글은 임시 휴업 표시. 우리 영업시간은 휴업을 반영하지 못함 |
| 1-2 | La Iglesia de Jesucristo de los Santos | 대도 | 볼거리 | 단일 출처 | O | O | O | - | La Iglesia de Jesucristo de lo | 11m |  |
| 1-3 | Naciones | 대도 | 식당 | 단일 출처 | ? | ? | ? | - | - | - | 구글에 항목 없음. OSM에만 있는 식당. 확인 불가 |
| 1-4 | Las Cábilas | 대도 | 식당 | 단일 출처 | O | O | O | - | Bar Las Cabilas | 13m |  |
| 1-5 | Hostal Golden Torrejón | 대도 | 숙박 | 단일 출처 | O | O | O | - | Golden Torrejon | 43m |  |
| 1-6 | Parque de las Veredillas | 대도 | 자연 | 일치 | O | O | O | - | Veredillas Park | 41m |  |
| 2-1 | Humilladero de la Virgen del Mar | 대도 | 볼거리 | 일치 | ? | ? | ? | - | via A-4 | - | 구글이 검색어를 경로 검색으로 오해석(Humilladero를 말라가의 마을로 인식). 좌표 핀으로 확인 필요 |
| 2-2 | Burbuja de salvamento | 대도 | 볼거리 | 단일 출처 | ? | ? | ? | - | - | - | 구글에 항목 없음. OSM의 조형물로 추정. 확인 불가 |
| 2-3 | Café Centro Botín | 대도 | 식당 | 일치 | O | O | O | ? | El Muelle | 5m | 구글 현재 명칭 El Muelle, 부제 El Café Centro Botín. 같은 장소(5m). 영업시간은 사용자 확인 |
| 2-4 | Restaurante del Hotel Hoyuela | 대도 | 식당 | 단일 출처 | O | O | ? | - | Hotel Hoyuela | 14m | 구글에는 Hotel Hoyuela(호텔)만 있고 부속 식당 항목 없음. 호텔 식당이면 분류는 맞음 |
| 2-5 | Boutique Las Brisas | 대도 | 숙박 | 일치 | O | O | O | - | Hotel Boutique Las Brisas | 3m |  |
| 2-6 | Playa de la Magdalena | 대도 | 자연 | 일치 | O | ? | O | - | Playa de la Magdalena | - | 해변은 면적 장소라 위치 부호 없음. 화면상 같은 해변으로 보임 |
| 3-1 | Castell de Petrés | 중소 | 볼거리 | 일치 | O | O | O | - | Castell de Petrés | 13m |  |
| 3-2 | plaza del Distrito | 중소 | 볼거리 | 단일 출처 | O | ? | O | - | Plaça del Districte | - | 구글 Plaça del Districte(광장). 위치 부호 없음. 화면상 사군토 시내 |
| 3-3 | Temple de Diana | 중소 | 식당 | 일치 | O | O | O | - | Restaurant El Temple de Diana | 2m |  |
| 3-4 | Bar Restaurante El Llorer | 중소 | 식당 | 단일 출처 | O | O | O | ? | Bar Restaurant El Llorer | 10m | 영업시간은 사용자 확인(구글: Closed · Opens 8 AM Wed) |
| 3-5 | Sensity Vent de Mar | 중소 | 숙박 | 단일 출처 | O | O | O | - | Hotel Vent de Mar | 21m |  |
| 3-6 | Alt de la Ponera | 중소 | 자연 | 단일 출처 | ? | ? | ? | - | Carrer Alt de la Ponera | - | 구글에는 같은 이름의 도로(Carrer)만 있고 봉우리 항목 없음. OSM의 봉우리. 확인 불가 |
| 4-1 | Sant Baldiri de Taballera | 중소 | 볼거리 | 일치 | O | O | O | - | Sant Baldiri de Taballera | 13m |  |
| 4-2 | Sant Salvador de Verdera castle ruins | 중소 | 볼거리 | 단일 출처 | O | X | O | - | Castell de Verdera (Sant Salva | 3561m | 구글 Castell de Verdera는 우리 좌표에서 3,561m 떨어짐. 우리 좌표가 능선 전체의 평균일 가능성. 사용자 확인 필요 |
| 4-3 | La Tina | 중소 | 식당 | 일치 | O | O | O | - | Hostal Restaurant La Tina | 6m | 구글 Hostal Restaurant La Tina. 숙박과 식당 겸업이라 식당 분류도 맞음 |
| 4-4 | Xiri Platja | 중소 | 식당 | 단일 출처 | O | ? | O | - | - | - | 구글 목록의 Xiringuito de la playa(해변 칵테일 바)가 같은 업소로 보임. 거리 측정 불가 |
| 4-5 | Porto Cristo | 중소 | 숙박 | 일치 | O | O | O | - | Hotel Spa PORTO CRISTO | 7m |  |
| 4-6 | el Torrelló | 중소 | 자연 | 일치 | ? | ? | ? | - | - | - | 구글에 항목 없음. Wikidata와 OSM이 일치한 소지명(언덕). 확인 불가 |
| 5-1 | Jarola jauregia | 데이 | 볼거리 | 일치 | O | O | O | - | Palacio Cabo de Armería Jarola | 12m | 바스크어 Jauregia = 궁전. 구글 Palacio Cabo de Armería Jarola, 12m |
| 5-2 | Bergarako Jauregia | 데이 | 볼거리 | 단일 출처 | O | ? | O | - | - | - | Bergara = Vergara. 구글 목록에 Palacio de Vergara(역사 명소) 있음. 거리 측정 불가 |
| 5-3 | Hiru Ostatua | 데이 | 식당 | 단일 출처 | O | O | O | - | Hiru Ostatua | 10m |  |
| 5-4 | Hiru Iturri | 데이 | 식당 | 단일 출처 | O | O | O | - | HIRU ITTURRI OSTATUA | 10m |  |
| 5-5 | Trinkete Antxitonea | 데이 | 숙박 | 단일 출처 | O | O | O | - | HOSTAL ANTXITONEA | 2m |  |
| 5-6 | Autrin | 데이 | 자연 | 일치 | O | ? | O | - | - | - | 구글 목록에 Monte Autrin(봉우리) 있음. 거리 측정 불가 |
| 6-1 | Castilfrío | 데이 | 볼거리 | 단일 출처 | ? | ? | ? | - | - | - | 구글에는 30km 떨어진 동명 마을 Castilfrío de la Sierra만 있음. 우리 항목은 다른 대상일 가능성. 확인 불가 |
| 6-2 | Ermita de San José | 데이 | 볼거리 | 단일 출처 | ? | ? | ? | - | - | - | 구글에 이 마을의 Ermita de San José 없음(다른 지역의 동명 예배당만). OSM에만 있는 예배당. 확인 불가 |
| 6-3 | Restaurante Villabamba | 데이 | 식당 | 단일 출처 | O | O | O | - | Restaurant Villabamba | 15m |  |
| 6-4 | Pololo | 데이 | 식당 | 단일 출처 | ? | ? | ? | - | - | - | 구글에 항목 없음(부분 일치만). 확인 불가 |
| 6-5 | Hostal Cebollera | 데이 | 숙박 | 단일 출처 | O | ? | O | - | - | - | 구글 목록에 Hotel rural Cebollera와 CEBOLLERA HR 있음. 같은 숙소로 보임. 거리 측정 불가 |
| 6-6 | la Pista | 데이 | 자연 | 단일 출처 | ? | O | O | - | Sports Field | 54m | 구글 Sports Field(운동장) 54m. 이름이 일반명사라 명칭 판정 보류. 분류와 위치는 맞음 |

## 3. 사용자 확인이 필요한 항목

아래 항목만 확인해 주세요. 검수표의 '이름으로 찾기'와 '좌표 핀' 링크를 쓰시면 됩니다.

| 번호 | 장소 | 확인할 것 | 클로드 판독 |
|---|---|---|---|
| 4-2 | Sant Salvador de Verdera castle ruins | 좌표 핀이 실제 성터인지. 구글 핀과 3.5km 차이 | 우리 좌표 오류 가능성 큼 |
| 2-1 | Humilladero de la Virgen del Mar | 좌표 핀에 작은 예배소(humilladero)가 있는지 | 검색 오해석으로 미확인 |
| 1-1 | Museo de la Ciudad | 우리 영업시간 대 구글의 임시 휴업 | 우리 값이 오래됨 |
| 3-4 | Bar Restaurante El Llorer | 영업시간이 맞는지 | 미확인 |
| 2-4 | Restaurante del Hotel Hoyuela | 호텔 안 식당이 실제로 있는지 | 호텔 부속 식당으로 추정 |
| 6-1 | Castilfrío (Valdeavellano 근처) | 좌표 핀에 무엇이 있는지 | 동명 마을과 혼동 가능 |
| 3-6 | Alt de la Ponera | 좌표 핀이 봉우리인지 | 구글에 봉우리 항목 없음 |

구글에 없는 나머지 장소(1-3, 2-2, 4-6, 6-2, 6-4)는 구글로는 확인할 수 없으므로 보류합니다. 보고 싶으시면 좌표 핀으로 주변을 보시면 됩니다.

## 4. 도시 6곳

| 도시 | 층 | 구글 명칭 | 영문 위키백과 | 한국어 위키백과 | 판정 |
|---|---|---|---|---|---|
| Torrejón de Ardoz | 대도시 | Torrejón de Ardoz | Torrejón de Ardoz | 토레혼데아르도스 | 요약 출처 일치 |
| Santander | 대도시 | Santander | Santander, Spain | 산탄데르 (스페인) | 요약 출처 일치 |
| Sagunto | 중소 관광 도시 | Sagunt | Sagunto | 사군토 | 요약 출처 일치 |
| Puerto de la Selva | 중소 관광 도시 | El Port de la Selva | El Port de la Selva | 없음 | 요약 출처 일치 |
| Baztán | 데이터 빈약 소도시 | Baztan | Baztan, Navarre | 없음 | 요약 출처 일치 |
| Valdeavellano de Tera | 데이터 빈약 소도시 | Valdeavellano de Tera | Valdeavellano de Tera | 없음 | 요약 출처 일치 |

여섯 도시 모두 구글 명칭과 위키백과 문서가 같은 도시를 가리킨다. 한국어 문서는 대도시 2곳과 Sagunto에만 있다.

## 5. P-17 현지 관심도 대리 지표

스페인어 조회 비중 상위 10곳과 하위 10곳의 구글 분류와 리뷰 수다. 리뷰 수는 참고용이며 저장하지 않는다.

### Madrid

| 구분 | 장소 | en | es | es 비중 | 구글 분류 | 리뷰 수 |
|---|---|---|---|---|---|---|
| 상위 | estación de Atocha-Cercanías | 0 | 1,109 | 1.0 | - | - |
| 상위 | iglesia de la Santa Cruz | 0 | 561 | 1.0 | Catholic church | 2,802 |
| 상위 | Hotel Palace | 0 | 676 | 1.0 | Hotel | 4,904 |
| 상위 | Museo de Historia de Madrid | 0 | 597 | 1.0 | Local history museum | 11,120 |
| 상위 | Palacio de Zurbano | 0 | 967 | 1.0 | Tourist attraction | 152 |
| 상위 | Parque del Retiro | 178 | 5,685 | 0.97 | Park | 216,868 |
| 상위 | Casa de las Siete Chimeneas | 54 | 1,061 | 0.95 | Historical landmark | 484 |
| 상위 | Ermita de la Virgen del Puerto | 33 | 511 | 0.94 | Chapel | 1,371 |
| 상위 | iglesia de Santa Bárbara | 117 | 1,337 | 0.92 | Catholic church | 1,968 |
| 상위 | iglesia de San Martín | 45 | 472 | 0.91 | Church | 4.5 stars 314 |
| 하위 | Real Armería de Madrid | 598 | 275 | 0.32 | War museum | 823 |
| 하위 | Sobrino de Botín | 2,741 | 1,288 | 0.32 | Spanish restaurant | 17,160 |
| 하위 | plaza de España | 1,292 | 678 | 0.34 | - | - |
| 하위 | Museo Nacional Centro de Arte Reina  | 5,591 | 3,276 | 0.37 | Art museum | 72,352 |
| 하위 | Museo del Prado | 14,055 | 8,710 | 0.38 | Art museum | 157,574 |
| 하위 | Museo Nacional Thyssen-Bornemisza | 5,229 | 3,360 | 0.39 | Art museum | 48,538 |
| 하위 | Palacio Real de Madrid | 15,034 | 10,723 | 0.42 | Castle | 134,677 |
| 하위 | plaza de Cibeles | 3,065 | 2,353 | 0.43 | - | - |
| 하위 | Puerta del Sol | 5,788 | 4,317 | 0.43 | - | - |
| 하위 | Horcher (Madrid) | 327 | 262 | 0.44 | Restaurant | 722 |

### Barcelona

| 구분 | 장소 | en | es | es 비중 | 구글 분류 | 리뷰 수 |
|---|---|---|---|---|---|---|
| 상위 | A Rafael Casanova | 0 | 2,071 | 1.0 | Monument | 349 |
| 상위 | Casa Milá | 0 | 4,734 | 1.0 | Heritage building | 115,002 |
| 상위 | Casa Comalat | 0 | 864 | 1.0 | Heritage building | 700 |
| 상위 | Fossar de les Moreres | 827 | 3,258 | 0.8 | Historical landmark | 873 |
| 상위 | Palacio Real Mayor de Barcelona | 722 | 2,113 | 0.75 | restaurant | 4.7 stars 600 |
| 상위 | Palacio de Albéniz | 306 | 884 | 0.74 | Tourist attraction | 774 |
| 상위 | Palacio de la Virreina | 161 | 409 | 0.72 | Museum | 2,605 |
| 상위 | basílica de la Merced | 481 | 1,024 | 0.68 | Basilica | 2,770 |
| 상위 | Barcelona-Estación de Francia | 407 | 881 | 0.68 | Train station | 1,467 |
| 상위 | Casa de les Punxes | 654 | 1,392 | 0.68 | Historical landmark | 6,357 |
| 하위 | Disfrutar | 2,738 | 0 | 0.0 | Fine dining restaurant | 3,838 |
| 하위 | Templo Expiatorio de la Sagrada Fami | 157,321 | 22,345 | 0.12 | Basilica | 336,745 |
| 하위 | Museo Picasso de Barcelona | 3,003 | 547 | 0.15 | Art museum | 40,558 |
| 하위 | Catedral de Santa Eulalia de Barcelo | 11,056 | 3,069 | 0.22 | Cathedral | 85,599 |
| 하위 | La Rambla | 6,767 | 1,875 | 0.22 | - | 10,446 |
| 하위 | Pabellón alemán, Barcelona | 5,136 | 1,782 | 0.26 | - | 4.5 stars 3,775 |
| 하위 | Estadio Olímpico Lluís Companys | 31,096 | 10,661 | 0.26 | Stadium | 25,967 |
| 하위 | Casa Batlló | 17,504 | 6,386 | 0.27 | Historical landmark | 221,453 |
| 하위 | Fundación Joan Miró | 1,074 | 388 | 0.27 | Modern art museum | 15,102 |
| 하위 | Monumento a Colón | 2,754 | 1,235 | 0.31 | Sculpture | 53,666 |

### 클로드의 판독

- 하위(스페인어 비중 낮음)는 두 도시 모두 해외 관광객이 몰리는 대표 명소다. 프라도, 레이나 소피아, 티센, 왕궁, 보틴 식당, 사그라다 파밀리아, 피카소 미술관, 대성당, 람블라, 카사 바트요, 미로 재단, 콜럼버스 기념탑.
- 상위(스페인어 비중 높음)는 동네 성당, 기차역, 지역사 박물관, 호텔, 작은 궁전과 유산 건물처럼 해외 인지도가 낮은 곳이다. 레티로 공원은 영어 조회수 178이 비정상적으로 낮아 영문 문서 제목 대응 오류로 추정한다.
- 해석: 이 지표는 '현지인이 선호하는 곳'을 직접 고르지는 못하지만 '해외에 덜 알려진 곳'을 걸러내는 데는 쓸 수 있다. 대표 명소와 그 밖의 장소를 나누는 보조 신호로 쓰고, 한 달 치가 아니라 여러 달 평균과 영문 제목 대응 검증이 필요하다. 유지 여부는 F 단계에서 결정한다.
- 사용자 판단: 상위는 현지 선호로 보이는가 [  ]  하위는 해외 관심으로 보이는가 [  ]  비고: 

## 6. 발견 사항과 다음 단계 반영

- 좌표: 웨이의 구성 노드 평균으로 잡은 좌표가 긴 능선 같은 객체에서 크게 어긋날 수 있다(4-2). E1 설계에서 폴리곤 중심점 계산으로 바꾼다.
- 명칭: 바스크어와 카탈루냐어 지역은 OSM name이 현지어라 스페인어 명칭과 다르다. 명칭 병기(R-20)에서 name:es와 name:ca, name:eu를 함께 다뤄야 한다.
- 영업시간: 보유율이 낮을 뿐 아니라 있는 값도 휴업 등 변동을 반영하지 못한다(1-1). E4에서 영업시간을 확정값이 아니라 참고값으로 다루고 사용자 확인을 요구하는 방향이 맞다.
- 구글에 없는 소규모 장소가 19%다. 이 장소들은 제품에서 '검증되지 않은 장소'로 표시하거나 추천 가중치를 낮추는 규칙이 필요하다(E2).
- 분류: 숙박과 식당 겸업(4-3), 호텔 부속 식당(2-4)처럼 한 장소가 두 유형인 경우가 있어 단일 분류보다 복수 태그가 맞다(E1).
- 검수 방법: 구글 이름 검색은 검색어에 마을 이름이 들어가면 경로 검색으로 오해석될 수 있고, 면적 장소는 위치 부호가 없다. 자동 검수를 다시 쓰려면 좌표 핀 조회를 병행해야 한다.