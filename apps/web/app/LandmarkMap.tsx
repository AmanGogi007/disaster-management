// LandmarkMap.tsx - Interactive GIS map with marker, search radius, and zoom controls
"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

interface LandmarkMapProps {
  lat: string;
  lon: string;
  setLat: (v: string) => void;
  setLon: (v: string) => void;
  setPlace: (v: string) => void;
  searching: boolean;
  radius: number;
}

// Simple geodesic circle radius (Web Mercator) for the search radius overlay
function lngLatToMercator(lng: number, lat: number): [number, number] {
  const x = (lng + 180) / 360;
  const sinLat = Math.sin((lat * Math.PI) / 180);
  const y = 0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI);
  return [x, y];
}

function mercatorToLngLat(x: number, y: number): [number, number] {
  const lng = x * 360 - 180;
  const n = Math.PI - 2 * Math.PI * y;
  const lat = (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
  return [lng, lat];
}

function circleCoords(center: [number, number], radiusKm: number, segments = 64): [number, number][] {
  const [cx, cy] = lngLatToMercator(center[0], center[1]);
  // In normalized Web-Mercator units (0..1 for longitude), one full unit equals the
  // full equatorial circumference scaled by cos(latitude) for the local east-west scale.
  const metersPerUnit = 40075016.686 * Math.cos((center[1] * Math.PI) / 180);
  const r = (radiusKm * 1000) / metersPerUnit;
  const pts: [number, number][] = [];
  for (let i = 0; i < segments; i++) {
    const a = (i / segments) * 2 * Math.PI;
    pts.push(mercatorToLngLat(cx + r * Math.cos(a), cy + r * Math.sin(a)));
  }
  return pts;
}

const LandmarkMap: React.FC<LandmarkMapProps> = ({
  lat,
  lon,
  setLat,
  setLon,
  setPlace,
  searching,
  radius,
}) => {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const radiusRef = useRef<number>(radius);
  const centerRef = useRef<[number, number] | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);

  radiusRef.current = radius;

  const latNum = parseFloat(lat);
  const lonNum = parseFloat(lon);
  const validCenter = !isNaN(latNum) && !isNaN(lonNum) && latNum >= -90 && latNum <= 90 && lonNum >= -180 && lonNum <= 180;

  // Add or update the radius overlay. Only call when the style has loaded.
  const ensureRadiusLayer = useCallback(() => {
    const map = mapRef.current;
    if (!map || !validCenter) return;
    if (!map.isStyleLoaded()) return;
    const km = radiusRef.current;
    const center = centerRef.current ?? [lonNum, latNum];
    const coords = circleCoords(center as [number, number], km);
    const geojson = {
      type: "Feature" as const,
      properties: {},
      geometry: { type: "Polygon" as const, coordinates: [coords] },
    };
    if (map.getSource("radius")) {
      (map.getSource("radius") as maplibregl.GeoJSONSource).setData(geojson);
      return;
    }
    map.addSource("radius", {
      type: "geojson",
      data: geojson,
    });
    map.addLayer({
      id: "radius-fill",
      type: "fill",
      source: "radius",
      paint: { "fill-color": "#4f8cff", "fill-opacity": 0.12 },
    });
    map.addLayer({
      id: "radius-line",
      type: "line",
      source: "radius",
      paint: {
        "line-color": "#4f8cff",
        "line-width": 1.5,
        "line-dasharray": [2, 2],
      },
    });
  }, [latNum, lonNum, validCenter]);

  // Update the marker position and recenter the (single) map instance when the
  // resolved coordinates change. Never recreates the Map — updates in place.
  useEffect(() => {
    if (!validCenter) return;
    const map = mapRef.current;
    if (!map) return;

    const [clng, clat] = [lonNum, latNum];
    centerRef.current = [clng, clat];

    map.easeTo({ center: [clng, clat] });
    if (markerRef.current) {
      markerRef.current.setLngLat([clng, clat]);
    }

    ensureRadiusLayer();
  }, [latNum, lonNum, validCenter, ensureRadiusLayer]);

  // Create ONE Map instance on mount. Reuses refs; never recreated on prop changes.
  useEffect(() => {
    if (!validCenter) return;
    if (!containerRef.current) return;

    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: containerRef.current,
        style: {
          version: 8,
          sources: {
            osm: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              attribution: "© OpenStreetMap contributors",
              maxzoom: 19,
            },
          },
          layers: [{ id: "osm", type: "raster", source: "osm" }],
        },
        center: [lonNum, latNum],
        zoom: 12,
      });
    } catch (e) {
      setMapError("Failed to initialize map: " + (e instanceof Error ? e.message : String(e)));
      return;
    }

    mapRef.current = map;
    centerRef.current = [lonNum, latNum];
    setMapError(null);

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 100 }), "bottom-left");

    const markerEl = document.createElement("div");
    markerEl.className = "gis-marker";
    const marker = new maplibregl.Marker({ element: markerEl })
      .setLngLat([lonNum, latNum])
      .addTo(map);
    markerRef.current = marker;

    const clickHandler = (e: maplibregl.MapMouseEvent) => {
      const { lng, lat: clat } = e.lngLat;
      setLat(clat.toFixed(6));
      setLon(lng.toFixed(6));
      setPlace(`Lat ${clat.toFixed(4)}, Lng ${lng.toFixed(4)}`);
    };
    map.on("click", clickHandler);

    map.once("load", () => {
      ensureRadiusLayer();
    });
    if (map.loaded()) {
      ensureRadiusLayer();
    }

    return () => {
      map.off("click", clickHandler);
      marker.remove();
      markerRef.current = null;
      map.remove();
      mapRef.current = null;
      centerRef.current = null;
    };
    // Intentionally mount-only: the map instance and listeners are created once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update radius overlay when the slider changes (style already loaded).
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => ensureRadiusLayer();
    if (map.isStyleLoaded()) {
      apply();
    }
  }, [radius, ensureRadiusLayer]);

  return (
    <div className="landmark-map-wrap">
      <div ref={containerRef} className="landmark-map" />
      {mapError && (
        <div className="map-error-banner">
          <strong>Map error:</strong> {mapError}
        </div>
      )}
      {searching && (
        <div className="map-loading-overlay">
          <div className="spinner" />
          <span>Searching…</span>
        </div>
      )}
      <div className="map-coord-footer">
        <span>{validCenter ? `${latNum.toFixed(5)}°, ${lonNum.toFixed(5)}°` : "no valid coordinates"}</span>
        {validCenter && <span className="coord-km">{radius} km search radius</span>}
      </div>
    </div>
  );
};

export default LandmarkMap;