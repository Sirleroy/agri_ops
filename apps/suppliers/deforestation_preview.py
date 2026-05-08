"""
Deforestation preview — one-shot intersection check against Hansen GFC tiles.

Preview only: results are displayed but never persisted. This view exists so
operators can run checks against real farm data before the full DeforestationCheck
model and async pipeline are built.
"""
import os
from pathlib import Path

from django.conf import settings
from django.views import View
from django.shortcuts import render

from apps.users.permissions import StaffRequiredMixin
from .models import Farm, Supplier


EUDR_CUTOFF_YEAR = 20   # pixel value > 20 → loss after 2020 (EUDR reference date)
TILE_NODATA      = 255


GFC_GCS_BASE = (
    "https://storage.googleapis.com/earthenginepartners-hansen/"
    "GFC-2024-v1.12/Hansen_GFC-2024-v1.12_lossyear_{tile}.tif"
)


def _tile_label(lon, lat):
    import math
    top_lat  = int(math.ceil(lat  / 10) * 10)
    left_lon = int(math.floor(lon / 10) * 10)
    return (f"{abs(top_lat):02d}{'N' if top_lat >= 0 else 'S'}_"
            f"{abs(left_lon):03d}{'E' if left_lon >= 0 else 'W'}")


def _find_tile(lon, lat):
    """
    Return a tile path/URL for the given lon/lat.

    Priority:
      1. Local file in GFC_TILE_DIR — fast, works offline, preferred for dev.
      2. /vsicurl/ streaming from GCS — works on any server with internet access,
         fetches only the bytes covering the farm polygon via HTTP range requests.

    Returns a string (local path or /vsicurl/ URL), or None if both are unavailable.
    """
    label    = _tile_label(lon, lat)
    tile_dir = Path(getattr(settings, 'GFC_TILE_DIR', ''))
    local    = tile_dir / f"lossyear_{label}.tif"
    if local.exists():
        return str(local)
    return f"/vsicurl/{GFC_GCS_BASE.format(tile=label)}"


def _check_farm(geojson, tile_path):
    """
    Run Hansen GFC intersection for one farm polygon.
    Returns dict: pixels, loss_pixels, loss_area_ha, loss_years, result, error.
    """
    try:
        import numpy as np
        import rasterio
        from rasterio.mask import mask as rio_mask

        # Strip Z coordinates — rasterio works in 2D
        coords = geojson.get('coordinates', [])
        geom_2d = {
            'type': 'Polygon',
            'coordinates': [[[c[0], c[1]] for c in ring] for ring in coords],
        }

        with rasterio.open(tile_path) as src:
            pixel_area_ha = (src.res[0] * 111_320) * (src.res[1] * 110_540) / 10_000
            out, _ = rio_mask(src, [geom_2d], crop=True, nodata=TILE_NODATA)
            arr   = out[0]
            valid = arr[arr != TILE_NODATA]

            loss_px    = int(np.sum(valid > EUDR_CUTOFF_YEAR))
            loss_years = sorted({int(y) for y in valid[valid > EUDR_CUTOFF_YEAR]})
            loss_ha    = round(loss_px * pixel_area_ha, 4)

        return {
            'pixels':      len(valid),
            'loss_pixels': loss_px,
            'loss_area_ha': loss_ha,
            'loss_years':  loss_years,
            'result':      'CLEAR' if loss_px == 0 else 'FLAGGED',
            'error':       None,
        }
    except Exception as e:
        return {
            'pixels': 0, 'loss_pixels': 0, 'loss_area_ha': 0,
            'loss_years': [], 'result': 'ERROR', 'error': str(e),
        }


class DeforestationPreviewView(StaffRequiredMixin, View):

    def _suppliers(self, request):
        return Supplier.objects.filter(company=request.user.company).order_by('name')

    def get(self, request):
        return render(request, 'suppliers/farms/deforestation_preview.html', {
            'suppliers': self._suppliers(request),
        })

    def post(self, request):
        supplier_id = request.POST.get('supplier_id') or None
        company     = request.user.company

        farms_qs = Farm.objects.filter(company=company).select_related('supplier')
        if supplier_id:
            farms_qs = farms_qs.filter(supplier_id=supplier_id)

        results = []
        no_geom = 0

        for farm in farms_qs.order_by('name'):
            if not farm.geolocation:
                no_geom += 1
                continue

            geom = farm.geolocation
            # Use centroid of outer ring to select tile
            try:
                ring = geom['coordinates'][0]
                lon  = sum(c[0] for c in ring) / len(ring)
                lat  = sum(c[1] for c in ring) / len(ring)
            except Exception:
                no_geom += 1
                continue

            tile  = _find_tile(lon, lat)
            check = _check_farm(geom, tile)
            results.append({'farm': farm, **check})

        flagged = sum(1 for r in results if r['result'] == 'FLAGGED')
        clear   = sum(1 for r in results if r['result'] == 'CLEAR')
        errors  = sum(1 for r in results if r['result'] == 'ERROR')

        return render(request, 'suppliers/farms/deforestation_preview.html', {
            'suppliers':   self._suppliers(request),
            'selected_id': int(supplier_id) if supplier_id else None,
            'results':     results,
            'flagged':     flagged,
            'clear':       clear,
            'errors':      errors,
            'no_geom':     no_geom,
            'total':       len(results),
        })
