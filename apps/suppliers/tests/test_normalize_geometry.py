import pytest
from apps.suppliers.forms import normalize_sw_maps_geometry

pytestmark = pytest.mark.django_db


# ── Helpers ────────────────────────────────────────────────────────────────────

def _poly(ring):
    return {"type": "Polygon", "coordinates": [ring]}


def _multipoly(ring):
    return {"type": "MultiPolygon", "coordinates": [[ring]]}


# ── Z stripping ────────────────────────────────────────────────────────────────

def test_strips_elevation():
    ring = [[10.0, 7.0, 183.8], [10.1, 7.0, 184.0], [10.1, 7.1, 184.2],
            [10.0, 7.1, 184.0], [10.0, 7.0, 183.8]]
    result = normalize_sw_maps_geometry(_poly(ring))
    for coord in result["coordinates"][0]:
        assert len(coord) == 2, f"Expected 2D coord, got {coord}"


def test_rounds_to_6dp():
    ring = [[10.9740433330000001, 7.8606083330000001], [10.974048333, 7.860623333],
            [10.97406, 7.860626667], [10.974048333, 7.860623333],
            [10.9740433330000001, 7.8606083330000001]]
    result = normalize_sw_maps_geometry(_poly(ring))
    for coord in result["coordinates"][0]:
        assert coord[0] == round(coord[0], 6)
        assert coord[1] == round(coord[1], 6)


# ── Deduplication ──────────────────────────────────────────────────────────────

def test_removes_consecutive_duplicates():
    # GPS paused: same point repeated many times
    pt = [10.974043, 7.860608]
    ring = [pt] * 20 + [[10.974385, 7.860697], [10.974395, 7.860490],
                         [10.974035, 7.860453]] + [pt]
    result = normalize_sw_maps_geometry(_poly(ring))
    ring_out = result["coordinates"][0]
    # No two consecutive identical points (except closure: first == last)
    for i in range(len(ring_out) - 1):
        assert ring_out[i] != ring_out[i + 1], (
            f"Consecutive duplicate at index {i}: {ring_out[i]}"
        )


def test_preserves_non_consecutive_duplicates():
    # Same coordinate appearing twice but not adjacent is fine
    ring = [[10.0, 7.0], [10.1, 7.0], [10.0, 7.0], [10.0, 7.1], [10.0, 7.0]]
    result = normalize_sw_maps_geometry(_poly(ring))
    # Should not collapse non-adjacent duplicates into one
    ring_out = result["coordinates"][0]
    assert len(ring_out) >= 4


# ── Closure ────────────────────────────────────────────────────────────────────

def test_auto_closes_open_ring():
    ring = [[10.0, 7.0], [10.1, 7.0], [10.1, 7.1], [10.0, 7.1]]  # not closed
    result = normalize_sw_maps_geometry(_poly(ring))
    ring_out = result["coordinates"][0]
    assert ring_out[0] == ring_out[-1], "Ring should be auto-closed"


def test_already_closed_ring_unchanged():
    ring = [[10.0, 7.0], [10.1, 7.0], [10.1, 7.1], [10.0, 7.1], [10.0, 7.0]]
    result = normalize_sw_maps_geometry(_poly(ring))
    ring_out = result["coordinates"][0]
    assert ring_out[0] == ring_out[-1]
    # Closing point not duplicated
    assert len(ring_out) == 5


# ── Simplification ─────────────────────────────────────────────────────────────

def test_simplification_triggers_above_threshold():
    # Build a ring with >200 unique points along a straight edge — should simplify
    base = [[10.0 + i * 0.00001, 7.0] for i in range(150)]
    right = [[10.0 + 150 * 0.00001, 7.0 + i * 0.00001] for i in range(60)]
    close = [[10.0, 7.0]]
    ring = base + right + close
    assert len(ring) > 200
    result = normalize_sw_maps_geometry(_poly(ring), max_vertices=200)
    ring_out = result["coordinates"][0]
    assert len(ring_out) <= 200, f"Expected ≤ 200 vertices, got {len(ring_out)}"
    assert ring_out[0] == ring_out[-1], "Ring must remain closed after simplification"


def test_simplification_does_not_trigger_below_threshold():
    ring = [[10.0, 7.0], [10.1, 7.0], [10.1, 7.1], [10.0, 7.1], [10.0, 7.0]]
    result = normalize_sw_maps_geometry(_poly(ring), max_vertices=200)
    assert len(result["coordinates"][0]) == 5


# ── Real SW Maps sample ────────────────────────────────────────────────────────

def test_real_sw_maps_polygon():
    """End-to-end: the actual Khadija Suleiman Farms polygon from a field export."""
    ring = [
        [10.974043333,7.860608333,183.8],[10.974043333,7.860608333,183.8],
        [10.974043333,7.860608333,183.8],[10.974043333,7.860608333,183.8],
        [10.974043333,7.860608333,183.8],[10.974048333,7.860623333,185.4],
        [10.97406,7.860626667,185.4],[10.97407,7.860626667,185.3],
        [10.974078333,7.860626667,185.0],[10.974088333,7.860628333,185.0],
        [10.974098333,7.860631667,185.1],[10.974106667,7.860635,185.2],
        [10.974116667,7.860636667,185.2],[10.974125,7.860638333,185.0],
        [10.974135,7.860641667,184.8],[10.974143333,7.860645,184.7],
        [10.974153333,7.860648333,184.4],[10.974163333,7.860651667,184.6],
        [10.974173333,7.860656667,184.8],[10.974376667,7.860698333,185.4],
        [10.974376667,7.860698333,185.4],[10.974376667,7.860698333,185.4],
        [10.974383333,7.860685,186.2],[10.974385,7.860673333,186.3],
        [10.974395,7.86049,186.0],[10.974395,7.86049,186.0],
        [10.974395,7.86049,186.0],[10.974395,7.86049,186.0],
        [10.974378333,7.860491667,183.8],[10.974315,7.86049,182.3],
        [10.974253333,7.860483333,182.8],[10.974118333,7.860455,184.1],
        [10.974038333,7.860453333,185.4],[10.974038333,7.860453333,185.4],
        [10.974038333,7.860453333,185.4],[10.974038333,7.860453333,185.4],
        [10.974035,7.860471667,186.1],[10.974036667,7.860555,185.7],
        [10.974033333,7.860635,184.6],[10.974033333,7.860635,184.6],
        [10.974043333,7.860608333,183.8],
    ]
    result = normalize_sw_maps_geometry({"type": "Polygon", "coordinates": [ring]})
    ring_out = result["coordinates"][0]

    # All 2D
    assert all(len(c) == 2 for c in ring_out)
    # Closed
    assert ring_out[0] == ring_out[-1]
    # Fewer vertices than input
    assert len(ring_out) < len(ring)
    # No consecutive duplicates
    for i in range(len(ring_out) - 1):
        assert ring_out[i] != ring_out[i + 1]


# ── Passthrough cases ──────────────────────────────────────────────────────────

def test_none_returns_none():
    assert normalize_sw_maps_geometry(None) is None


def test_non_polygon_type_returned_unchanged():
    point = {"type": "Point", "coordinates": [10.0, 7.0]}
    assert normalize_sw_maps_geometry(point) == point


def test_multipolygon_processed():
    ring = [[10.0, 7.0, 183.0], [10.1, 7.0, 183.0], [10.1, 7.1, 183.0],
            [10.0, 7.1, 183.0], [10.0, 7.0, 183.0]]
    result = normalize_sw_maps_geometry(_multipoly(ring))
    ring_out = result["coordinates"][0][0]
    assert all(len(c) == 2 for c in ring_out)
    assert ring_out[0] == ring_out[-1]
