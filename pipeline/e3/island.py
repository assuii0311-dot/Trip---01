"""E3 사전 계산 3: 섬 여행지 안의 지자체 사이 차량 행렬(T-048, E3 4절 2항).

섬 여행지(D-030)는 지자체 여러 곳을 묶은 단위라 섬 안에서도 수십 km를 이동한다. 도시 간 행렬(intercity)은 인구 상위 도시만 담아
섬 안의 지자체 쌍이 거의 없으므로, 섬마다 소속 지자체 중심 사이의 차량 시간을 따로 계산한다.

출력 travel/island_<섬 ID>.json.gz: {island, correction, cities:[{id, lat, lon}], car_min[][], car_km[][]} (도달 불가는 null)
실행: python -I pipeline/run.py e3.island <타일 디렉터리> <cities.json.gz> --out <travel 디렉터리> [--islands ID,ID,...]
타일은 추출본별로 다르다(카나리아 섬은 카나리아 타일, 발레아레스 섬은 스페인 타일). 타일이 덮지 않는 섬은 쌍의 절반 이상이 도달 불가로 나오므로 쓰지 않고 건너뛴다.
"""
import argparse
import gzip
import json
import pathlib
import time

CORRECTION = 1.23  # 차량 속도 보정(D-025 (c)). intercity.car_matrix가 곱해서 돌려준다


def island_points(cities, island_id):
    """섬 레코드의 소속 지자체(좌표 있는 것)를 ID 순으로. 순서가 행렬의 행·열 순서다."""
    by = {c["id"]: c for c in cities}
    isl = by.get(island_id) or {}
    return [by[m] for m in sorted(isl.get("members") or []) if m in by and by[m].get("lat") is not None and by[m].get("lon") is not None]


def coverage(mins):
    """자기 자신을 뺀 쌍 가운데 차량 시간이 있는 비율."""
    n = len(mins)
    cells = [mins[i][j] for i in range(n) for j in range(n) if i != j]
    return sum(1 for v in cells if v is not None) / len(cells) if cells else 0.0


def island_file(island_id, pts, mins, kms):
    return {"island": island_id, "correction": {"car": CORRECTION}, "cities": [{"id": c["id"], "lat": c["lat"], "lon": c["lon"]} for c in pts], "car_min": mins, "car_km": kms}


def write_gz(path, obj):
    """같은 내용이면 같은 바이트가 나오게 쓴다(gzip 머리의 시각과 파일 이름을 비운다)."""
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as f:
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def main():
    from .intercity import car_matrix
    ap = argparse.ArgumentParser(); ap.add_argument("tiles"); ap.add_argument("cities"); ap.add_argument("--out", required=True); ap.add_argument("--islands", default="")
    a = ap.parse_args(); t0 = time.time()
    cities = json.load(gzip.open(a.cities, "rt", encoding="utf-8"))
    ids = [x for x in a.islands.split(",") if x] or sorted(c["id"] for c in cities if c.get("kind") == "island")
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for iid in ids:
        pts = island_points(cities, iid)
        if len(pts) < 2:
            print(f"  {iid}: 지자체 {len(pts)}곳, 건너뜀", flush=True); continue
        try:
            mins, kms = car_matrix(a.tiles, pts)
        except Exception as e:  # 타일이 덮지 않는 섬은 경로 엔진이 "연결되지 않은 지역" 오류를 낸다
            print(f"  {iid}: 지자체 {len(pts)}곳, 경로 엔진 오류({str(e)[:60]}) → 이 타일이 덮지 않는 섬으로 보고 건너뜀", flush=True); continue
        cov = coverage(mins)
        if cov < 0.5:
            print(f"  {iid}: 지자체 {len(pts)}곳, 차량 시간이 있는 쌍 {cov:.0%} → 이 타일이 덮지 않는 섬으로 보고 건너뜀", flush=True); continue
        write_gz(out / f"island_{iid}.json.gz", island_file(iid, pts, mins, kms))
        print(f"  {iid}: 지자체 {len(pts)}곳, 쌍 {cov:.0%}, 최장 {max(v for r in mins for v in r if v is not None)}분 → island_{iid}.json.gz ({time.time() - t0:.0f}초)", flush=True)


if __name__ == "__main__":
    main()
