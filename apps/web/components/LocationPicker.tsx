"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MlMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

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
  lat: number;
  lon: number;
  onPick: (lat: number, lon: number) => void;
}

export default function LocationPicker({ lat, lon, onPick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const [status, setStatus] = useState("Click the map to set the plot location.");

  const placeMarker = (mlat: number, mlon: number) => {
    const map = mapRef.current;
    if (!map) return;
    if (markerRef.current) {
      markerRef.current.setLngLat([mlon, mlat]);
    } else {
      markerRef.current = new maplibregl.Marker({ color: "#4f8cff" })
        .setLngLat([mlon, mlat])
        .addTo(map);
    }
  };

  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;
  const coordsRef = useRef({ lat, lon });
  coordsRef.current = { lat, lon };

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const { lat: initLat, lon: initLon } = coordsRef.current;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: [initLon, initLat],
      zoom: 13,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.on("click", (e) => {
      const mlon = e.lngLat.lng;
      const mlat = e.lngLat.lat;
      placeMarker(mlat, mlon);
      onPickRef.current(round6(mlat), round6(mlon));
      setStatus(`Selected ${round6(mlat)}, ${round6(mlon)}`);
      reverseGeocode(mlat, mlon).then((name) => {
        if (name) setStatus(`Selected ${round6(mlat)}, ${round6(mlon)} — ${name}`);
      });
    });
    mapRef.current = map;
    placeMarker(initLat, initLon);
    return () => { map.remove(); mapRef.current = null; markerRef.current = null; };
  }, []);

  return (
    <div className="picker-wrap">
      <div className="picker-map" ref={containerRef} />
      <div className="picker-hint">{status}</div>
    </div>
  );
}

function round6(n: number) {
  return Math.round(n * 1e6) / 1e6;
}

async function reverseGeocode(lat: number, lon: number): Promise<string | null> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=14&addressdetails=1`
    );
    const data = await res.json();
    const a = data?.address ?? {};
    const parts = [a.village || a.town || a.city || a.suburb, a.state?.split(",")[0], a.country]
      .filter(Boolean);
    return parts.join(", ") || data?.display_name || null;
  } catch {
    return null;
  }
}
