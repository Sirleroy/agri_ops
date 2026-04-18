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


def _geom_vertex_count(geojson):
    """Count total vertices in a GeoJSON Polygon / MultiPolygon (including Z)."""
    if not geojson:
        return 0
    coords = geojson.get('coordinates', [])
    geo_type = geojson.get('type', '')
    try:
        if geo_type == 'Polygon':
            return sum(len(ring) for ring in coords)
        if geo_type == 'MultiPolygon':
            return sum(len(ring) for poly in coords for ring in poly)
    except Exception:
        pass
    return 0


def _geom_centroid(geojson):
    """
    Return (lat, lon) centroid of the outer ring of a GeoJSON Polygon / MultiPolygon.
    Handles both 2D [lon, lat] and 3D [lon, lat, elev] coordinates.
    Returns None if computation fails.
    """
    if not geojson:
        return None
    try:
        geo_type = geojson.get('type', '')
        coords   = geojson.get('coordinates', [])
        if geo_type == 'Polygon' and coords:
            ring = coords[0]
        elif geo_type == 'MultiPolygon' and coords and coords[0]:
            ring = coords[0][0]
        else:
            return None
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        return (sum(lats) / len(lats), sum(lons) / len(lons))
    except Exception:
        return None


def _haversine_m(lat1, lon1, lat2, lon2):
    """Approximate distance in metres between two lat/lon points."""
    import math
    R = 6_371_009
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return round(2 * R * math.asin(min(1.0, math.sqrt(a))), 2)


def _parse_mapping_date(raw):
    """
    Parse a mapping date string from various field-app export formats.
    Tries ISO (YYYY-MM-DD) then DD/MM/YYYY then MM/DD/YYYY.
    Returns a datetime.date or None on failure.
    """
    import datetime
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def run_farm_geojson_import(company, supplier, features, default_commodity='', dry_run=False,
                            simplification_tolerance=0.00005):
    """
    Core GeoJSON import pipeline — called by both the web view and the API endpoint.
    Runs all validation layers and bulk-creates passing farms (unless dry_run=True).
    Returns a result dict: {total, created, duplicates, blocked, errors, error_detail,
                            blocked_detail, warnings, transformations, dry_run}

    transformations is a list of auditable normalisation events.  Each entry has:
      row, farm, field, from, to, reason
    and an optional 'detail' dict with quantitative evidence:
      geometry  → vertex counts, area delta %, centroid shift (m), topology flag
      lga       → fuzzy-match confidence score
      farmer    → match_method, match_fields, match_count (ambiguity signal)
    Stored in FarmImportLog so every stored value is explainable under audit.
    """
    from django import forms as django_forms
    from django.db import transaction
    from .models import Farm, Farmer
    from .forms import _validate_geojson_polygon, _find_overlapping_farm, normalize_field_gps_geometry, _compute_area_ha
    from .ng_geodata import canonicalise_lga_state, normalise_commodity, is_eudr_commodity

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
    batch_names    = set()  # intra-batch name+supplier duplicate guard (case-insensitive)

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

        # ── Provenance metadata ──────────────────────────────────────────────
        field_officer = _s(
            props.get('field officer name') or props.get('field_officer_name') or
            props.get('field officer')      or props.get('officer name') or
            props.get('officer')            or props.get('surveyor') or
            props.get('mapped by')          or props.get('mapped_by_name')
        )
        mapping_date_raw = _s(
            props.get('mapping date') or props.get('mapping_date') or
            props.get('survey date')  or props.get('survey_date') or
            props.get('date mapped')  or props.get('date_mapped')
        )
        mapping_date_parsed = _parse_mapping_date(mapping_date_raw)

        # row_warnings collected throughout — initialised here so all blocks below can append
        row_warnings = []

        # ── Geometry: normalise + always log invariant event ─────────────────
        raw_geometry = geometry
        raw_vertices = _geom_vertex_count(raw_geometry)
        raw_centroid = _geom_centroid(raw_geometry)

        had_elevation = False
        if raw_geometry and raw_geometry.get('coordinates'):
            try:
                outer = raw_geometry['coordinates'][0]
                if raw_geometry.get('type') == 'MultiPolygon':
                    outer = raw_geometry['coordinates'][0][0]
                had_elevation = any(len(c) >= 3 for c in outer)
            except Exception:
                pass

        raw_is_valid = True
        if raw_geometry:
            try:
                from shapely.geometry import shape as _shp
                raw_is_valid = _shp(raw_geometry).is_valid
            except Exception:
                pass

        if geometry:
            geometry = normalize_field_gps_geometry(
                geometry, simplify_tolerance=simplification_tolerance
            )

        geom_was_corrected = bool(raw_geometry) and geometry != raw_geometry

        if raw_geometry:
            # Always emit a geometry event — 'geometry_normalised' if changed,
            # 'geometry_clean' if it passed without modification (invariant guarantee)
            proc_vertices    = _geom_vertex_count(geometry)
            proc_centroid    = _geom_centroid(geometry)
            area_before_m2   = round(_compute_area_ha(raw_geometry) * 10_000, 1) if _compute_area_ha(raw_geometry) else None
            area_after_m2    = round(_compute_area_ha(geometry)     * 10_000, 1) if _compute_area_ha(geometry)     else None
            area_delta_pct   = None
            if area_before_m2 and area_after_m2 and area_before_m2 > 0:
                area_delta_pct = round(abs(area_after_m2 - area_before_m2) / area_before_m2 * 100, 2)
            centroid_shift_m = None
            if raw_centroid and proc_centroid:
                centroid_shift_m = _haversine_m(
                    raw_centroid[0], raw_centroid[1],
                    proc_centroid[0], proc_centroid[1],
                )
            vertex_reduction_pct = (
                round((1 - proc_vertices / raw_vertices) * 100)
                if raw_vertices > 0 else 0
            )
            transformations.append({
                'row': row, 'farm': name, 'field': 'geometry',
                'from': None, 'to': None,
                'reason': 'geometry_normalised' if geom_was_corrected else 'geometry_clean',
                'detail': {
                    'had_elevation':          had_elevation,
                    'had_duplicates':         raw_vertices > proc_vertices,
                    'topology_repaired':      not raw_is_valid,
                    'topology_valid':         raw_is_valid or True,
                    'vertex_count_before':    raw_vertices,
                    'vertex_count_after':     proc_vertices,
                    'vertex_reduction_pct':   vertex_reduction_pct,
                    'area_before_m2':         area_before_m2,
                    'area_after_m2':          area_after_m2,
                    'area_delta_pct':         area_delta_pct,
                    'centroid_shift_m':       centroid_shift_m,
                    'simplification_tolerance': simplification_tolerance,
                },
            })

        # ── LGA canonicalisation — tiered confidence response ────────────────
        import difflib as _difflib
        lga_was_corrected = bool(lga_raw) and lga.strip().lower() != lga_raw.strip().lower()
        if lga_was_corrected:
            confidence = round(
                _difflib.SequenceMatcher(None, lga_raw.strip().lower(), lga.strip().lower()).ratio(), 3
            )
            transformations.append({
                'row': row, 'farm': name, 'field': 'lga',
                'from': lga_raw, 'to': lga, 'reason': 'fuzzy_match',
                'detail': {'confidence': confidence},
            })
            # Below 0.90 confidence: correct but surface a warning for human review
            if confidence < 0.90:
                row_warnings.append(
                    f"LGA '{lga_raw}' was fuzzy-matched to '{lga}' "
                    f"(confidence {confidence}) — verify this is correct."
                )

        # ── Commodity controlled-vocabulary enforcement ───────────────────────
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

        # ── Source area comparison (device-reported vs computed) ─────────────
        # Compares the AREA property from the mapping app against the value we
        # computed from the polygon.  Unit inferred by whichever match is closer.
        source_area_raw = _s(
            raw_props.get('AREA') or raw_props.get('area') or raw_props.get('Area')
        )
        if source_area_raw and area:
            try:
                source_val = float(source_area_raw)
                computed_ha = float(area)
                if source_val > 0 and computed_ha > 0:
                    computed_m2   = computed_ha * 10_000
                    diff_if_ha = abs(source_val - computed_ha) / computed_ha
                    diff_if_m2 = abs(source_val - computed_m2) / computed_m2
                    if diff_if_m2 <= diff_if_ha:
                        unit_inferred  = 'm2'
                        computed_same  = round(computed_m2, 1)
                        delta_pct      = round(diff_if_m2 * 100, 2)
                    else:
                        unit_inferred  = 'ha'
                        computed_same  = round(computed_ha, 4)
                        delta_pct      = round(diff_if_ha * 100, 2)
                    transformations.append({
                        'row': row, 'farm': name, 'field': 'area',
                        'from': f"{source_val} ({unit_inferred})",
                        'to':   f"{computed_same} ({unit_inferred})",
                        'reason': 'area_source_comparison',
                        'detail': {
                            'source_area':      source_val,
                            'computed_area_ha': computed_ha,
                            'unit_inferred':    unit_inferred,
                            'delta_pct':        delta_pct,
                        },
                    })
            except (ValueError, ZeroDivisionError, TypeError):
                pass

        # ── EUDR commodity scope check ────────────────────────────────────────
        if commodity and commodity != 'Unknown' and not is_eudr_commodity(commodity):
            row_warnings.append(
                f"'{commodity}' is not an EUDR Annex I commodity — "
                "standard EUDR due-diligence rules do not apply. "
                "Verify the correct commodity is recorded."
            )

        try:
            _validate_geojson_polygon(geometry)
        except django_forms.ValidationError as e:
            errors.append({'row': row, 'name': name, 'reason': e.messages[0]})
            continue

        if Farm.objects.filter(company=company, supplier=supplier, name__iexact=name).exists():
            duplicates.append({'row': row, 'name': name})
            continue

        if name.lower() in batch_names:
            duplicates.append({'row': row, 'name': name})
            continue

        overlapping = _find_overlapping_farm(geometry, company)
        if overlapping:
            sup_label = overlapping.supplier.name if overlapping.supplier else 'no supplier'
            blocked.append({'row': row, 'name': name,
                            'reason': f"Overlaps with existing farm '{overlapping.name}' ({sup_label})"})
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

        batch_names.add(name.lower())

        # Completeness warnings (commodity checked after farmer resolution below)
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
                # Build query progressively, tracking which fields are used
                q = Farmer.objects.filter(
                    company=company,
                    first_name__iexact=first_name,
                    last_name__iexact=last_name,
                )
                match_fields = ['first_name', 'last_name']
                if village:
                    q = q.filter(village__iexact=village)
                    match_fields.append('village')
                if lga:
                    q = q.filter(lga__iexact=lga)
                    match_fields.append('lga')

                match_count   = q.count()
                linked_farmer = q.first()

                if linked_farmer is not None:
                    method = 'ambiguous_exact' if match_count > 1 else 'exact'
                    transformations.append({
                        'row': row, 'farm': name, 'field': 'farmer',
                        'from': farmer_label,
                        'to': f"pk={linked_farmer.pk} ({linked_farmer.full_name})",
                        'reason': 'farmer_merged',
                        'detail': {
                            'match_method': method,
                            'match_fields': match_fields,
                            'match_count':  match_count,
                        },
                    })
                    if match_count > 1:
                        row_warnings.append(
                            f"Farmer name '{farmer_label}' matched {match_count} existing records — "
                            f"first match (pk={linked_farmer.pk}) used. Verify identity manually."
                        )
                elif not dry_run:
                    linked_farmer = Farmer.objects.create(
                        company=company,
                        first_name=first_name,
                        last_name=last_name,
                        phone=phone_raw,
                        village=village,
                        lga=lga,
                    )
                    transformations.append({
                        'row': row, 'farm': name, 'field': 'farmer',
                        'from': farmer_label,
                        'to': f"pk={linked_farmer.pk} (new record)",
                        'reason': 'farmer_created',
                        'detail': {
                            'match_method': 'created',
                            'match_fields': match_fields,
                            'match_count':  0,
                        },
                    })
                farmer_cache[cache_key] = linked_farmer

        # Fall back to farmer's registered crops if commodity is still unknown
        if commodity == 'Unknown' and linked_farmer and linked_farmer.crops:
            first_crop = linked_farmer.crops.split(',')[0].strip()
            if first_crop:
                commodity = normalise_commodity(first_crop)
                transformations.append({
                    'row': row, 'farm': name, 'field': 'commodity',
                    'from': 'Unknown (not in file)',
                    'to': commodity,
                    'reason': 'farmer_crop_fallback',
                })

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
            mapped_by_name=field_officer,
            mapping_date=mapping_date_parsed,
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
