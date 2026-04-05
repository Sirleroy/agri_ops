import pytest
from django.contrib.gis.geos import GEOSGeometry

def test_valid_polygon_check():
    # A simple valid triangle in Nigeria
    poly_wkt = "POLYGON((7.0 9.0, 8.0 9.0, 8.0 10.0, 7.0 9.0))"
    poly = GEOSGeometry(poly_wkt)
    assert poly.valid is True

def test_coordinate_bomb_prevention():
    # Testing our logic that handles massive/invalid floats
    with pytest.raises(Exception):
        invalid_coord = "999999999.999999999"
        GEOSGeometry(f"POINT({invalid_coord} 9.0)")
