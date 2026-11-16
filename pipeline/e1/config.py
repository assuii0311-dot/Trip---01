"""E1 파이프라인 설정. 상위 범주, 소스별 대응표, 임계값, 등급 규칙 (docs/engines/E1-data-pipeline.md, D-023)."""
import re


# 상위 범주 12개 (D-023). 키는 코드 식별자, 값은 한국어 이름
CATEGORIES = {
    "heritage": "유적·기념물", "religious": "종교 건축", "museum": "박물관·미술관", "nature": "자연·전망",
    "park": "공원·정원", "beach": "해변", "square": "광장·거리", "market": "시장·쇼핑",
    "restaurant": "식당", "cafe": "카페·바", "lodging": "숙박", "activity": "체험·공연",
}
# 범주의 뜻(입력 화면의 범주 설명). 아래 대응표(OSM 태그, Wikidata 클래스, Wikivoyage 유형)에서 그 범주로 들어가는 것을 풀어 쓴 것이다. 대응표를 바꾸면 함께 고친다
CATEGORY_DESC = {
    "heritage": "성, 궁전, 유적, 성문과 성벽, 탑, 옛 다리, 기념물과 동상, 시청 같은 역사적 건물. 다른 범주에 들지 않는 문화재와 가이드의 일반 볼거리도 여기에 든다",
    "religious": "성당, 대성당, 수도원, 예배당, 모스크, 유대교 회당",
    "museum": "박물관, 미술관, 갤러리",
    "nature": "산과 봉우리, 화산, 곶과 절벽, 폭포, 동굴, 샘, 전망대, 자연 보호 구역",
    "park": "공원, 정원, 소풍 장소",
    "beach": "해변과 해변 휴양지",
    "square": "광장, 이름난 거리, 분수",
    "market": "시장, 쇼핑센터, 가게",
    "restaurant": "식당, 패스트푸드점, 푸드코트",
    "cafe": "카페, 바, 펍, 아이스크림 가게",
    "lodging": "호텔, 호스텔, 게스트하우스, 아파트형 숙소, 캠핑장",
    "activity": "극장·영화관·공연장, 경기장, 테마파크·동물원·수족관, 와이너리, 마리나, 골프장",
}

# OSM key=value → 범주. None은 장소에서 제외(잡음 또는 다른 개체). 목록에 없는 kept 태그는 키 기본값을 쓴다
OSM_TAG_CATEGORY = {
    "tourism=museum": "museum", "tourism=gallery": "museum", "tourism=attraction": "heritage", "tourism=artwork": "heritage",
    "tourism=viewpoint": "nature", "tourism=picnic_site": "park", "tourism=theme_park": "activity", "tourism=zoo": "activity",
    "tourism=aquarium": "activity", "tourism=wine_cellar": "activity", "tourism=information": None,
    "tourism=hotel": "lodging", "tourism=guest_house": "lodging", "tourism=hostel": "lodging", "tourism=apartment": "lodging",
    "tourism=motel": "lodging", "tourism=chalet": "lodging", "tourism=camp_site": "lodging", "tourism=caravan_site": "lodging",
    "tourism=alpine_hut": "lodging", "tourism=wilderness_hut": "lodging", "tourism=camp_pitch": None,
    "historic=castle": "heritage", "historic=ruins": "heritage", "historic=monument": "heritage", "historic=memorial": "heritage",
    "historic=archaeological_site": "heritage", "historic=city_gate": "heritage", "historic=citywalls": "heritage", "historic=fort": "heritage",
    "historic=tower": "heritage", "historic=building": "heritage", "historic=manor": "heritage", "historic=palace": "heritage",
    "historic=aqueduct": "heritage", "historic=bridge": "heritage", "historic=church": "religious", "historic=monastery": "religious",
    "historic=wayside_cross": None, "historic=wayside_shrine": None, "historic=boundary_stone": None, "historic=milestone": None,
    "historic=cannon": None, "historic=stone": None, "historic=yes": "heritage",
    "amenity=place_of_worship": "religious", "amenity=restaurant": "restaurant", "amenity=fast_food": "restaurant", "amenity=food_court": "restaurant",
    "amenity=cafe": "cafe", "amenity=bar": "cafe", "amenity=pub": "cafe", "amenity=biergarten": "cafe", "amenity=ice_cream": "cafe",
    "amenity=marketplace": "market", "amenity=theatre": "activity", "amenity=cinema": "activity", "amenity=arts_centre": "activity",
    "amenity=events_venue": "activity", "amenity=casino": "activity", "amenity=nightclub": "activity", "amenity=townhall": "heritage",
    "amenity=fountain": "square", "amenity=library": None, "amenity=university": None,
    "natural=peak": "nature", "natural=volcano": "nature", "natural=cliff": "nature", "natural=cape": "nature", "natural=bay": "nature",
    "natural=spring": "nature", "natural=hot_spring": "nature", "natural=cave_entrance": "nature", "natural=waterfall": "nature",
    "natural=valley": "nature", "natural=arch": "nature", "natural=dune": "nature", "natural=glacier": "nature", "natural=saddle": "nature",
    "natural=beach": "beach", "natural=coastline": None, "natural=wood": None, "natural=water": None,
    "leisure=park": "park", "leisure=garden": "park", "leisure=nature_reserve": "nature", "leisure=stadium": "activity",
    "leisure=water_park": "activity", "leisure=marina": "activity", "leisure=golf_course": "activity", "leisure=beach_resort": "beach",
    "leisure=sports_centre": None, "leisure=swimming_pool": None, "leisure=playground": None, "leisure=pitch": None,
    "place=square": "square",
}
OSM_KEY_DEFAULT = {"tourism": "heritage", "historic": "heritage", "shop": "market", "amenity": None, "natural": "nature", "leisure": None}
# 장소가 아닌 OSM 개체 (별도 출력)
OSM_SETTLEMENT = {"city", "town", "village", "hamlet"}
OSM_DISTRICT = {"suburb", "quarter", "neighbourhood"}
OSM_TRANSIT_KEYS = {"railway", "public_transport"}
OSM_AIRPORT = ("aeroway", "aerodrome")

# Wikivoyage 유형 → 범주. see는 raw_type으로 세분
WV_TYPE_CATEGORY = {"see": "heritage", "do": "activity", "buy": "market", "eat": "restaurant", "drink": "cafe", "sleep": "lodging", "go": None, "marker": None, "listing": None}
WV_RAW_TYPE_CATEGORY = [
    ("museum", "museum"), ("museo", "museum"), ("gallery", "museum"), ("church", "religious"), ("cathedral", "religious"), ("monastery", "religious"),
    ("iglesia", "religious"), ("catedral", "religious"), ("mosque", "religious"), ("synagogue", "religious"), ("park", "park"), ("garden", "park"), ("parque", "park"),
    ("beach", "beach"), ("playa", "beach"), ("square", "square"), ("plaza", "square"), ("street", "square"), ("view", "nature"), ("nature", "nature"),
    ("mountain", "nature"), ("cave", "nature"), ("castle", "heritage"), ("palace", "heritage"), ("ruin", "heritage"), ("monument", "heritage"),
    ("market", "market"), ("mall", "market"), ("shop", "market"), ("restaurant", "restaurant"), ("cafe", "cafe"), ("bar", "cafe"), ("hotel", "lodging"),
    ("hostel", "lodging"), ("theatre", "activity"), ("theater", "activity"), ("stadium", "activity"), ("zoo", "activity"),
]

# Wikidata 클래스 → 범주. None은 장소가 아닌 개체(도시, 역, 공항)
WD_CLASS_CATEGORY = {
    "Q33506": "museum", "Q207694": "museum", "Q16970": "religious", "Q2977": "religious", "Q44613": "religious",
    "Q839954": "heritage", "Q4989906": "heritage", "Q12280": "heritage", "Q23413": "heritage", "Q16560": "heritage", "Q570116": "heritage",
    "Q15243209": "heritage", "Q39715": "heritage", "Q8502": "nature", "Q35509": "nature", "Q179049": "nature", "Q46169": "nature", "Q23397": "nature",
    "Q40080": "beach", "Q174782": "square", "Q22698": "park", "Q1107656": "park", "Q11315": "market", "Q11707": "restaurant",
    "Q483110": "activity", "Q24354": "activity", "Q43501": "activity", "Q330284": "activity",
    "Q2074737": None, "Q515": None, "Q3957": None, "Q532": None, "Q55488": None, "Q1248784": None,
}
WD_SETTLEMENT_CLASSES = {"Q2074737", "Q515", "Q3957", "Q532"}
MUNICIPALITY_SUPPLEMENT = ["Q5823"]  # 수집 질의에서 빠진 지자체(세우타, T-049). e1.wikidata_supplement가 Wikidata에서 받아 지자체 파일에 보탠다
WD_AIRPORT_CLASS = "Q1248784"
WD_STATION_CLASS = "Q55488"
WD_WORLD_HERITAGE = "Q9259"

# 매칭 임계값 (C 단계 규칙, E1 4절 4항)
R_MATCH_M = 150.0
SIM_MATCH = 0.6
R_MISMATCH_M = 500.0
SIM_MISMATCH = 0.4
TOKEN_AGREE_STRICT = 0.7   # 상업 시설(식당·카페·숙소·가게)의 이름 일치: 양쪽 각각에서 겹친 낱말의 무게 비율 중 작은 값. 추정값
SIM_STRONG = 0.8   # 이름 일치: 글자 유사도가 이 이상이면 낱말이 달라도 같은 이름으로 본다(Javier/Xabier 같은 철자 차이). 상업 시설에는 쓰지 않는다
DISTRICT_RADIUS_M = 1500.0
LODGING_CENTER_RADIUS_M = 3000.0

# 등급 (E1 4절 7항): 1등급 = Wikivoyage 수록, 유산 지정, 사이트링크 1개 이상 중 하나
TIER1_MIN_SITELINKS = 1
MAX_FILE_MB = 10

# 여행지 목록(E1 4절 14~16항, D-030). 등급은 정렬과 참고 표시용이며 값은 제안값(추정)이다
DEST_TIER_SIZES = (20, 30, 50)  # 순위 1~20위 1등급, 21~50위 2등급, 51~100위 3등급
# 사용자 검수로 채우는 수동 보정표. exclude: 목록에서 뺄 ID, include: {ID: 등급} 100위 밖이어도 넣을 것, tier: {ID: 등급} 등급 고정
DEST_OVERRIDES = {"exclude": [], "include": {}, "tier": {}}
# 취향 중심 표기: 대표 장소 상위 N곳의 범주 비중이 후보 전체의 기준 비중보다 뚜렷이 높은 범주(숙박 제외)
DEST_FOCUS_CATS = ("heritage", "religious", "museum", "nature", "park", "beach", "square", "market", "restaurant", "cafe", "activity")
DEST_FOCUS_TOP_N = 12        # 추정값
DEST_FOCUS_MIN_PLACES = 2    # 추정값: 상위 N곳 안에 그 범주가 2곳 이상
DEST_FOCUS_MIN_SCORE = 0.04  # 추정값: 비중 × ln(비중 ÷ 기준 비중)
DEST_FOCUS_MAX = 2
DEST_FOCUS_WV_BONUS = 0.7    # 추정값: Wikivoyage 수록 장소의 가중치 가산
# 대표 명소 이름(카드 표시용): 볼거리 범주를 먼저 보이고, 역은 이름으로 걸러 뺀다(장소 레코드에 역 여부가 없어 이름으로 판별. 추정)
DEST_HL_SIGHT_CATS = ("heritage", "religious", "museum", "nature", "park", "beach", "square")
DEST_HL_SKIP_NAME = re.compile(r"\b(station|estaci[oó]n|estació|geltokia)\b", re.I)

# 택시 요금표(개발 시점 데이터 입력, E6). 사실: 바르셀로나 AMB 2026-10-21 확인. 다른 도시는 입력 전
TAXI_FARES = {"Q1492": {"base_eur": 2.80, "per_km_eur": 1.35, "per_km_eur_night": 1.66, "min_eur": 8.0, "airport_eur": 4.60, "source": "taxi.amb.cat/es/usuaris/tarifes-del-taxi (2026-10-21)"}}

# 출처 표기 (P-13, D-025)
ATTRIBUTION = [
    {"source": "OpenStreetMap", "license": "ODbL 1.0", "text": "© OpenStreetMap contributors", "url": "https://www.openstreetmap.org/copyright"},
    {"source": "Wikidata", "license": "CC0 1.0", "text": "Wikidata", "url": "https://www.wikidata.org/"},
    {"source": "Wikivoyage", "license": "CC BY-SA 4.0", "text": "Wikivoyage 기여자", "url": "https://en.wikivoyage.org/"},
    {"source": "Wikipedia", "license": "CC BY-SA 4.0", "text": "위키백과 기여자", "url": "https://www.wikipedia.org/"},
    {"source": "Wikimedia pageviews", "license": "CC0 1.0", "text": "Wikimedia Analytics", "url": "https://dumps.wikimedia.org/other/pageview_complete/"},
    {"source": "Renfe", "license": "CC BY 4.0", "text": "Renfe 공개 데이터", "url": "https://data.renfe.com/"},
    {"source": "MITRAMS (NAP)", "license": "MITRAMS 공개 데이터 라이선스", "text": "Powered by MITRAMS", "url": "https://www.transportes.gob.es/"},
    {"source": "CRTM", "license": "CRTM 공개 데이터 라이선스", "text": "Consorcio Regional de Transportes de Madrid", "url": "https://www.crtm.es/"},
    {"source": "Mobility Database", "license": "피드별", "text": "MobilityData", "url": "https://mobilitydatabase.org/"},
]
