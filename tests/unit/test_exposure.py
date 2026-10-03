"""Transparent flood-exposure scoring — deterministic, weights audit."""
from geo.analysis.exposure import ExposureInputs, ScoreWeights, compute_exposure


def test_weights_sum_to_one():
    ScoreWeights()
    try:
        ScoreWeights(distance=0.5, elevation=0.5, connectivity=0.5, historical=0.5, flow_accumulation=0.5)
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-summing weights")


def test_low_risk_when_far_and_high_above_water():
    out = compute_exposure(ExposureInputs(
        nearest_river_km=50.0, nearest_reservoir_km=200.0, nearest_dam_km=300.0,
        plot_elevation_m=400.0, nearest_water_elevation_m=200.0,
        slope_deg=5.0, flow_accumulation_at_plot=2,
        historical_flood_events=0, hydraulic_connection="none",
    ))
    assert out.category == "low"
    assert out.score < 25


def test_high_risk_when_below_water_and_close():
    out = compute_exposure(ExposureInputs(
        nearest_river_km=0.3, nearest_reservoir_km=5.0, nearest_dam_km=10.0,
        plot_elevation_m=100.0, nearest_water_elevation_m=110.0,
        slope_deg=0.2, flow_accumulation_at_plot=200,
        historical_flood_events=4, hydraulic_connection="likely",
    ))
    assert out.category in ("high", "very_high")
    assert out.score > 60


def test_confidence_low_when_data_missing():
    out = compute_exposure(ExposureInputs(
        nearest_river_km=None, nearest_reservoir_km=None, nearest_dam_km=None,
        plot_elevation_m=None, nearest_water_elevation_m=None,
        slope_deg=None, flow_accumulation_at_plot=None,
        historical_flood_events=0, hydraulic_connection="unknown",
    ))
    assert out.confidence == "low"


def test_contributing_factors_listed_when_high_subscores():
    out = compute_exposure(ExposureInputs(
        nearest_river_km=0.3, nearest_reservoir_km=4.0, nearest_dam_km=8.0,
        plot_elevation_m=110.0, nearest_water_elevation_m=120.0,
        slope_deg=0.5, flow_accumulation_at_plot=150,
        historical_flood_events=3, hydraulic_connection="likely",
    ))
    assert len(out.contributing_factors) >= 2


def test_result_includes_weights_and_limitations():
    out = compute_exposure(ExposureInputs(
        nearest_river_km=5.0, nearest_reservoir_km=20.0, nearest_dam_km=40.0,
        plot_elevation_m=200.0, nearest_water_elevation_m=180.0,
        slope_deg=2.0, flow_accumulation_at_plot=10,
        historical_flood_events=1, hydraulic_connection="possible",
    ))
    assert out.weights is not None
    assert sum(out.weights.values()) == pytest_sum_one()
    assert len(out.limitations) >= 1


def pytest_sum_one() -> float:
    return 1.0