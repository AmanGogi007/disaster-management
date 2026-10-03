"""End-to-end orchestrator with the offline sample DEM + stub providers."""
from geo.hydrology.features import FeatureType, WaterFeature
from geo.hydrology.provider import StubProvider as HydroStub
from geo.terrain.provider import SampleProvider, StubProvider as ElevStub
from geo.orchestrator import analyze


def test_analyze_with_synthetic_providers():
    report = analyze(
        lat=30.7, lon=76.0, radius_km=50.0,
        elevation_provider=SampleProvider(),
        hydrology_provider=HydroStub(),
        historical_flood_count=0,
        historical_flood_source="none",
    )
    d = report.to_dict()
    assert d["version"] == "0.2.0"
    assert d["terrain"]["available"] is True
    assert d["terrain"]["point_elevation_m"] is not None
    assert d["hydrology"]["available"] is True
    assert d["hydrology"]["feature_count"] == 0
    assert d["risk"]["category"] in ("low", "moderate", "high", "very_high", "unknown")
    assert "weights" in d["risk"]


def test_analyze_with_elev_stub_returns_graceful_error():
    report = analyze(
        lat=30.7, lon=76.0, radius_km=50.0,
        elevation_provider=ElevStub(),
        hydrology_provider=HydroStub(),
    )
    d = report.to_dict()
    assert d["terrain"]["available"] is False
    assert d["risk"]["score"] is None


def test_analyze_rejects_bad_coords():
    import pytest
    try:
        analyze(lat=200, lon=0, radius_km=50.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_analyze_rejects_oversized_radius():
    import pytest
    try:
        analyze(lat=30.7, lon=76.0, radius_km=500.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_hydrology_features_with_synthetic_features_produce_score():
    feats = [
        WaterFeature(osm_id="1", name="Test River", type=FeatureType.RIVER,
                     latitude=30.71, longitude=76.0, distance_km=1.2),
        WaterFeature(osm_id="2", name="Test Dam", type=FeatureType.DAM,
                     latitude=30.9, longitude=76.2, distance_km=22.0),
    ]

    class FakeHydro:
        name = "fake"
        def get_features(self, lat, lon, radius_km):
            from geo.hydrology.provider import HydrologyResult
            return HydrologyResult(features=feats, source="fake", dataset="fake",
                                   retrieved_at=None, license="test")

    report = analyze(
        lat=30.7, lon=76.0, radius_km=50.0,
        elevation_provider=SampleProvider(),
        hydrology_provider=FakeHydro(),
        historical_flood_count=2,
        historical_flood_source="osm-tagged",
    )
    d = report.to_dict()
    assert d["hydrology"]["nearest_river"]["name"] == "Test River"
    assert d["hydrology"]["nearest_dam"]["name"] == "Test Dam"
    assert d["risk"]["score"] is not None