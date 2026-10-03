"use client"

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { createAssessment } from "@/lib/api";
import LandmarkMap from "./LandmarkMap";
import "./globals.css";

const TYPEWRITER_STAGES = ["LOCATION", "TERRAIN", "HYDROLOGY", "HYDRAULIC CONNECTIVITY", "FLOOD MODEL"];

// Default map center: Ghanaur Kalan, Dhuri Tahsil, Sangrur, Punjab, India
const DEFAULT_LOCATION = {
  lat: "30.4256591",
  lon: "75.7951498",
  place: "Ghanaur Kalan, Dhuri Tahsil, Sangrur, Punjab, India",
};

function LandingPage() {
  const [lat, setLat] = useState(DEFAULT_LOCATION.lat);
  const [lon, setLon] = useState(DEFAULT_LOCATION.lon);
  const [place, setPlace] = useState(DEFAULT_LOCATION.place);
  const [radius, setRadius] = useState(10);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [locating, setLocating] = useState(false);

  const router = useRouter();

  // Detect "lat, lon" or "lon, lat" coordinate input and use directly
  const parseCoords = (query: string): { lat: number; lon: number } | null => {
    const cleaned = query.trim().replace(/\s+/g, " ");
    const m = cleaned.match(/^(-?\d+(?:\.\d+)?)\s*[,;\s]+\s*(-?\d+(?:\.\d+)?)$/);
    if (!m) return null;
    const a = parseFloat(m[1]);
    const b = parseFloat(m[2]);
    // Heuristic: assume "lat, lon" order. If first value is a plausible latitude
    // (<=90) and second is a plausible longitude (<=180), use as-is, otherwise swap.
    if (isNaN(a) || isNaN(b)) return null;
    if (Math.abs(a) <= 90 && Math.abs(b) <= 180) return { lat: a, lon: b };
    if (Math.abs(b) <= 90 && Math.abs(a) <= 180) return { lat: b, lon: a };
    return null;
  };

  const geocode = async (query: string) => {
    setSearching(true);
    setError("");
    if (!query.trim()) {
      setError("Please enter an address, city, or coordinates.");
      setSearching(false);
      return;
    }

    // Direct coordinate input (e.g. "30.9, 75.8")
    const coords = parseCoords(query);
    if (coords) {
      setLat(coords.lat.toFixed(6));
      setLon(coords.lon.toFixed(6));
      setPlace(`Lat ${coords.lat.toFixed(4)}, Lng ${coords.lon.toFixed(4)}`);
      setSearching(false);
      return;
    }

    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`
      );
      if (!res.ok) {
        setError("Geocoding service error. Try again.");
        return;
      }
      const data = await res.json();
      if (!data || data.length === 0) {
        setError("Unable to find that location. Try an address, city name, or coordinates such as 30.9000, 75.8000");
        return;
      }
      setLat(data[0].lat);
      setLon(data[0].lon);
      setPlace(data[0].display_name || query);
    } catch (e: unknown) {
      setError("Geocoding failed. Check the network or enter coordinates manually.");
    } finally {
      setSearching(false);
    }
  };

  const handleSearch = () => {
    if (!place.trim()) {
      setError("Please enter an address, city, or coordinates.");
      return;
    }
    geocode(place);
  };

  const handleUseMyLocation = () => {
    if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
      setError("Geolocation is not supported in this browser.");
      return;
    }
    setLocating(true);
    setError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const la = pos.coords.latitude.toFixed(6);
        const lo = pos.coords.longitude.toFixed(6);
        setLat(la);
        setLon(lo);
        setPlace(`Your location — Lat ${la}, Lng ${lo}`);
        setLocating(false);
      },
      (err) => {
        setLocating(false);
        if (err.code === err.PERMISSION_DENIED) {
          setError("Location access was denied. Showing Ghanaur Kalan, Punjab as the default — use the search box to pick another place.");
        } else {
          setError("Could not get your location. Try the search box instead.");
        }
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const handleCreate = async () => {
    if (!lat || !lon || isNaN(parseFloat(lat)) || isNaN(parseFloat(lon))) {
      setError("Please search for a valid location first.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await createAssessment(
        parseFloat(lat),
        parseFloat(lon),
        radius,
        place
      );
      router.push(`/assessment/${res.assessment_id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setLoading(false);
    }
  };

  const hasValidCoords = lat && lon && !isNaN(parseFloat(lat)) && !isNaN(parseFloat(lon));
  const isDefaultLocation =
    hasValidCoords &&
    Math.abs(parseFloat(lat) - parseFloat(DEFAULT_LOCATION.lat)) < 0.00001 &&
    Math.abs(parseFloat(lon) - parseFloat(DEFAULT_LOCATION.lon)) < 0.00001;
  const resolvedLocation = place || (hasValidCoords ? `Lat ${parseFloat(lat).toFixed(5)}, Lng ${parseFloat(lon).toFixed(5)}` : "Unresolved");
  const pipelineStage = hasValidCoords ? 2 : 1; // Show initial stages

  return (
    <main className="gis-app">
      {/* ── Header ── */}
      <header className="gis-header">
        <div className="gis-brand">
          <span className="gis-logo">▼</span>
          <div>
            <h1>Location Hazard Intelligence Engine</h1>
            <p className="gis-header-sub">Evidence-based terrain and hydrology analysis</p>
          </div>
        </div>
        <div className="gis-header-meta">
          <span className="badge available">EVIDENCE-FIRST</span>
        </div>
      </header>

      {/* ── Main workspace ── */}
      <div className="gis-workspace">
        {/* ── Left: Map (65%) ── */}
        <section className="gis-map-col">
          <div className="gis-map-header">
            <span>TERRAIN &amp; LOCATION</span>
          </div>
          <div className="gis-map-stage">
            {hasValidCoords ? (
              <LandmarkMap
                lat={lat}
                lon={lon}
                setLat={setLat}
                setLon={setLon}
                setPlace={setPlace}
                searching={searching}
                radius={radius}
              />
            ) : (
              <div className="gis-empty-map">
                <div className="gis-empty-icon">🗺️</div>
                <p className="gis-empty-title">No location selected</p>
                <p className="gis-empty-sub">
                  Search for an address, city, or coordinates (e.g., <code>75.8, 30.9</code>) on the
                  right to render the interactive map with the search-radius overlay.
                </p>
              </div>
            )}
          </div>
        </section>

        {/* ── Right: Controls & Evidence (35%) ── */}
        <aside className="gis-controls-col">
          {/* Location search */}
          <div className="gis-panel">
            <div className="gis-panel-title">LOCATION</div>
            <div className="gis-field">
              <label htmlFor="location-search">Search location</label>
              <div className="gis-search-row">
                <input
                  id="location-search"
                  type="text"
                  placeholder="Address, city, or lat, lon (e.g. 30.9, 75.8)"
                  value={place}
                  onChange={(e) => setPlace(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
                />
                <button className="btn gis-btn-search" onClick={handleSearch} disabled={searching}>
                  {searching ? "…" : "Search"}
                </button>
              </div>
            </div>
            <div className="gis-locate-row">
              <span className="gis-locate-note">Default: Ghanaur Kalan, Dhuri, Punjab</span>
              <button
                className="btn gis-btn-locate"
                onClick={handleUseMyLocation}
                disabled={locating}
              >
                {locating ? "Locating…" : "📍 Use my location"}
              </button>
            </div>

            <div className="gis-resolved-row">
              <span className="gis-resolved-label">Resolved</span>
              <span className="gis-resolved-status">
                {isDefaultLocation ? (
                  <span className="gis-tag gis-tag-default">DEFAULT (demo)</span>
                ) : hasValidCoords ? (
                  <span className="gis-tag gis-tag-user">USER</span>
                ) : (
                  <span className="gis-tag gis-tag-muted">UNRESOLVED</span>
                )}
              </span>
            </div>
            <div className="gis-resolved-detail">
              {hasValidCoords ? resolvedLocation : "—"}
            </div>

            {hasValidCoords && (
              <div className="gis-coords-row">
                <span className="gis-coord-chip">
                  <b>LAT</b> {parseFloat(lat).toFixed(5)}
                </span>
                <span className="gis-coord-chip">
                  <b>LNG</b> {parseFloat(lon).toFixed(5)}
                </span>
              </div>
            )}

            <div className="gis-field gis-radius-field">
              <label>Search radius — <span className="gis-radius-val">{radius} km</span></label>
              <input
                type="range"
                min="1"
                max="50"
                step="1"
                value={radius}
                onChange={(e) => setRadius(Number(e.target.value))}
                id="radius-slider"
                className="gis-slider"
              />
              <div className="gis-radius-scale"><span>1 km</span><span>50 km</span></div>
            </div>

            <button
              className="btn gis-btn-assess"
              onClick={handleCreate}
              disabled={loading || !hasValidCoords}
            >
              {loading ? "Creating…" : "Start Assessment"}
            </button>
          </div>

          {/* Assessment pipeline */}
          <div className="gis-panel">
            <div className="gis-panel-title">ASSESSMENT PIPELINE</div>
            <div className="gis-pipeline">
              {TYPEWRITER_STAGES.map((stage, i) => {
                const isCurrent = i === pipelineStage - 1;
                const isBlocked = !hasValidCoords && i > 0;
                const isPast = i < pipelineStage - 1;
                return (
                  <div key={stage} className={`gis-pipe-stage ${isBlocked ? "blocked" : isPast ? "done" : isCurrent ? "current" : "pending"}`}>
                    <span className="gis-pipe-dot">
                      {isBlocked ? "🔒" : isPast ? "✓" : isCurrent ? "●" : "○"}
                    </span>
                    <span className="gis-pipe-label">{stage}</span>
                  </div>
                );
              })}
            </div>
            <div className="gis-pipe-note">
              {!hasValidCoords
                ? "Select a location to begin evidence gathering."
                : "Location locked. Terrain, hydrology, and hydraulic connectivity will be gathered next."}
            </div>
          </div>

          {/* Data provenance */}
          <div className="gis-panel">
            <div className="gis-panel-title">DATA PROVENANCE</div>
            <div className="gis-provenance">
              <div className="gis-prov-row"><span>Source</span><span className="mono">COPERNICUS/DEM/GLO30_2024_1</span></div>
              <div className="gis-prov-row"><span>Resolution</span><span>~30 m</span></div>
              <div className="gis-prov-row"><span>Vertical datum</span><span>EGM2008</span></div>
              <div className="gis-prov-row"><span>Horizontal CRS</span><span>EPSG:4326</span></div>
              <div className="gis-prov-row"><span>Limitation</span><span className="gis-prov-warn">Includes building/vegetation — not surveyed ground elevation.</span></div>
            </div>
          </div>

          {/* Flood result safety note */}
          <div className="gis-note-blocked">
            <strong>FLOOD MODEL — LOCKED</strong>
            <p>
              Flood depth and risk percentages require a verified local survey, a sub-30&nbsp;m DEM, and
              resolved hydraulic connectivity. The engine reports <em>evidence states</em> — never
              invented flood depths.
            </p>
          </div>
        </aside>
      </div>

      {error && (
        <div className="error-banner gis-error-fixed">
          <span className="error-icon">⚠</span> {error}
        </div>
      )}
    </main>
  );
}

export default LandingPage;
