"""E3 파이프라인(섬 안 차량 행렬, 도시 간 기차)의 순수 함수 테스트. 경로 엔진과 네트워크는 부르지 않는다."""
import datetime
import gzip
import json
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.e3 import intercity, island  # noqa: E402

CITIES = [{"id": "Q40846", "kind": "island", "members": ["Q3", "Q1", "Q2", "Q9"], "lat": 28.27, "lon": -16.6},
          {"id": "Q1", "lat": 28.47, "lon": -16.25}, {"id": "Q2", "lat": 28.05, "lon": -16.72}, {"id": "Q3", "lat": 28.39, "lon": -16.52}, {"id": "Q9", "lat": None, "lon": None}]


def test_island_points_sorted_members_with_coords():
    pts = island.island_points(CITIES, "Q40846")
    assert [p["id"] for p in pts] == ["Q1", "Q2", "Q3"]  # ID 순, 좌표 없는 지자체는 뺀다
    assert island.island_points(CITIES, "Q0") == []


def test_coverage_and_file_shape_and_deterministic_gzip(tmp_path):
    mins = [[0, 70, 35], [70, 0, None], [35, None, 0]]; kms = [[0, 80.1, 40.2], [80.1, 0, None], [40.2, None, 0]]
    assert abs(island.coverage(mins) - 4 / 6) < 1e-9 and island.coverage([[0]]) == 0.0
    obj = island.island_file("Q40846", island.island_points(CITIES, "Q40846"), mins, kms)
    assert obj["cities"][1] == {"id": "Q2", "lat": 28.05, "lon": -16.72} and obj["car_min"][0][1] == 70 and obj["correction"] == {"car": 1.23}
    a, b = tmp_path / "a.json.gz", tmp_path / "b.json.gz"
    island.write_gz(a, obj); island.write_gz(b, obj)
    assert a.read_bytes() == b.read_bytes() and json.load(gzip.open(a, "rt", encoding="utf-8")) == obj


# --- 도시 간 기차(E3 4절 5항, D-055). 두 도시는 약 85km 떨어져 있고, 도시마다 중심역(1)과 8.5km 떨어진 외곽역(2)이 있다 ---
PTS = [{"id": "A", "n": "가", "lat": 40.0, "lon": -3.0}, {"id": "B", "n": "나", "lat": 40.0, "lon": -2.0}]
STOPS = [{"stop_id": "A1", "stop_lat": "40.0", "stop_lon": "-3.0"}, {"stop_id": "A2", "stop_lat": "40.0", "stop_lon": "-2.9"},
         {"stop_id": "B1", "stop_lat": "40.0", "stop_lon": "-2.0"}, {"stop_id": "B2", "stop_lat": "40.0", "stop_lon": "-2.1"},
         {"stop_id": "FAR", "stop_lat": "41.0", "stop_lon": "-2.5"}, {"stop_id": "BAD", "stop_lat": "", "stop_lon": ""}]
ALL = {d: "1" for d in intercity.DOW}
WEEKDAYS = {d: ("1" if i < 5 else "0") for i, d in enumerate(intercity.DOW)}
CALENDAR = [dict(ALL, service_id="D", start_date="20260105", end_date="20260201"),       # 28일 매일(2026-01-05는 월요일)
            dict(WEEKDAYS, service_id="W", start_date="20260105", end_date="20260301")]  # 8주 평일
CALENDAR_DATES = [{"service_id": "D", "date": "20260110", "exception_type": "2"},  # 운휴
                  {"service_id": "W", "date": "20260111", "exception_type": "1"}]  # 일요일 추가 운행
TRIPS = [{"trip_id": "t1", "service_id": "D"}, {"trip_id": "hs", "service_id": "W"}, {"trip_id": "bad", "service_id": "D"}, {"trip_id": "none", "service_id": "X"}]


def st(trip, seq, stop, arr, dep=None):
    return {"trip_id": trip, "stop_sequence": str(seq), "stop_id": stop, "arrival_time": arr, "departure_time": dep or arr}


STOP_TIMES = [st("t1", 1, "A1", "08:00:00"), st("t1", 2, "A2", "08:08:00", "08:09:00"), st("t1", 3, "B2", "08:45:00", "08:46:00"), st("t1", 4, "B1", "08:55:00"),
              st("hs", 1, "A1", "12:00:00"), st("hs", 2, "B2", "12:20:00"),      # 외곽역이지만 훨씬 빠르다
              st("bad", 1, "A1", "8:00:00"), st("bad", 2, "B1", "8:01:00"),        # 85km를 1분에: 자료 오류
              st("none", 1, "A1", "09:00:00"), st("none", 2, "FAR", "09:30:00")]  # FAR는 어느 도시에도 붙지 않는다
FEED = {"stops": STOPS, "calendar": CALENDAR, "calendar_dates": CALENDAR_DATES, "trips": TRIPS, "stop_times": STOP_TIMES}


def test_service_dates_and_window():
    dates = intercity.service_dates(CALENDAR, CALENDAR_DATES)
    assert len(dates["D"]) == 27 and datetime.date(2026, 1, 10) not in dates["D"]
    assert datetime.date(2026, 1, 11) in dates["W"] and datetime.date(2026, 1, 17) not in dates["W"] and len(dates["W"]) == 41
    window, start = intercity.window_of(dates)
    assert start == datetime.date(2026, 1, 5) and len(window) == 28 and max(window) == datetime.date(2026, 2, 1)
    assert len(dates["W"] & window) == 21
    assert intercity.window_of({}) == (set(), None)
    assert intercity.service_dates([{"service_id": "Z", "start_date": "x", "end_date": "y"}]) == {}


def test_assign_stops_nearest_city_within_radius():
    got = intercity.assign_stops(STOPS, PTS)
    assert set(got) == {"A1", "A2", "B1", "B2"} and got["A2"][0] == 0 and got["B2"][0] == 1
    assert got["A1"][3] == 0 and 25 < got["A2"][3] < 26  # 8.5km × 3분/km(추정)


def test_trip_pairs_one_entry_per_pair_and_central_stations():
    cs = intercity.assign_stops(STOPS, PTS)
    seq = [(int(r["stop_sequence"]), r["arrival_time"], r["departure_time"], *cs[r["stop_id"]]) for r in STOP_TIMES if r["trip_id"] == "t1"]
    pairs = intercity.trip_pairs(seq)
    assert list(pairs) == [(0, 1)]                 # 역 조합이 네 개여도 쌍은 하나
    assert pairs[(0, 1)] == (55.0, 55.0, None, None)  # 가장 짧은 외곽역 조합(36분)이 아니라 중심역끼리(55분). 역 ID를 넘기지 않으면 None
    with_ids = intercity.trip_pairs([x + (r["stop_id"],) for x, r in zip(seq, [r for r in STOP_TIMES if r["trip_id"] == "t1"])])
    assert with_ids[(0, 1)] == (55.0, 55.0, "A1", "B1")
    bad = [(int(r["stop_sequence"]), r["arrival_time"], r["departure_time"], *cs[r["stop_id"]]) for r in STOP_TIMES if r["trip_id"] == "bad"]
    assert intercity.trip_pairs(bad) == {}         # 시속 350km를 넘는 기록은 버린다
    assert intercity.trip_pairs([(1, "09:00:00", "09:00:00", 0, 40.0, -3.0, 0.0), (2, "08:00:00", "08:00:00", 1, 40.0, -2.0, 0.0)]) == {}  # 소요 0 이하


def test_train_stats_counts_each_trip_once_per_day():
    tr_min, tr_cnt, basis = intercity.train_stats([FEED], PTS)
    assert tr_min == [[None, 20], [None, None]]    # 외곽역이라도 접근을 더한 합(20+25.6)이 중심역끼리(55)보다 작으면 고른다
    assert tr_cnt == [[0, 1.7], [0, 0]]            # t1 27일 + hs 21일 = 48회 ÷ 28일. bad는 세지 않는다
    assert basis == [{"from": "2026-01-05", "days": 28}]
    feed2 = {"stops": STOPS, "calendar": [dict(ALL, service_id="E", start_date="20260201", end_date="20260228")], "trips": [{"trip_id": "x", "service_id": "E"}],
             "stop_times": [st("x", 1, "B1", "07:00:00"), st("x", 2, "A1", "08:10:00"), st("x", 3, "B1", "09:30:00")]}
    tr_min, tr_cnt, basis = intercity.train_stats([FEED, feed2], PTS)
    assert tr_min == [[None, 20], [70, None]] and tr_cnt == [[0, 2.7], [1.0, 0]]  # 자료가 여럿이면 더한 뒤 나눈다: (48 + 28) ÷ 28
    assert basis[1] == {"from": "2026-02-01", "days": 28}


def test_pick_run_lower_share_ignores_one_wrong_train():
    # (합, 소요, 운행 횟수). 10분짜리는 28일에 3회뿐인 잘못된 기록이고, 정상 운행은 34분 이상이다
    runs = [(31.0, 10.0, 3), (41.0, 34.0, 60), (46.0, 39.0, 500), (60.0, 55.0, 200)]
    assert intercity.pick_run(runs)[1] == 34.0                      # 전체 763회의 5%(38.15회)에 처음 닿는 운행
    assert intercity.pick_run([(31.0, 10.0, 3), (41.0, 34.0, 20)])[1] == 10.0   # 운행이 적으면(23회의 5% = 1.15회) 가장 빠른 운행
    assert intercity.pick_run([(50.0, 45.0, 0), (41.0, 34.0, 0)])[1] == 34.0    # 평균 기간 안에 운행이 없으면 합이 가장 작은 운행
    assert intercity.pick_run([(41.0, 34.0, 0), (50.0, 45.0, 10)])[1] == 45.0   # 운행이 없는 것은 건너뛴다


def test_train_stats_uses_lower_share_and_reports_detail():
    # 정상 열차 t는 28일 매일 40회, 잘못 적힌 열차 w는 28일 가운데 하루만 다닌다(중심역끼리 5분: 시속 350km는 넘지 않게 A1 → A2 방향이 아니라 가까운 두 도시로 만든다)
    pts = [{"id": "A", "n": "가", "lat": 40.0, "lon": -3.0}, {"id": "B", "n": "나", "lat": 40.0, "lon": -2.8}]  # 약 17km
    stops = [{"stop_id": "A1", "stop_lat": "40.0", "stop_lon": "-3.0"}, {"stop_id": "B1", "stop_lat": "40.0", "stop_lon": "-2.8"}]
    cal = [dict(ALL, service_id="D", start_date="20260105", end_date="20260201"), dict(ALL, service_id="ONE", start_date="20260106", end_date="20260106")]
    trips = [{"trip_id": f"t{i}", "service_id": "D"} for i in range(40)] + [{"trip_id": "w", "service_id": "ONE"}]
    times = [r for i in range(40) for r in (st(f"t{i}", 1, "A1", "08:00:00"), st(f"t{i}", 2, "B1", "08:20:00"))] + [st("w", 1, "A1", "21:23:00"), st("w", 2, "B1", "21:28:00")]
    detail = {}
    tr_min, tr_cnt, _ = intercity.train_stats([{"stops": stops, "calendar": cal, "trips": trips, "stop_times": times}], pts, detail=detail)
    assert tr_min[0][1] == 20            # 5분짜리 한 번(1,121회 가운데 1회)은 값을 정하지 못한다
    assert tr_cnt[0][1] == 40.0          # (40 × 28 + 1) ÷ 28 = 40.04
    assert detail[(0, 1)] == (0, "A1", "B1")


def write_gtfs(path, feed):
    cols = {"stops": ["stop_id", "stop_lat", "stop_lon"], "calendar": ["service_id", *intercity.DOW, "start_date", "end_date"], "calendar_dates": ["service_id", "date", "exception_type"],
            "trips": ["trip_id", "service_id"], "stop_times": ["trip_id", "stop_sequence", "stop_id", "arrival_time", "departure_time"]}
    with zipfile.ZipFile(path, "w") as z:
        for name, head in cols.items():
            z.writestr(name + ".txt", "\ufeff" + ",".join(head) + "\n" + "".join(",".join(r.get(h, "") for h in head) + "\n" for r in feed.get(name, [])))


def test_reuse_keeps_cities_and_car_matrix_and_is_deterministic(tmp_path, monkeypatch):
    old = {"generated": "2026-10-25", "correction": {"car": 1.23}, "cities": PTS, "car_min": [[0, 70], [71, 0]], "car_km": [[0, 90.5], [90.6, 0]],
           "train_min": [[None, 2], [None, None]], "trains_per_day": [[0, 138134.4], [0, 0]]}
    src = tmp_path / "old.json.gz"; intercity.write_gz(src, old)
    gtfs = tmp_path / "feed.zip"; write_gtfs(gtfs, FEED)
    outs = []
    for name in ("a", "b"):
        monkeypatch.setattr(sys, "argv", ["intercity", str(gtfs), "--reuse", str(src), "--out", str(tmp_path / name)])
        intercity.main(); outs.append((tmp_path / name / "intercity.json.gz").read_bytes())
    assert outs[0] == outs[1]
    obj = json.load(gzip.open(tmp_path / "a" / "intercity.json.gz", "rt", encoding="utf-8"))
    assert obj["cities"] == PTS and obj["car_min"] == old["car_min"] and obj["car_km"] == old["car_km"] and obj["generated"] == "2026-10-25"
    assert obj["train_min"] == [[None, 20], [None, None]] and obj["trains_per_day"] == [[0, 1.7], [0, 0]]
    assert obj["train_basis"]["feeds"] == [{"from": "2026-01-05", "days": 28}] and obj["train_basis"]["access_min_per_km"] == 3.0 and obj["train_basis"]["fast_share"] == 0.05
