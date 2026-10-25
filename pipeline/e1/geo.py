"""도시·지역 귀속 (E1 4절 8항). OSM 행정 경계 폴리곤(admin_level 8)에 점을 넣고, 없으면 최근접 지자체."""
import json
import math

from shapely import wkb
from shapely.geometry import Point
from shapely.strtree import STRtree

from .match import Grid, hav


class Boundaries:
    def __init__(self, path, levels=("4", "6", "8")):
        self.by_level = {l: [] for l in levels}
        self.trees = {}
        n = 0
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            if r["admin_level"] not in self.by_level:
                continue
            try:
                geom = wkb.loads(bytes.fromhex(r["wkb"]))
            except Exception:
                continue
            if geom.is_empty:
                continue
            if not geom.is_valid:
                geom = geom.buffer(0)
            r2 = {"osm_id": r["osm_id"], "name": r.get("name"), "name_es": r.get("name_es"), "wikidata": r.get("wikidata"), "ine": r.get("ine"), "geom": geom}
            self.by_level[r["admin_level"]].append(r2); n += 1
        for l, rows in self.by_level.items():
            self.trees[l] = STRtree([r["geom"] for r in rows]) if rows else None
        self.count = n

    def lookup(self, level, lat, lon):
        tree = self.trees.get(level)
        if tree is None:
            return None
        p = Point(lon, lat)
        for i in tree.query(p, predicate="within"):
            return self.by_level[level][int(i)]
        return None


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


def assign_city(boundaries, nearest, lat, lon, qid_by_ine, qid_by_boundary_name):
    """(city_qid, method). 폴리곤 → 경계의 wikidata 태그 → INE 코드 → 이름 → 최근접."""
    b = boundaries.lookup("8", lat, lon) if boundaries else None
    if b:
        if b.get("wikidata"):
            return b["wikidata"], "polygon"
        if b.get("ine") and b["ine"] in qid_by_ine:
            return qid_by_ine[b["ine"]], "polygon_ine"
        if b.get("name") and b["name"] in qid_by_boundary_name:
            return qid_by_boundary_name[b["name"]], "polygon_name"
    m, d = nearest.find(lat, lon)
    if m:
        return m["qid"], "nearest"
    return None, "none"


def assign_admin(boundaries, lat, lon):
    """(자치주 경계, 주 경계)"""
    if not boundaries:
        return None, None
    return boundaries.lookup("4", lat, lon), boundaries.lookup("6", lat, lon)
