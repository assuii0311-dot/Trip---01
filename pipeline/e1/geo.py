"""도시·지역 귀속 (E1 4절 8항). OSM 행정 경계 폴리곤(admin_level 8)에 점을 넣고, 없으면 최근접 지자체."""
import json
import math
import pathlib

from shapely import wkb
from shapely.geometry import Point
from shapely.ops import nearest_points
from shapely.strtree import STRtree

from . import config as C
from .match import Grid, hav


class Boundaries:
    def __init__(self, paths, levels=("4", "6", "8")):
        """paths: 경계 파일 하나 또는 여러 개(스페인 추출본 + 카나리아 추출본, D-031). 같은 osm_id는 먼저 나온 것만 쓴다."""
        self.by_level = {l: [] for l in levels}
        self.trees = {}
        n = 0
        seen = set()
        lines = (line for path in ([paths] if isinstance(paths, (str, pathlib.Path)) else list(paths)) for line in open(path, encoding="utf-8"))
        for line in lines:
            r = json.loads(line)
            if r["admin_level"] not in self.by_level or r["osm_id"] in seen:
                continue
            seen.add(r["osm_id"])
            try:
                geom = wkb.loads(bytes.fromhex(r["wkb"]))
            except Exception:
                continue
            if geom.is_empty:
                continue
            if not geom.is_valid:
                geom = geom.buffer(0)
            r2 = {"osm_id": r["osm_id"], "name": r.get("name"), "name_es": r.get("name_es"), "wikidata": r.get("wikidata"), "ine": r.get("ine"), "geom": geom, "area": geom.area}
            self.by_level[r["admin_level"]].append(r2); n += 1
        for l, rows in self.by_level.items():
            self.trees[l] = STRtree([r["geom"] for r in rows]) if rows else None
        self.count = n

    def lookup_all(self, level, lat, lon):
        """점을 포함하는 경계를 모두, 면적이 작은 순(같으면 osm_id 순)으로. 색인의 순서에 기대지 않아 입력 파일이 늘어도 결과가 같다."""
        tree = self.trees.get(level)
        if tree is None:
            return []
        p = Point(lon, lat)
        rows = [self.by_level[level][int(i)] for i in tree.query(p, predicate="within")]
        return sorted(rows, key=lambda r: (r["area"], r["osm_id"]))

    def lookup(self, level, lat, lon):
        rows = self.lookup_all(level, lat, lon)
        return rows[0] if rows else None

    def lookup_near(self, level, lat, lon, max_m=C.ADMIN_NEAR_M):
        """max_m 안에서 가장 가까운 경계(같으면 osm_id 순). 점을 포함하는 경계가 없을 때 쓴다: 해안 도시의 중심 좌표가 경계에서 바다 쪽으로 벗어난 경우(말라가, 마타로)."""
        tree = self.trees.get(level)
        if tree is None:
            return None
        p = Point(lon, lat)
        best = None
        for i in tree.query(p.buffer(max_m / 60000.0)):  # 후보는 넉넉히 잡고(위도 1도는 약 111km) 거리는 미터로 다시 잰다
            r = self.by_level[level][int(i)]
            q = nearest_points(r["geom"], p)[0]
            d = hav(lat, lon, q.y, q.x)
            if d <= max_m and (best is None or (d, r["osm_id"]) < (best[0], best[1]["osm_id"])):
                best = (d, r)
        return best[1] if best else None


class Nearest:
    """최근접 지자체(좌표 보유 Wikidata 지자체). 격자 색인으로 50km 안에서 찾는다."""
    def __init__(self, munis):
        self.grid = Grid(cell=0.1)
        for m in munis:
            self.grid.add(m["lat"], m["lon"], m)

    def find(self, lat, lon, max_m=50000):
        bestm, bestd = None, max_m
        for m in self.grid.near(lat, lon):
            d = hav(lat, lon, m["lat"], m["lon"])
            if d < bestd:
                bestm, bestd = m, d
        return bestm, bestd


def assign_city(boundaries, nearest, lat, lon, qid_by_ine, qid_by_boundary_name, known=None):
    """(city_qid, method). 폴리곤 → 경계의 wikidata 태그 → INE 코드 → 이름 → 최근접.

    점이 여러 경계에 들면(지자체 안의 하위 행정 단위 등) 면적이 작은 순으로 보되, 지자체 목록(known)에 있는 것으로 풀리는 경계를 먼저 쓴다.
    그런 경계가 없으면 wikidata 태그가 있는 첫 경계의 값을 그대로 쓴다(국경 밖 지자체 등. 이전 동작 유지).
    """
    rows = boundaries.lookup_all("8", lat, lon) if boundaries else []
    for b in rows:
        if b.get("wikidata") and (known is None or b["wikidata"] in known):
            return b["wikidata"], "polygon"
        if b.get("ine") and b["ine"] in qid_by_ine:
            return qid_by_ine[b["ine"]], "polygon_ine"
        if b.get("name") and b["name"] in qid_by_boundary_name:
            return qid_by_boundary_name[b["name"]], "polygon_name"
    for b in rows:
        if b.get("wikidata"):
            return b["wikidata"], "polygon"
    m, d = nearest.find(lat, lon)
    if m:
        return m["qid"], "nearest"
    return None, "none"


def assign_admin(boundaries, lat, lon):
    """(자치주 경계, 주 경계). 점을 포함하는 경계가 없으면 가까운 경계(lookup_near)."""
    if not boundaries:
        return None, None
    return (boundaries.lookup("4", lat, lon) or boundaries.lookup_near("4", lat, lon),
            boundaries.lookup("6", lat, lon) or boundaries.lookup_near("6", lat, lon))
