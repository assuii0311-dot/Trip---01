// MapLibre GL 지도(D-026). 기본 OpenFreeMap 벡터 타일, 실패 시 OSM 래스터 폴백(식별 Referer는 브라우저가 보낸다).
/* global maplibregl */
const OFM_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const OSM_RASTER_STYLE = {
  version: 8,
  sources: { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, attribution: "© OpenStreetMap contributors", maxzoom: 19 } },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};
const ATTR_OFM = "© OpenStreetMap contributors · <a href=\"https://openfreemap.org\">OpenFreeMap</a>";

export function createMap(container, { center = [-3.7038, 40.4168], zoom = 12, onSelect } = {}) {
  if (typeof maplibregl === "undefined") return null;
  let fallback = false;
  const map = new maplibregl.Map({ container, style: OFM_STYLE, center, zoom, attributionControl: false });
  map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: ATTR_OFM }));
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
  map.on("error", (e) => {
    // 스타일·타일 로드 실패 → 래스터 폴백 한 번
    if (!fallback && e?.error && /style|tiles|Failed to fetch|40[34]|5\d\d/i.test(String(e.error.message || e.error))) {
      fallback = true;
      map.setStyle(OSM_RASTER_STYLE);
    }
  });
  let ready = false; const queue = [];
  map.on("load", () => { ready = true; queue.splice(0).forEach((f) => f()); });
  map.on("style.load", () => { if (ready) rerender(); });
  let lastFeatures = [];
  function rerender() {
    if (!map.isStyleLoaded()) return;
    const data = { type: "FeatureCollection", features: lastFeatures };
    if (map.getSource("places")) { map.getSource("places").setData(data); return; }
    map.addSource("places", { type: "geojson", data });
    // 핀: ★ 대표 명소(금), ● 그 밖(파랑), ◌ 검증 안 됨(회색), ✓ 선택(진파랑). 색은 의미에만(04-design-rules)
    map.addLayer({ id: "places-circle", type: "circle", source: "places", paint: {
      "circle-radius": ["case", ["get", "selected"], 9, ["get", "landmark"], 8, 6],
      "circle-color": ["case", ["get", "selected"], "#1E63D6", ["get", "landmark"], "#CA8A04", ["get", "unverified"], "#ffffff", "#60a5fa"],
      "circle-stroke-color": ["case", ["get", "unverified"], "#6B7280", "#ffffff"], "circle-stroke-width": 1.5,
    } });
    map.addLayer({ id: "places-label", type: "symbol", source: "places", minzoom: 14, layout: { "text-field": ["get", "name"], "text-size": 12, "text-offset": [0, 1.2], "text-anchor": "top", "text-font": ["Noto Sans Regular"] }, paint: { "text-halo-color": "#fff", "text-halo-width": 1 } });
    map.on("click", "places-circle", (e) => { const f = e.features && e.features[0]; if (f && onSelect) onSelect(f.properties.id); });
    map.on("mouseenter", "places-circle", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "places-circle", () => { map.getCanvas().style.cursor = ""; });
  }
  return {
    map,
    setPlaces(places, { selectedId, isLandmark } = {}) {
      lastFeatures = places.slice(0, 2000).map((p) => ({ type: "Feature", geometry: { type: "Point", coordinates: [p.lon, p.lat] }, properties: { id: p.id, name: p.n?.ko || p.n?.local || "", selected: p.id === selectedId, landmark: !!(isLandmark && isLandmark(p)), unverified: p.ver === false } }));
      const run = () => rerender();
      ready ? run() : queue.push(run);
    },
    flyTo(lat, lon, z = 14) { map.flyTo({ center: [lon, lat], zoom: z, duration: 300 }); },
    fitTo(places) { if (!places.length) return; const b = new maplibregl.LngLatBounds(); places.forEach((p) => b.extend([p.lon, p.lat])); map.fitBounds(b, { padding: 32, maxZoom: 15, duration: 300 }); },
    resize() { map.resize(); },
    destroy() { map.remove(); },
  };
}
