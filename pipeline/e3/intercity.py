"""E3 사전 계산 1: 도시 간 행렬. 인구 상위 60개 도시 + 공항 도시의 차량 행렬(로컬 경로 엔진)과 Renfe GTFS의 기차 소요·하루 운행 수.

출력 travel/intercity.json.gz: {cities:[{id, n, lat, lon}], car_min[][], car_km[][], train_min[][], trains_per_day[][], train_basis, unreachable 쌍은 null}
기차 규칙(E3 4절 5항, D-055): 역은 15km 안 가장 가까운 대상 도시에 붙인다. 소요는 "기차 소요 + 역 접근"이 가장 작은 역 조합의 기차 소요,
하루 운행 수는 운행(trip)을 쌍마다 한 번만 세어 자료의 첫날부터 28일 평균. 순수 함수(service_dates, window_of, assign_stops, trip_pairs, train_stats, intercity_file)는 파일과 네트워크를 모른다.
실행(전체): python -I pipeline/run.py e3.intercity <타일 디렉터리> <cities.json.gz> <airports.json.gz> <Renfe GTFS zip...> --out <travel 디렉터리>
실행(기차만): python -I pipeline/run.py e3.intercity <Renfe GTFS zip...> --reuse <기존 intercity.json.gz> --out <travel 디렉터리>
  --reuse: 기존 파일의 도시 목록과 차량 행렬을 그대로 쓰고 기차 값만 다시 계산한다(경로 타일이 없을 때).
"""
import argparse
import collections
import csv
import datetime
import gzip
import io
import json
import math
import pathlib
import time
import zipfile

TOP_N = 60  # D-025 (a)


def hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(min(1, x)))


def pick_cities(cities, airports):
    cities = [c for c in cities if c.get("kind") != "island"]  # 섬 단위 여행지 레코드(D-030)는 행렬 대상이 아니다
    by_pop = sorted([c for c in cities if c.get("pop")], key=lambda c: -c["pop"])[:TOP_N]
    ids = {c["id"] for c in by_pop}
    # 공항에서 가장 가까운 지자체를 추가(섬 공항 포함)
    for a in airports:
        best = min(cities, key=lambda c: hav(a["lat"], a["lon"], c["lat"], c["lon"]))
        if best["id"] not in ids and hav(a["lat"], a["lon"], best["lat"], best["lon"]) < 30000 and (best.get("pop") or 0) >= 20000:
            ids.add(best["id"]); by_pop.append(best)
    return by_pop


def car_matrix(tiles, pts):
    from valhalla import Actor, get_config
    cfg = get_config(tile_dir=tiles, tile_extract="")
    cfg["service_limits"]["auto"]["max_matrix_location_pairs"] = 50000; cfg["service_limits"]["auto"]["max_matrix_distance"] = 5000000; cfg["service_limits"]["auto"]["max_locations"] = 200
    actor = Actor(cfg)
    locs = [{"lat": p["lat"], "lon": p["lon"]} for p in pts]
    n = len(locs); mins = [[None] * n for _ in range(n)]; kms = [[None] * n for _ in range(n)]
    for i0 in range(0, n, 25):
        m = actor.matrix({"sources": locs[i0:i0 + 25], "targets": locs, "costing": "auto"})
        for di, row in enumerate(m["sources_to_targets"]):
            for j, c in enumerate(row):
                if c.get("time") is not None:
                    mins[i0 + di][j] = round(c["time"] / 60 * 1.23)  # 속도 보정 ×1.23 (D-025 (c))
                    kms[i0 + di][j] = round(c["distance"], 1)
    return mins, kms


STOP_RADIUS_M = 15000     # 역을 대상 도시에 붙이는 반경
ACCESS_MIN_PER_KM = 3.0   # 추정: 역에서 도시 중심까지 시속 20km. 역 조합을 고르는 데만 쓴다
MAX_KMH = 350             # 두 역 사이의 직선 속도가 이보다 빠른 기록은 자료 오류로 본다
WINDOW_DAYS = 28          # 하루 운행 수를 평균하는 기간(자료의 첫 운행 날부터)
DOW = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def rows(z, name):
    """zip 안의 CSV를 한 줄씩 낸다(stop_times는 수백만 줄이라 목록으로 만들지 않는다)."""
    with z.open(name) as f:
        for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace")):
            yield {k.strip(): (v or "").strip() for k, v in r.items() if k}


def ymd(text):
    return datetime.date(int(text[:4]), int(text[4:6]), int(text[6:8]))


def service_dates(calendar, calendar_dates=()):
    """{service_id: {운행 날짜}}. calendar의 기간과 요일에 calendar_dates의 추가(1)와 운휴(2)를 반영한다."""
    out = collections.defaultdict(set)
    for c in calendar:
        try:
            d, end = ymd(c["start_date"]), ymd(c["end_date"])
        except (KeyError, ValueError):
            continue
        while d <= end:
            if c.get(DOW[d.weekday()]) == "1":
                out[c["service_id"]].add(d)
            d += datetime.timedelta(days=1)
    for r in calendar_dates:
        try:
            d = ymd(r["date"])
        except (KeyError, ValueError):
            continue
        if r.get("exception_type") == "1":
            out[r["service_id"]].add(d)
        elif r.get("exception_type") == "2":
            out[r["service_id"]].discard(d)
    return dict(out)


def window_of(dates_by_service, days=WINDOW_DAYS):
    """자료의 첫 운행 날부터 days일의 날짜 집합과 첫날. 운행 날짜가 없으면 (빈 집합, None)"""
    every = [d for v in dates_by_service.values() for d in v]
    if not every:
        return set(), None
    start = min(every)
    return {start + datetime.timedelta(days=i) for i in range(days)}, start


def assign_stops(stops, pts, radius=STOP_RADIUS_M):
    """{stop_id: (도시 번호, 위도, 경도, 도시 중심까지 분)} 반경 안에서 가장 가까운 대상 도시. 접근 분은 직선거리 × ACCESS_MIN_PER_KM(추정)"""
    out = {}
    for s in stops:
        try:
            la, lo = float(s["stop_lat"]), float(s["stop_lon"])
        except (KeyError, ValueError):
            continue
        j, d = min(((j, hav(la, lo, p["lat"], p["lon"])) for j, p in enumerate(pts)), key=lambda x: x[1])
        if d <= radius:
            out[s["stop_id"]] = (j, la, lo, d / 1000 * ACCESS_MIN_PER_KM)
    return out


def sec(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def trip_pairs(seq):
    """운행 하나 → {(출발 도시, 도착 도시): (기차 소요 + 역 접근, 기차 소요)}. 쌍마다 합이 가장 작은 역 조합 하나만 남긴다.

    seq: [(정차 순서, 도착 시각, 출발 시각, 도시 번호, 위도, 경도, 접근 분)]. 소요는 뒤 역의 도착 − 앞 역의 출발(분).
    소요가 0 이하이거나 두 역 사이의 직선 속도가 MAX_KMH를 넘는 조합은 버린다(자료 오류).
    """
    seq = sorted(seq)
    out = {}
    for a in range(len(seq)):
        for b in range(a + 1, len(seq)):
            ca, cb = seq[a][3], seq[b][3]
            if ca == cb:
                continue
            try:
                dur = (sec(seq[b][1]) - sec(seq[a][2])) / 60
            except (ValueError, AttributeError):
                continue
            if dur <= 0 or hav(seq[a][4], seq[a][5], seq[b][4], seq[b][5]) / 1000 / (dur / 60) > MAX_KMH:
                continue
            cand = (dur + seq[a][6] + seq[b][6], dur)
            if (ca, cb) not in out or cand < out[(ca, cb)]:
                out[(ca, cb)] = cand
    return out


def train_stats(feeds, pts, days=WINDOW_DAYS):
    """자료 목록 → (소요 행렬, 하루 운행 수 행렬, 기준 [{from, days}]).

    feeds: [{stops, calendar, calendar_dates, trips, stop_times}] 각 값은 GTFS 표의 줄(딕셔너리)을 내는 반복 가능 객체.
    소요: 모든 운행에서 "기차 소요 + 역 접근"이 가장 작은 역 조합의 기차 소요(분, 반올림).
    하루 운행 수: 운행 하나를 쌍마다 한 번만 세고, 자료마다 첫 운행 날부터 days일 안의 운행 횟수를 모두 더해 days로 나눈다(소수 1자리).
    """
    n = len(pts); best = {}; total = collections.Counter(); basis = []
    for feed in feeds:
        stop_city = assign_stops(feed["stops"], pts)
        dates = service_dates(feed.get("calendar") or (), feed.get("calendar_dates") or ())
        window, start = window_of(dates, days)
        basis.append({"from": start.isoformat() if start else None, "days": days})
        service = {t["trip_id"]: t["service_id"] for t in feed["trips"]}
        by_trip = collections.defaultdict(list)
        for st in feed["stop_times"]:
            c = stop_city.get(st["stop_id"])
            if c:
                by_trip[st["trip_id"]].append((int(st["stop_sequence"]), st.get("arrival_time") or st.get("departure_time"), st.get("departure_time") or st.get("arrival_time"), c[0], c[1], c[2], c[3]))
        for tid, seq in by_trip.items():
            pairs = trip_pairs(seq)
            active = len(dates.get(service.get(tid), set()) & window)
            for pair, cand in pairs.items():
                if pair not in best or cand < best[pair]:
                    best[pair] = cand
                total[pair] += active
    tr_min = [[None] * n for _ in range(n)]; tr_cnt = [[0] * n for _ in range(n)]
    for (a, b), cand in best.items():
        tr_min[a][b] = round(cand[1]); tr_cnt[a][b] = round(total[(a, b)] / days, 1)
    return tr_min, tr_cnt, basis


def train_times(gtfs_paths, pts):
    """GTFS zip들을 읽어 train_stats를 부른다."""
    def feed(path):
        z = zipfile.ZipFile(path); names = z.namelist()
        return {"stops": rows(z, "stops.txt"), "calendar": rows(z, "calendar.txt") if "calendar.txt" in names else (),
                "calendar_dates": rows(z, "calendar_dates.txt") if "calendar_dates.txt" in names else (),
                "trips": rows(z, "trips.txt"), "stop_times": rows(z, "stop_times.txt")}
    return train_stats([feed(p) for p in gtfs_paths], pts)


def intercity_file(cities, car_min, car_km, tr_min, tr_cnt, basis, generated, correction=None):
    """내보낼 객체. cities는 [{id, n, lat, lon}]. generated는 차량 행렬을 만든 날, train_basis는 기차 값의 기준(자료의 첫날과 평균 기간)."""
    return {"generated": generated, "correction": correction or {"car": 1.23}, "cities": cities, "car_min": car_min, "car_km": car_km,
            "train_min": tr_min, "trains_per_day": tr_cnt,
            "train_basis": {"feeds": basis, "access_min_per_km": ACCESS_MIN_PER_KM, "max_kmh": MAX_KMH, "stop_radius_m": STOP_RADIUS_M}}


def write_gz(path, obj):
    """같은 내용이면 같은 바이트가 나오게 쓴다(gzip 머리의 시각과 파일 이름을 비운다)."""
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as f:
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("inputs", nargs="+", help="전체: 타일 cities airports GTFS... / --reuse: GTFS..."); ap.add_argument("--reuse"); ap.add_argument("--out", required=True)
    a = ap.parse_args(); t0 = time.time()
    if a.reuse:  # 도시 목록과 차량 행렬은 기존 파일 그대로, 기차 값만 다시 계산한다
        old = json.load(gzip.open(a.reuse, "rt", encoding="utf-8"))
        cities, car_min, car_km, generated, correction, gtfs = old["cities"], old["car_min"], old["car_km"], old.get("generated"), old.get("correction"), a.inputs
        print(f"  기존 파일의 도시 {len(cities)}곳과 차량 행렬({generated})을 그대로 쓴다", flush=True)
    else:
        if len(a.inputs) < 3:
            ap.error("타일 디렉터리, cities.json.gz, airports.json.gz가 필요하다(기차만 다시 계산하려면 --reuse)")
        tiles, cities_path, airports_path, gtfs = a.inputs[0], a.inputs[1], a.inputs[2], a.inputs[3:]
        all_cities = json.load(gzip.open(cities_path, "rt", encoding="utf-8")); airports = json.load(gzip.open(airports_path, "rt", encoding="utf-8"))
        pts = pick_cities(all_cities, airports)
        print(f"  대상 도시 {len(pts)}곳", flush=True)
        car_min, car_km = car_matrix(tiles, pts); print(f"  차량 행렬 완료 ({time.time() - t0:.0f}초), 도달 불가 {sum(1 for r in car_min for v in r if v is None)}셀", flush=True)
        cities = [{"id": c["id"], "n": c["n"].get("ko") or c["n"].get("es"), "lat": c["lat"], "lon": c["lon"]} for c in pts]
        generated, correction = time.strftime("%Y-%m-%d"), None
    tr_min, tr_cnt, basis = train_times(gtfs, cities)
    print(f"  기차 직통 쌍 {sum(1 for r in tr_min for v in r if v is not None)}개, 기준 {basis} ({time.time() - t0:.0f}초)", flush=True)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    write_gz(out / "intercity.json.gz", intercity_file(cities, car_min, car_km, tr_min, tr_cnt, basis, generated, correction))
    print(f"  저장 {out / 'intercity.json.gz'} ({(out / 'intercity.json.gz').stat().st_size / 1e3:.0f}KB)", flush=True)


if __name__ == "__main__":
    main()
