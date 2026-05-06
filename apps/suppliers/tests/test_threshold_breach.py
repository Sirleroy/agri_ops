"""
Threshold-breach behaviour: when geometry normalisation would change the polygon
beyond spec (area Δ > 0.5%, centroid shift > 15m), the import preserves the raw
GPS trace as the geometry of record. No "manual review" warning is emitted —
the operator's mental model stays binary (imported / not imported).
"""
import pytest
from unittest.mock import patch

from apps.companies.models import Company
from apps.suppliers.models import Supplier, Farm
from apps.suppliers.import_pipeline import run_farm_geojson_import

pytestmark = pytest.mark.django_db


def _square(lon0, lat0, side):
    return [
        [lon0,        lat0],
        [lon0 + side, lat0],
        [lon0 + side, lat0 + side],
        [lon0,        lat0 + side],
        [lon0,        lat0],
    ]


def _feature(name, ring):
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {"NAME": name, "Commodity": "Soy"},
    }


@pytest.fixture
def tenant():
    company = Company.objects.create(
        name='Test Co', country='Nigeria', plan_tier='starter'
    )
    supplier = Supplier.objects.create(
        company=company, name='Test Supplier', category='seeds'
    )
    return company, supplier


def test_threshold_breach_keeps_raw_as_geometry_of_record(tenant):
    company, supplier = tenant
    raw_ring = _square(7.0, 9.0, side=0.010)
    smaller  = {"type": "Polygon", "coordinates": [_square(7.0, 9.0, side=0.007)]}

    with patch(
        'apps.suppliers.forms.normalize_field_gps_geometry',
        return_value=smaller,
    ):
        result = run_farm_geojson_import(
            company=company, supplier=supplier, features=[_feature('raw_kept', raw_ring)]
        )

    assert result['created'] == 1
    farm = Farm.objects.get(name='raw_kept')
    assert farm.geolocation['coordinates'] == [raw_ring]
    assert farm.raw_geolocation is None

    # No row warning about manual review or threshold breach
    breach_phrases = ('manual review', 'threshold', 'spec thresholds')
    for w in result['warnings']:
        for issue in w['issues']:
            issue_lower = issue.lower()
            for phrase in breach_phrases:
                assert phrase not in issue_lower, f"unexpected breach warning: {issue}"

    geom_events = [t for t in result['transformations'] if t['field'] == 'geometry']
    assert len(geom_events) == 1
    assert geom_events[0]['reason'] == 'geometry_raw_preserved'
    assert geom_events[0]['severity'] == 'info'
    assert geom_events[0]['detail']['threshold_breach']
    assert geom_events[0]['detail']['would_change_area_pct'] is not None


def test_within_threshold_normalisation_is_applied(tenant):
    company, supplier = tenant
    raw_ring = _square(7.5, 9.5, side=0.010)

    # Stub the candidate to be visibly different from raw but within tolerance —
    # one vertex shifted by ~0.000001° (≈11 cm). Triggers a transformation event
    # but the area delta stays well under the 0.5% threshold.
    near_identical = _square(7.5, 9.5, side=0.010)
    near_identical[1] = [7.510001, 9.5]
    candidate = {"type": "Polygon", "coordinates": [near_identical]}

    with patch(
        'apps.suppliers.forms.normalize_field_gps_geometry',
        return_value=candidate,
    ):
        result = run_farm_geojson_import(
            company=company, supplier=supplier, features=[_feature('clean', raw_ring)]
        )

    assert result['created'] == 1
    farm = Farm.objects.get(name='clean')
    assert farm.geolocation == candidate
    assert farm.raw_geolocation == {"type": "Polygon", "coordinates": [raw_ring]}

    geom_events = [t for t in result['transformations'] if t['field'] == 'geometry']
    assert len(geom_events) == 1
    assert geom_events[0]['reason'] == 'geometry_normalised'


def test_no_geometry_change_logs_clean_event(tenant):
    company, supplier = tenant
    raw_ring = _square(8.0, 10.0, side=0.010)

    # Stub returns the input unchanged — no normalisation needed
    raw_geom = {"type": "Polygon", "coordinates": [raw_ring]}
    with patch(
        'apps.suppliers.forms.normalize_field_gps_geometry',
        return_value=raw_geom,
    ):
        result = run_farm_geojson_import(
            company=company, supplier=supplier, features=[_feature('untouched', raw_ring)]
        )

    assert result['created'] == 1
    farm = Farm.objects.get(name='untouched')
    assert farm.geolocation == raw_geom
    assert farm.raw_geolocation is None

    geom_events = [t for t in result['transformations'] if t['field'] == 'geometry']
    assert len(geom_events) == 1
    assert geom_events[0]['reason'] == 'geometry_clean'


def test_threshold_breach_hash_matches_raw(tenant):
    """Integrity invariant: whatever lands on Farm.geolocation is what's hashed."""
    import hashlib
    import json
    company, supplier = tenant
    raw_ring = _square(7.0, 9.0, side=0.010)
    smaller  = {"type": "Polygon", "coordinates": [_square(7.0, 9.0, side=0.007)]}

    with patch(
        'apps.suppliers.forms.normalize_field_gps_geometry',
        return_value=smaller,
    ):
        run_farm_geojson_import(
            company=company, supplier=supplier, features=[_feature('hashed', raw_ring)]
        )

    farm = Farm.objects.get(name='hashed')
    expected = hashlib.sha256(
        json.dumps(farm.geolocation, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()
    assert farm.geometry_hash == expected
