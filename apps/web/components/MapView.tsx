"use client";

import { useEffect, useRef } from "react";
import type { MutableRefObject } from "react";
import maplibregl, { Map as MlMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Assessment, MapLayer } from "@/types/api";
import { getMapLayers } from "@/lib/api";

const OSM_STYLE = {
  version: 8 as const,
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
      maxzoom: 19,
    },
  },
  layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
};

interface Props {
  assessment: Assessment;
}

const GROUP_STYLE: Record<string, { color: string; width: number }> = {
  waterways: { color: "#3ba7ff", width: 2.5 },
  barriers: { color: "#ffb84d", width: 2 },
  crossings: { color: "#7dff8a", width: 2 },
  flood_control: { color: "#ff7a7a", width: 2 },
};

export default function MapView({ assessment }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const markerRef = useRef<Marker | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: [assessment.location.lon, assessment.location.lat],
      zoom: 12,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, [assessment.location.lat, assessment.location.lon]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    let cancelled = false;
    getMapLayers(assessment.id)
      .then((res) => {
        if (cancelled) return;
        applyLayers(map, res.layers, assessment, markerRef);
      })
      .catch((err) => {
        // Fall back to plot + radius even if layers fail to fetch.
        if (!cancelled) {
          const fallback: MapLayer[] = [
            {
              id: "plot", type: "point", label: "Plot location", visible: true,
              coordinates: [assessment.location.lon, assessment.location.lat],
              properties: { radius_km: assessment.location.radius_km },
            },
            {
              id: "radius", type: "circle", label: "Search radius", visible: true,
              center: [assessment.location.lon, assessment.location.lat],
              radius_km: assessment.location.radius_km,
            },
          ];
          applyLayers(map, fallback, assessment, markerRef);
        }
      });

    return () => { cancelled = true; };
  }, [assessment]);

  return <div className="map" ref={containerRef} />;
}

function applyLayers(
  map: MlMap,
  layers: MapLayer[],
  assessment: Assessment,
  markerRef: MutableRefObject<Marker | null>
) {
  const style = map.getStyle();
  for (const id of style.layers?.map((l) => l.id) ?? []) {
    if (id !== "osm") map.removeLayer(id);
  }
  for (const id of Object.keys(style.sources ?? {})) {
    if (id !== "osm") map.removeSource(id);
  }
  if (markerRef.current) {
    markerRef.current.remove();
    markerRef.current = null;
  }

  const center: [number, number] = [assessment.location.lon, assessment.location.lat];
  const radiusKm = assessment.location.radius_km;

  markerRef.current = new maplibregl.Marker({ color: "#4f8cff" })
    .setLngLat(center)
    .addTo(map);

  // Collect vector features grouped by layer type.
  const lines: GeoJSON.Feature[] = [];
  const points: GeoJSON.Feature[] = [];
  let radiusLayer: MapLayer | undefined;

  for (const ly of layers) {
    if (!ly.visible) continue;
    if (ly.type === "circle") {
      radiusLayer = ly;
    } else if (ly.type === "line" && Array.isArray(ly.coordinates)) {
      const lineCoords = ly.coordinates as [number, number][];
      lines.push({
        type: "Feature",
        geometry: { type: "LineString", coordinates: lineCoords as unknown as GeoJSON.Position[] },
        properties: {
          label: ly.label,
          group: ly.group || "other",
          name: ly.name,
          length_km: ly.length_km,
        },
      });
    } else if (ly.type === "point" && ly.id !== "plot" && Array.isArray(ly.coordinates)) {
      points.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: ly.coordinates as [number, number] },
        properties: { label: ly.label, group: ly.group || "other", name: ly.name },
      });
    }
  }

  // Radius circle
  if (radiusLayer?.center && radiusLayer.radius_km) {
    const circle = turfCircle(radiusLayer.center, radiusLayer.radius_km);
    map.addSource("radius", { type: "geojson", data: circle });
    map.addLayer({
      id: "radius-fill",
      type: "fill",
      source: "radius",
      paint: { "fill-color": "#4f8cff", "fill-opacity": 0.05 },
    });
    map.addLayer({
      id: "radius-line",
      type: "line",
      source: "radius",
      paint: { "line-color": "#4f8cff", "line-width": 1, "line-dasharray": [3, 3] },
    });
  }

  // Evidence lines (per-group styling). To color per group we add the whole
  // collection once and use a data-driven color expression on the `group` prop.
  if (lines.length > 0) {
    map.addSource("evidence-lines", {
      type: "geojson",
      data: { type: "FeatureCollection", features: lines },
    });
    map.addLayer({
      id: "evidence-lines",
      type: "line",
      source: "evidence-lines",
      paint: {
        "line-color": [
          "match", ["get", "group"],
          "waterways", "#3ba7ff",
          "barriers", "#ffb84d",
          "crossings", "#7dff8a",
          "flood_control", "#ff7a7a",
          "#d0d0d0",
        ],
        "line-width": [
          "match", ["get", "group"],
          "waterways", 2.5,
          "barriers", 2,
          "crossings", 2,
          "flood_control", 2,
          1.5,
        ],
      },
    });
  }

  if (points.length > 0) {
    map.addSource("evidence-points", {
      type: "geojson",
      data: { type: "FeatureCollection", features: points },
    });
    map.addLayer({
      id: "evidence-points",
      type: "circle",
      source: "evidence-points",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 3, 14, 6],
        "circle-color": ["match", ["get", "group"], "crossings", "#7dff8a", "barriers", "#ffb84d", "flood_control", "#ff7a7a", "#4f8cff"],
        "circle-stroke-color": "#0b0f14",
        "circle-stroke-width": 1,
      },
    });
  }

  map.fitBounds(
    [
      [center[0] - radiusKm / 40, center[1] - radiusKm / 40],
      [center[0] + radiusKm / 40, center[1] + radiusKm / 40],
    ],
    { padding: 40, animate: true }
  );
}

function turfCircle(center: [number, number], radiusKm: number) {
  const coords: [number, number][] = [];
  const earthR = 6371;
  const lat = center[1];
  const lon = center[0];
  const d = radiusKm / earthR;
  for (let i = 0; i <= 64; i++) {
    const bearing = (i * 360) / 64;
    const brad = (bearing * Math.PI) / 180;
    const latR = (lat * Math.PI) / 180;
    const lonR = (lon * Math.PI) / 180;
    const lat2 = Math.asin(Math.sin(latR) * Math.cos(d) + Math.cos(latR) * Math.sin(d) * Math.cos(brad));
    const lon2 = lonR + Math.atan2(
      Math.sin(brad) * Math.sin(d) * Math.cos(latR),
      Math.cos(d) - Math.sin(latR) * Math.sin(lat2)
    );
    coords.push([(lon2 * 180) / Math.PI, (lat2 * 180) / Math.PI]);
  }
  return { type: "Feature" as const, geometry: { type: "Polygon" as const, coordinates: [coords] }, properties: {} };
}
