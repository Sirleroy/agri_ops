"""
Deforestation intersection engine.

Checks a farm polygon against Hansen GFC lossyear raster tiles.
Persists results into DeforestationCheck and updates Farm.deforestation_risk_status.

Callable from:
  - DeforestationPreviewView (tenant UI, per-supplier batch)
  - run_deforestation_checks management command (CLI, any scope)
"""
import math
from pathlib import Path

from django.conf import settings
from django.utils import timezone


EUDR_CUTOFF_YEAR = 20   # pixel value > 20 → loss after 2020
TILE_NODATA      = 255
DATASET_NAME     = 'Hansen GFC'
DATASET_VERSION  = 'v1.12'

GFC_GCS_BASE = (
    "https://storage.googleapis.com/earthenginepartners-hansen/"
    "GFC-2024-v1.12/Hansen_GFC-2024-v1.12_lossyear_{tile}.tif"
)

# Map engine risk_status → Farm.deforestation_risk_status
_RISK_MAP = {
    'clear':        'low',
    'flagged':      'high',
    'inconclusive': 'standard',
    'error':        None,   # don't overwrite farm status on engine error
}


def tile_label(lon, lat):
    top_lat  = int(math.ceil(lat  / 10) * 10)
    left_lon = int(math.floor(lon / 10) * 10)
    return (f"{abs(top_lat):02d}{'N' if top_lat >= 0 else 'S'}_"
            f"{abs(left_lon):03d}{'E' if left_lon >= 0 else 'W'}")


def find_tile(lon, lat):
    """Local file first; fall back to /vsicurl/ HTTP range streaming."""
    label    = tile_label(lon, lat)
    tile_dir = Path(getattr(settings, 'GFC_TILE_DIR', ''))
    local    = tile_dir / f"lossyear_{label}.tif"
    if local.exists():
        return str(local)
    return f"/vsicurl/{GFC_GCS_BASE.format(tile=label)}"


def intersect_farm(geojson, tile_path):
    """
    Run the rasterio intersection for one farm polygon.
    Returns a dict: pixels, loss_pixels, loss_area_ha, loss_years, risk_status, error.
    """
    try:
        import numpy as np
        import rasterio
        from rasterio.mask import mask as rio_mask

        coords  = geojson.get('coordinates', [])
        geom_2d = {
            'type': 'Polygon',
            'coordinates': [[[c[0], c[1]] for c in ring] for ring in coords],
        }

        with rasterio.open(tile_path) as src:
            pixel_area_ha = (src.res[0] * 111_320) * (src.res[1] * 110_540) / 10_000
            out, _  = rio_mask(src, [geom_2d], crop=True, nodata=TILE_NODATA)
            arr     = out[0]
            valid   = arr[arr != TILE_NODATA]
            loss_px = int(np.sum(valid > EUDR_CUTOFF_YEAR))
            loss_years = sorted({int(y) for y in valid[valid > EUDR_CUTOFF_YEAR]})
            loss_ha    = round(loss_px * pixel_area_ha, 4)

        return {
            'pixels':        len(valid),
            'loss_pixels':   loss_px,
            'loss_area_ha':  loss_ha,
            'loss_years':    loss_years,
            'risk_status':   'clear' if loss_px == 0 else 'flagged',
            'error':         None,
        }
    except Exception as exc:
        return {
            'pixels': 0, 'loss_pixels': 0, 'loss_area_ha': 0,
            'loss_years': [], 'risk_status': 'error', 'error': str(exc),
        }


def _centroid(geojson):
    """Return (lon, lat) centroid of the outer ring, or None if unparseable."""
    try:
        ring = geojson['coordinates'][0]
        lon  = sum(c[0] for c in ring) / len(ring)
        lat  = sum(c[1] for c in ring) / len(ring)
        return lon, lat
    except Exception:
        return None


def run_check(farm, user=None):
    """
    Run the deforestation check for a single Farm instance.

    - Creates a DeforestationCheck record.
    - Updates Farm.deforestation_risk_status if the engine returns a definitive result.
    - Returns the DeforestationCheck instance.
    """
    from apps.suppliers.models import DeforestationCheck

    if not farm.geolocation:
        check = DeforestationCheck.objects.create(
            farm=farm,
            company=farm.company,
            dataset_name=DATASET_NAME,
            dataset_version=DATASET_VERSION,
            risk_status='inconclusive',
            engine_status='failed',
            error_detail='Farm has no GPS polygon.',
            geometry_hash_at_assessment=farm.geometry_hash,
            assessed_at=timezone.now(),
            checked_by=user,
        )
        return check

    centroid = _centroid(farm.geolocation)
    if centroid is None:
        check = DeforestationCheck.objects.create(
            farm=farm,
            company=farm.company,
            dataset_name=DATASET_NAME,
            dataset_version=DATASET_VERSION,
            risk_status='inconclusive',
            engine_status='failed',
            error_detail='Could not compute polygon centroid.',
            geometry_hash_at_assessment=farm.geometry_hash,
            assessed_at=timezone.now(),
            checked_by=user,
        )
        return check

    lon, lat  = centroid
    tile_path = find_tile(lon, lat)
    result    = intersect_farm(farm.geolocation, tile_path)

    # Build evidence summary
    if result['risk_status'] == 'clear':
        summary = (
            f"No post-2020 tree cover loss detected. "
            f"Total pixels sampled: {result['pixels']}. "
            f"Dataset: {DATASET_NAME} {DATASET_VERSION}."
        )
    elif result['risk_status'] == 'flagged':
        years_str = ', '.join(str(2000 + y) for y in result['loss_years'])
        summary = (
            f"Tree cover loss detected after 2020. "
            f"Loss area: {result['loss_area_ha']} ha ({result['loss_pixels']} pixels). "
            f"Loss years: {years_str}. "
            f"Dataset: {DATASET_NAME} {DATASET_VERSION}."
        )
    else:
        summary = f"Check failed: {result['error']}"

    check = DeforestationCheck.objects.create(
        farm=farm,
        company=farm.company,
        dataset_name=DATASET_NAME,
        dataset_version=DATASET_VERSION,
        total_pixels=result['pixels'],
        post_cutoff_loss_pixels=result['loss_pixels'],
        post_cutoff_loss_area_ha=result['loss_area_ha'] if result['loss_pixels'] else None,
        loss_years_detected=[2000 + y for y in result['loss_years']],
        risk_status=result['risk_status'],
        engine_status='complete' if result['risk_status'] != 'error' else 'failed',
        evidence_summary=summary,
        error_detail=result['error'] or '',
        geometry_hash_at_assessment=farm.geometry_hash,
        assessed_at=timezone.now(),
        checked_by=user,
    )

    farm_risk = _RISK_MAP.get(result['risk_status'])
    if farm_risk is not None:
        farm.deforestation_risk_status = farm_risk
        farm.save(update_fields=['deforestation_risk_status'])

    return check
