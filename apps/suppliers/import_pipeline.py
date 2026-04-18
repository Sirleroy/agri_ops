"""
Farm import pipeline — service layer.

All file parsing, geometry normalisation, validation, and bulk-create logic
lives here. Neither views nor the API endpoint contain this logic directly;
both call into this module.

Public API:
    parse_file_to_features(geojson_file)  → (features, error_message)
    run_farm_geojson_import(...)           → result dict
"""


def _wkt_csv_to_features(csv_text):
    """
    Convert a WKT-geometry CSV export to a list of GeoJSON Feature dicts.
    Expects a 'geometry' (or 'wkt' / 'geom') column containing WKT polygon data —
    the standard export format of SW Maps, Avenza Maps, QGIS, and most GIS tools.
    Returns (features, error_message) — error_message is None on success.
    """
    import csv as _csv
    import io
    reader = _csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    if not rows:
        return [], "CSV file is empty."

    headers = reader.fieldnames or []
    geom_col = next(
        (c for c in ('geometry', 'Geometry', 'GEOMETRY', 'wkt', 'WKT', 'geom', 'GEOM')
         if c in headers),
        None,
    )
    if not geom_col:
        return [], (
            "No geometry column found in CSV. "
            "Your mapping app should export a 'geometry' column containing the polygon boundary as WKT. "
            "Try exporting as GeoJSON instead — most apps offer this under File → Export → GeoJSON."
        )

    try:
        from shapely import wkt as shapely_wkt
        from shapely.geometry import mapping as shapely_mapping
    except ImportError:
        return [], "Shapely is required to read WKT geometry from CSV files."

    features = []
    for row in rows:
        wkt_str = (row.get(geom_col) or '').strip()
        if not wkt_str:
            continue
        try:
            geometry = dict(shapely_mapping(shapely_wkt.loads(wkt_str)))
        except Exception:
            geometry = None
        features.append({
            'type': 'Feature',
            'geometry': geometry,
            'properties': {k: v for k, v in row.items() if k != geom_col},
        })

    return features, None


def parse_file_to_features(geojson_file):
    """Parse one uploaded file to a list of GeoJSON feature dicts.
    Returns (features, error_message). error_message is None on success."""
    import json, zipfile, io
    fname = geojson_file.name.lower()

    if fname.endswith('.zip'):
        try:
            zf = zipfile.ZipFile(io.BytesIO(geojson_file.read()))
        except zipfile.BadZipFile:
            return [], 'The ZIP file is corrupted or not a valid ZIP archive.'
        geojson_names = [
            n for n in zf.namelist()
            if n.lower().endswith(('.geojson', '.json')) and not n.startswith('__MACOSX')
        ]
        if not geojson_names:
            return [], ('No GeoJSON file found inside the ZIP. '
                        'Export from your mapping app as GeoJSON and try again.')
        merged, read_errors = [], []
        for inner in geojson_names:
            try:
                data = json.loads(zf.read(inner).decode('utf-8'))
                if isinstance(data, dict) and data.get('type') == 'FeatureCollection':
                    merged.extend(data.get('features') or [])
                elif isinstance(data, list):
                    merged.extend(data)
            except Exception as e:
                read_errors.append(f'{inner}: {e}')
        if read_errors and not merged:
            return [], 'Could not read any GeoJSON from the ZIP: ' + '; '.join(read_errors)
        if not merged:
            return [], 'The GeoJSON files inside the ZIP contain no features.'
        return merged, None

    if fname.endswith('.csv'):
        try:
            csv_text = geojson_file.read().decode('utf-8-sig')
        except Exception as e:
            return [], f'Could not read file: {e}'
        features, csv_err = _wkt_csv_to_features(csv_text)
        return ([], csv_err) if csv_err else (features, None)

    if fname.endswith(('.geojson', '.json')):
        try:
            data = json.loads(geojson_file.read().decode('utf-8'))
        except Exception as e:
            return [], f'Could not read file: {e}'
        if isinstance(data, list):
            return data, None
        if isinstance(data, dict) and data.get('type') == 'FeatureCollection':
            return data.get('features') or [], None
        return [], 'File must be a GeoJSON FeatureCollection.'

    return [], 'File must be a GeoJSON (.geojson, .json), WKT CSV (.csv), or ZIP export.'


def run_farm_geojson_import(company, supplier, features, default_commodity='', dry_run=False):
    """
    Core GeoJSON import pipeline — called by both the web view and the API endpoint.
    Runs all validation layers and bulk-creates passing farms (unless dry_run=True).
    Returns a result dict: {total, created, duplicates, blocked, errors, error_detail,
                            blocked_detail, warnings, transformations, dry_run}

    transformations is a list of auditable normalisation events — one entry per
    field change applied silently during import (LGA fuzzy-match, geometry repair,
    commodity canonicalisation, farmer record merge). Stored in FarmImportLog so
    the origin of every stored value is explainable under audit.
    """
    from django import forms as django_forms
    from django.db import transaction
    from .models import Farm, Farmer
    from .forms import _validate_geojson_polygon, _find_overlapping_farm, normalize_field_gps_geometry, _compute_area_ha
    from .ng_geodata import canonicalise_lga_state, normalise_commodity

    # Accept a FeatureCollection dict as well as a plain list
    if isinstance(features, dict) and features.get('type') == 'FeatureCollection':
        features = features.get('features') or []

    to_create      = []
    duplicates     = []
    blocked        = []
    errors         = []
    warnings       = []
    transformations = []  # auditable normalisation events
    auto_corrected = 0
    farmer_cache   = {}  # (first_name_lower, last_name_lower, village_lower, lga_lower) -> Farmer
    batch_shapes   = []  # (shape, name) — intra-batch overlap guard

    for i, feature in enumerate(features):
        row = i + 1
        raw_props = feature.get('properties') or {}
        props     = {k.strip().lower(): v for k, v in raw_props.items()}
        geometry  = feature.get('geometry')

        def _s(val):
            """Coerce a GeoJSON property value to a stripped string."""
            if val is None:
                return ''
            # Floats like 8135099470.0 should become '8135099470'
            if isinstance(val, float) and val == int(val):
                return str(int(val))
            return str(val).strip()

        name = (
            _s(props.get('name') or props.get('farm_name') or props.get('farm name')) or
            f"Farm {row}"
        )

        first_name   = _s(props.get('first name') or props.get('first_name')).title()
        last_name    = _s(props.get('last name')  or props.get('last_name')).title()
        farmer_label = f"{first_name} {last_name}".strip()
        phone_raw    = _s(props.get('phone number') or props.get('phone_number') or props.get('phone'))
        village      = _s(props.get('village')).title()
        lga_raw      = _s(props.get('lga'))
        state_raw    = _s(props.get('state') or props.get('state_region') or props.get('region'))
        lga, state_region = canonicalise_lga_state(lga_raw, state_raw)
        commodity_raw = _s(props.get('commodity')) or default_commodity or 'Unknown'
        commodity     = normalise_commodity(commodity_raw)

        # Track geometry auto-correction (3D→2D, dedup, close ring, simplify, buffer(0) repair)
        raw_geometry = geometry
        if geometry:
            geometry = normalize_field_gps_geometry(geometry)

        # ── Transformation events ────────────────────────────────────────────
        # LGA canonicalization: fuzzy-matched if the resolved value differs from raw input
        lga_was_corrected = bool(lga_raw) and lga.strip().lower() != lga_raw.strip().lower()
        if lga_was_corrected:
            transformations.append({
                'row': row, 'farm': name, 'field': 'lga',
                'from': lga_raw, 'to': lga, 'reason': 'fuzzy_match',
            })

        geom_was_corrected = bool(raw_geometry) and geometry != raw_geometry
        if geom_was_corrected:
            transformations.append({
                'row': row, 'farm': name, 'field': 'geometry',
                'from': None, 'to': None, 'reason': 'geometry_normalised',
            })

        commodity_was_corrected = (
            commodity_raw.strip().lower() != commodity.strip().lower()
            and commodity != 'Unknown'
        )
        if commodity_was_corrected:
            transformations.append({
                'row': row, 'farm': name, 'field': 'commodity',
                'from': commodity_raw, 'to': commodity, 'reason': 'canonical_name',
            })

        if lga_was_corrected or geom_was_corrected:
            auto_corrected += 1

        # Area computed from normalized polygon — file metadata is ignored
        area = _compute_area_ha(geometry) if geometry else None

        try:
            _validate_geojson_polygon(geometry)
        except django_forms.ValidationError as e:
            errors.append({'row': row, 'name': name, 'reason': e.messages[0]})
            continue

        if Farm.objects.filter(company=company, supplier=supplier, name__iexact=name).exists():
            duplicates.append({'row': row, 'name': name})
            continue

        overlapping = _find_overlapping_farm(geometry, company)
        if overlapping:
            blocked.append({'row': row, 'name': name,
                            'reason': f"Overlaps with existing farm '{overlapping.name}' ({overlapping.supplier.name})"})
            continue

        # Intra-batch overlap: check against farms already accepted in this run
        from .forms import _geojson_to_shape
        new_shape = _geojson_to_shape(geometry) if geometry else None
        if new_shape:
            intra_clash = next(
                (n for s, n in batch_shapes
                 if s.intersection(new_shape).area > 0),
                None,
            )
            if intra_clash:
                blocked.append({'row': row, 'name': name,
                                'reason': f"Overlaps with '{intra_clash}' in this same file"})
                continue
            batch_shapes.append((new_shape, name))

        # Completeness warnings (commodity checked after farmer resolution below)
        row_warnings = []
        if not farmer_label:
            row_warnings.append("No farmer name found — check 'First Name' and 'Last Name' columns.")
        if not lga:
            row_warnings.append("LGA missing — add an 'LGA' column or fill it in after import.")
        if area and area > 200:
            row_warnings.append(f"Declared area ({area} ha) is unusually large — verify this is correct.")

        linked_farmer = None
        if first_name:
            cache_key = (first_name.lower(), last_name.lower(), village.lower(), lga.lower())
            if cache_key in farmer_cache:
                linked_farmer = farmer_cache[cache_key]
                # farmer was already resolved this import — no new transformation event
            else:
                q = Farmer.objects.filter(
                    company=company,
                    first_name__iexact=first_name,
                    last_name__iexact=last_name,
                )
                if village:
                    q = q.filter(village__iexact=village)
                if lga:
                    q = q.filter(lga__iexact=lga)
                linked_farmer = q.first()
                if linked_farmer is not None:
                    transformations.append({
                        'row': row, 'farm': name, 'field': 'farmer',
                        'from': farmer_label,
                        'to': f"pk={linked_farmer.pk} ({linked_farmer.full_name})",
                        'reason': 'farmer_merged',
                    })
                elif not dry_run:
                    linked_farmer = Farmer.objects.create(
                        company=company,
                        first_name=first_name,
                        last_name=last_name,
                        phone=phone_raw,
                        village=village,
                        lga=lga,
                    )
                farmer_cache[cache_key] = linked_farmer

        # Fall back to farmer's registered crops if commodity is still unknown
        if commodity == 'Unknown' and linked_farmer and linked_farmer.crops:
            first_crop = linked_farmer.crops.split(',')[0].strip()
            if first_crop:
                commodity = normalise_commodity(first_crop)

        if commodity == 'Unknown':
            row_warnings.append("Commodity not in file — set a Default Commodity above, or add a 'Commodity' column.")
        if row_warnings:
            warnings.append({'row': row, 'name': name, 'issues': row_warnings})

        to_create.append(Farm(
            company=company,
            supplier=supplier,
            name=name,
            farmer=linked_farmer,
            farmer_name=farmer_label,
            geolocation=geometry,
            area_hectares=area,
            country='Nigeria',
            state_region=state_region,
            commodity=commodity,
            deforestation_risk_status='standard',
            is_eudr_verified=False,
        ))

    created_count = 0
    created_names = []
    if not dry_run:
        with transaction.atomic():
            for j in range(0, len(to_create), 50):
                batch = to_create[j:j + 50]
                Farm.objects.bulk_create(batch)
                created_count += len(batch)
        created_names = [f.name for f in to_create]

        # Attach farm PKs to warnings so the UI can link straight to the edit page
        if warnings:
            warning_names = {w['name'] for w in warnings}
            pk_by_name = dict(
                Farm.objects.filter(
                    company=company, supplier=supplier, name__in=warning_names
                ).values_list('name', 'pk')
            )
            for w in warnings:
                w['farm_pk'] = pk_by_name.get(w['name'])

    return {
        'total':           len(features),
        'created':         created_count if not dry_run else 0,
        'created_names':   created_names,
        'would_create':    len(to_create),
        'would_create_names': [f.name for f in to_create] if dry_run else [],
        'duplicates':      len(duplicates),
        'blocked':         len(blocked),
        'errors':          len(errors),
        'auto_corrected':  auto_corrected,
        'error_detail':    errors,
        'blocked_detail':  blocked,
        'warnings':        warnings,
        'transformations': transformations,
        'dry_run':         dry_run,
    }
