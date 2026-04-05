import pytest
from django import forms
from apps.suppliers.forms import _validate_geojson_polygon

pytestmark = pytest.mark.django_db


# ── Helpers ────────────────────────────────────────────────────────────────────

def _nigeria_polygon(coords=None):
    """Minimal closed Polygon inside Nigeria (Abuja area)."""
    ring = coords or [
        [7.0, 9.0],
        [7.5, 9.0],
        [7.5, 9.5],
        [7.0, 9.5],
        [7.0, 9.0],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def _assert_error(value, fragment):
    with pytest.raises(forms.ValidationError) as exc:
        _validate_geojson_polygon(value)
    assert fragment.lower() in str(exc.value).lower()


# ── Happy paths ────────────────────────────────────────────────────────────────

def test_valid_polygon_passes():
    result = _validate_geojson_polygon(_nigeria_polygon())
    assert result is not None


def test_valid_feature_wrapper_passes():
    feature = {
        "type": "Feature",
        "geometry": _nigeria_polygon(),
        "properties": {},
    }
    result = _validate_geojson_polygon(feature)
    assert result is not None


def test_none_value_passes():
    assert _validate_geojson_polygon(None) is None


def test_valid_multipolygon_passes():
    ring = [[7.0, 9.0], [7.5, 9.0], [7.5, 9.5], [7.0, 9.5], [7.0, 9.0]]
    value = {"type": "MultiPolygon", "coordinates": [[ring]]}
    result = _validate_geojson_polygon(value)
    assert result is not None


# ── Structural errors ──────────────────────────────────────────────────────────

def test_missing_type_field_raises():
    _assert_error({"coordinates": [[[7.0, 9.0]]]}, "type")


def test_wrong_type_raises():
    _assert_error({"type": "Point", "coordinates": [7.0, 9.0]}, "Polygon or MultiPolygon")


def test_unclosed_ring_raises():
    ring = [[7.0, 9.0], [7.5, 9.0], [7.5, 9.5], [7.0, 9.5]]  # last != first
    _assert_error({"type": "Polygon", "coordinates": [ring]}, "not closed")


def test_ring_too_short_raises():
    ring = [[7.0, 9.0], [7.5, 9.0], [7.0, 9.0]]  # only 3 points
    _assert_error({"type": "Polygon", "coordinates": [ring]}, "at least 4")


def test_missing_coordinates_raises():
    _assert_error({"type": "Polygon"}, "missing coordinates")


def test_feature_with_no_geometry_raises():
    _assert_error({"type": "Feature", "geometry": None, "properties": {}}, "no geometry")


# ── Coordinate range errors ────────────────────────────────────────────────────

def test_longitude_out_of_range_raises():
    ring = [[999.0, 9.0], [7.5, 9.0], [7.5, 9.5], [7.0, 9.5], [999.0, 9.0]]
    _assert_error({"type": "Polygon", "coordinates": [ring]}, "longitude")


def test_latitude_out_of_range_raises():
    ring = [[7.0, 999.0], [7.5, 999.0], [7.5, 9.5], [7.0, 9.5], [7.0, 999.0]]
    _assert_error({"type": "Polygon", "coordinates": [ring]}, "latitude")


def test_swapped_lat_lon_raises():
    # Lat/lon swapped: using [lat, lon] instead of [lon, lat].
    # lat=9.5 is fine as lon, but lat=3.0 is below Nigeria's southern bound (4.0°N).
    ring = [[9.5, 3.0], [10.0, 3.0], [10.0, 3.5], [9.5, 3.5], [9.5, 3.0]]
    _assert_error({"type": "Polygon", "coordinates": [ring]}, "nigeria")


# ── Coordinate bomb ────────────────────────────────────────────────────────────

def test_coordinate_bomb_rejected():
    """A ring with 10 000 points should be rejected at the out-of-range check
    because the spammed coordinates fall outside Nigeria."""
    point = [200.0, 200.0]  # clearly out of range
    ring = [point] * 10_000 + [point]
    _assert_error({"type": "Polygon", "coordinates": [ring]}, "longitude")


# ── Self-intersection (requires shapely) ──────────────────────────────────────

def test_self_intersecting_polygon_raises():
    # Figure-8: ring crosses itself
    ring = [
        [7.0, 9.0],
        [7.5, 9.5],
        [7.5, 9.0],
        [7.0, 9.5],
        [7.0, 9.0],
    ]
    _assert_error({"type": "Polygon", "coordinates": [ring]}, "crosses itself")
