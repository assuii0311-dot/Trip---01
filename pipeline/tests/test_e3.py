"""E3 파이프라인(섬 안 차량 행렬)의 순수 함수 테스트. 경로 엔진은 부르지 않는다."""
import gzip
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.e3 import island  # noqa: E402

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
