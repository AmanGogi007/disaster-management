"""Hydrology feature classification + offline stub."""
from geo.hydrology.features import FeatureType, WaterFeature
from geo.hydrology.provider import _classify, _confidence_for, StubProvider


def test_classify_river():
    assert _classify({"waterway": "river"}) == FeatureType.RIVER


def test_classify_reservoir():
    assert _classify({"water": "reservoir"}) == FeatureType.RESERVOIR


def test_classify_dam():
    assert _classify({"waterway": "dam"}) == FeatureType.DAM


def test_classify_unknown_returns_none():
    assert _classify({"highway": "primary"}) is None


def test_confidence_for_dam_way():
    assert _confidence_for("way", FeatureType.DAM) == "high"


def test_stub_provider_returns_empty():
    out = StubProvider().get_features(30.7, 76.0, 50.0)
    assert out.features == []
    assert out.source == "none"