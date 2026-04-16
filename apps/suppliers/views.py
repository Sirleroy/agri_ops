from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, render
from .models import Supplier, Farm, FarmCertification, Farmer
from .forms import FarmerForm, FarmForm, FarmUpdateForm, _compute_area_ha
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin, DatePickerMixin, OtherRevealMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin


# ─────────────────────────────────────
# FARMER VIEWS
# ─────────────────────────────────────

def _farmer_filter_qs(base_qs, params):
    """Apply URL params to a Farmer queryset. Returns (filtered_qs, active_filters_dict)."""
    filters = {}
    lga     = params.get('lga', '').strip()
    village = params.get('village', '').strip()
    if lga:
        base_qs = base_qs.filter(lga__icontains=lga)
        filters['lga'] = lga
    if village:
        base_qs = base_qs.filter(village__icontains=village)
        filters['village'] = village
    return base_qs, filters


class FarmerListView(StaffRequiredMixin, ListView):
    model = Farmer
    template_name = 'suppliers/farmers/list.html'
    context_object_name = 'farmers'
    paginate_by = 50

    def get_queryset(self):
        qs = Farmer.objects.filter(company=self.request.user.company)
        qs, _ = _farmer_filter_qs(qs, self.request.GET)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        _, ctx['active_filters'] = _farmer_filter_qs(
            Farmer.objects.none(), self.request.GET
        )
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['filter_qs'] = params.urlencode()
        return ctx


class FarmerDetailView(StaffRequiredMixin, DetailView):
    model = Farmer
    template_name = 'suppliers/farmers/detail.html'
    context_object_name = 'farmer'

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['farms'] = self.object.farms.filter(
            company=self.request.user.company
        ).select_related('supplier').order_by('name')
        return context


class FarmerCreateView(DatePickerMixin, AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = Farmer
    template_name = 'suppliers/farmers/form.html'
    form_class = FarmerForm
    success_url = reverse_lazy('suppliers:farmer_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.request.user.company
        return kwargs

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)


class FarmerUpdateView(DatePickerMixin, AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = Farmer
    template_name = 'suppliers/farmers/form.html'
    form_class = FarmerForm
    success_url = reverse_lazy('suppliers:farmer_list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.request.user.company
        return kwargs


class FarmerExportView(StaffRequiredMixin, View):
    def get(self, request):
        from .exports import farmer_registry_csv, farmer_registry_pdf
        fmt     = request.GET.get('format', 'csv')
        company = request.user.company
        base_qs = Farmer.objects.filter(company=company)
        filter_params = request.GET.copy()
        filter_params.pop('format', None)
        qs, _   = _farmer_filter_qs(base_qs, filter_params)
        if fmt == 'pdf':
            return farmer_registry_pdf(qs, company)
        return farmer_registry_csv(qs, company)


class FarmerImportTemplateView(StaffRequiredMixin, View):
    """Download the blank CSV template for bulk farmer import."""
    def get(self, request):
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="AgriOps_Farmer_Import_Template.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'first_name', 'last_name', 'gender', 'phone', 'village', 'lga', 'nin', 'crops',
            'consent_date',
        ])
        writer.writerow([
            'Amina', 'Musa', 'F', '08012345678', 'Shendam', 'Shendam',
            '12345678901', 'Soybeans, Groundnut', '2026-04-01',
        ])
        return response


class FarmerImportErrorsView(StaffRequiredMixin, View):
    """Download error rows from a previous import (stored in session)."""
    def get(self, request):
        import csv
        from django.http import HttpResponse
        session_key = 'farmer_import_errors'
        error_rows = request.session.get(session_key, [])
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="AgriOps_Farmer_Import_Errors.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'first_name', 'last_name', 'gender', 'phone', 'village', 'lga', 'nin', 'crops',
            'consent_date', 'error_reason',
        ])
        for row in error_rows:
            writer.writerow([
                row.get('first_name', ''),
                row.get('last_name', ''),
                row.get('gender', ''),
                row.get('phone', ''),
                row.get('village', ''),
                row.get('lga', ''),
                row.get('nin', ''),
                row.get('crops', ''),
                row.get('consent_date', ''),
                row.get('error_reason', ''),
            ])
        return response


class FarmerImportView(StaffRequiredMixin, View):
    template_name = 'suppliers/farmers/import.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        import csv
        import io
        import datetime
        from django.db import transaction
        from .models import Farmer

        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            return render(request, self.template_name, {'form_error': 'Please select a CSV file.'})
        if not csv_file.name.endswith('.csv'):
            return render(request, self.template_name, {'form_error': 'File must be a .csv file.'})

        company = request.user.company
        created_count   = 0
        duplicate_count = 0
        error_rows      = []
        error_detail    = []

        try:
            decoded = csv_file.read().decode('utf-8-sig')
            reader  = csv.DictReader(io.StringIO(decoded))
        except Exception as e:
            return render(request, self.template_name, {'form_error': f'Could not read file: {e}'})

        to_create = []
        row_num   = 1  # header is row 0

        for row in reader:
            row_num += 1
            # Accept both AgriOps template column names and SW Maps export column names
            first_name  = (row.get('first_name')   or row.get('First Name')    or '').strip()
            last_name   = (row.get('last_name')    or row.get('Last Name')     or '').strip()
            gender      = (row.get('gender')       or row.get('Gender')        or '').strip().upper()
            phone       = (row.get('phone')        or row.get('Phone Number')  or '').strip()
            village     = (row.get('village')      or row.get('Village')       or '').strip()
            lga         = (row.get('lga')          or row.get('LGA')           or '').strip()
            nin         = (row.get('nin')          or row.get('NIN')           or '').strip()
            crops       = (row.get('crops')        or row.get('Commodity')     or '').strip()
            consent_raw = (row.get('consent_date') or '').strip()

            if not first_name:
                error_rows.append({**row, 'error_reason': 'first_name is required'})
                error_detail.append({'row': row_num, 'first_name': first_name, 'last_name': last_name, 'reason': 'first_name is required'})
                continue

            # Validate gender
            if gender and gender not in ('M', 'F', 'O'):
                gender = ''

            # Parse consent date
            consent_date = None
            if consent_raw:
                for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
                    try:
                        consent_date = datetime.date.fromisoformat(consent_raw) if fmt == '%Y-%m-%d' else datetime.datetime.strptime(consent_raw, fmt).date()
                        break
                    except ValueError:
                        continue

            # NIN uniqueness check
            if nin:
                if Farmer.objects.filter(company=company, nin=nin).exists():
                    duplicate_count += 1
                    continue

            # Name + village + LGA duplicate check
            if first_name and village and lga:
                if Farmer.objects.filter(
                    company=company,
                    first_name__iexact=first_name,
                    last_name__iexact=last_name,
                    village__iexact=village,
                    lga__iexact=lga,
                ).exists():
                    duplicate_count += 1
                    continue

            to_create.append(Farmer(
                company=company,
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                phone=phone,
                village=village,
                lga=lga,
                nin=nin,
                crops=crops,
                consent_given=bool(consent_date or consent_raw),
                consent_date=consent_date,
            ))

        # Bulk create in batches of 100
        batch_size = 100
        with transaction.atomic():
            for i in range(0, len(to_create), batch_size):
                Farmer.objects.bulk_create(to_create[i:i + batch_size])
                created_count += len(to_create[i:i + batch_size])

        # Store error rows in session for download
        session_key = 'farmer_import_errors'
        request.session[session_key] = error_rows

        result = {
            'created':      created_count,
            'duplicates':   duplicate_count,
            'errors':       len(error_rows),
            'session_key':  session_key,
            'error_detail': error_detail,
        }

        if created_count:
            from apps.audit.models import AuditLog
            from apps.audit.mixins import get_client_ip
            AuditLog.objects.create(
                company=request.user.company,
                user=request.user,
                action='import',
                model_name='Farmer',
                object_repr=f'{created_count} farmer{"s" if created_count != 1 else ""} — {csv_file.name}'[:255],
                changes={
                    'created':    created_count,
                    'duplicates': duplicate_count,
                    'errors':     len(error_rows),
                    'file':       csv_file.name,
                },
                ip_address=get_client_ip(request),
            )

        return render(request, self.template_name, {'result': result})


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


def run_farm_geojson_import(company, supplier, features, default_commodity='', dry_run=False):
    """
    Core GeoJSON import pipeline — called by both the web view and the API endpoint.
    Runs all validation layers and bulk-creates passing farms (unless dry_run=True).
    Returns a result dict: {total, created, duplicates, blocked, errors, error_detail,
                            blocked_detail, warnings, dry_run}
    """
    from django import forms as django_forms
    from django.db import transaction
    from .models import Farm, Farmer
    from .forms import _validate_geojson_polygon, _find_overlapping_farm, normalize_field_gps_geometry
    from .ng_geodata import canonicalise_lga_state, normalise_commodity

    # Accept a FeatureCollection dict as well as a plain list
    if isinstance(features, dict) and features.get('type') == 'FeatureCollection':
        features = features.get('features') or []

    to_create      = []
    duplicates     = []
    blocked        = []
    errors         = []
    warnings       = []
    auto_corrected = 0
    farmer_cache   = {}  # (first_name_lower, last_name_lower, village_lower, lga_lower) -> Farmer

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
        commodity    = normalise_commodity(
            _s(props.get('commodity')) or default_commodity or 'Unknown'
        )

        # Track geometry auto-correction (3D→2D, dedup, close ring, simplify, buffer(0) repair)
        raw_geometry = geometry
        if geometry:
            geometry = normalize_field_gps_geometry(geometry)

        # LGA canonicalization: fuzzy-matched if the resolved value differs from raw input
        lga_was_corrected = bool(lga_raw) and lga.strip().lower() != lga_raw.strip().lower()
        geom_was_corrected = bool(raw_geometry) and geometry != raw_geometry
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

        # Completeness warnings — non-blocking but flagged for the operator
        row_warnings = []
        if not farmer_label:
            row_warnings.append("No farmer name found — check 'First Name' and 'Last Name' columns.")
        if not lga:
            row_warnings.append("LGA missing — add an 'LGA' column or fill it in after import.")
        if commodity == 'Unknown':
            row_warnings.append("Commodity not in file — set a Default Commodity above, or add a 'Commodity' column.")
        if area and area > 200:
            row_warnings.append(f"Declared area ({area} ha) is unusually large — verify this is correct.")
        if row_warnings:
            warnings.append({'row': row, 'name': name, 'issues': row_warnings})

        linked_farmer = None
        if first_name:
            cache_key = (first_name.lower(), last_name.lower(), village.lower(), lga.lower())
            if cache_key in farmer_cache:
                linked_farmer = farmer_cache[cache_key]
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
                if linked_farmer is None and not dry_run:
                    linked_farmer = Farmer.objects.create(
                        company=company,
                        first_name=first_name,
                        last_name=last_name,
                        phone=phone_raw,
                        village=village,
                        lga=lga,
                    )
                farmer_cache[cache_key] = linked_farmer

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
        'dry_run':         dry_run,
    }


class FarmImportView(StaffRequiredMixin, View):
    template_name = 'suppliers/farms/import.html'

    def _get_context(self, request):
        from .models import FarmImportLog
        return {
            'suppliers': Supplier.objects.filter(
                company=request.user.company, is_active=True
            ),
            'recent_imports': FarmImportLog.objects.filter(
                company=request.user.company
            ).select_related('uploaded_by', 'supplier')[:5],
        }

    def get(self, request):
        return render(request, self.template_name, self._get_context(request))

    @staticmethod
    def _parse_file_to_features(geojson_file):
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

    def post(self, request):
        company           = request.user.company
        default_commodity = request.POST.get('default_commodity', '').strip()
        dry_run           = 'dry_run' in request.POST
        ctx               = self._get_context(request)

        # ── Commit from session (dry-run → one-tap commit) ───────────────────
        if request.POST.get('use_session'):
            pending = request.session.get('farm_import_pending')
            if not pending:
                ctx['form_error'] = 'Session expired — please upload the file again.'
                return render(request, self.template_name, ctx)
            features          = pending['features']
            supplier_id       = pending['supplier_id']
            default_commodity = pending['default_commodity']
            filename          = pending.get('filename', 'session')
            dry_run           = False

        # ── Normal file upload ────────────────────────────────────────────────
        else:
            supplier_id = request.POST.get('supplier')
            if not supplier_id:
                ctx['form_error'] = 'Please select a supplier.'
                return render(request, self.template_name, ctx)

            files = request.FILES.getlist('geojson_file')
            if not files:
                ctx['form_error'] = 'Please select a file.'
                return render(request, self.template_name, ctx)

            features, filenames = [], []
            for f in files:
                file_features, err = self._parse_file_to_features(f)
                if err:
                    ctx['form_error'] = err
                    return render(request, self.template_name, ctx)
                features.extend(file_features)
                filenames.append(f.name)
            filename = ', '.join(filenames)[:255]

            if not features:
                ctx['form_error'] = 'File contains no features — check the export settings in your mapping app.'
                return render(request, self.template_name, ctx)

        supplier = Supplier.objects.filter(pk=supplier_id, company=company).first()
        if not supplier:
            ctx['form_error'] = 'Invalid supplier.'
            return render(request, self.template_name, ctx)

        result = run_farm_geojson_import(company, supplier, features, default_commodity, dry_run=dry_run)

        # After dry run stash features so the operator can commit without re-uploading
        if dry_run:
            request.session['farm_import_pending'] = {
                'features':          features,
                'supplier_id':       str(supplier_id),
                'default_commodity': default_commodity,
                'filename':          filename,
            }
        else:
            request.session.pop('farm_import_pending', None)

        from .models import FarmImportLog
        FarmImportLog.objects.create(
            company=company,
            uploaded_by=request.user,
            supplier=supplier,
            filename=filename,
            dry_run=dry_run,
            total=result['total'],
            created=result['created'],
            would_create=result['would_create'],
            duplicates=result['duplicates'],
            blocked=result['blocked'],
            errors=result['errors'],
            auto_corrected=result['auto_corrected'],
            warning_count=len(result['warnings']),
            error_detail=result['error_detail'],
            blocked_detail=result['blocked_detail'],
            warning_detail=result['warnings'],
        )

        session_key = 'farm_import_problems'
        request.session[session_key] = result['error_detail'] + result['blocked_detail']
        result['session_key'] = session_key

        if not dry_run and result['created']:
            from apps.audit.models import AuditLog
            from apps.audit.mixins import get_client_ip
            created = result['created']
            AuditLog.objects.create(
                company=company,
                user=request.user,
                action='import',
                model_name='Farm',
                object_repr=f'{created} farm{"s" if created != 1 else ""} — {filename}'[:255],
                changes={
                    'created':    created,
                    'duplicates': result['duplicates'],
                    'blocked':    result['blocked'],
                    'errors':     result['errors'],
                    'supplier':   supplier.name,
                    'file':       filename,
                },
                ip_address=get_client_ip(request),
            )

        result['supplier_id'] = supplier.pk

        # Incomplete farmer nudge — farmers linked to created farms missing phone/NIN/village
        if not dry_run and result['created']:
            created_farms = Farm.objects.filter(
                company=company, supplier=supplier,
                name__in=result['created_names']
            ).select_related('farmer')
            seen_pks = set()
            incomplete = []
            for farm in created_farms:
                if farm.farmer and farm.farmer.pk not in seen_pks:
                    seen_pks.add(farm.farmer.pk)
                    missing = farm.farmer.missing_fields
                    if missing:
                        incomplete.append({
                            'pk':        farm.farmer.pk,
                            'full_name': farm.farmer.full_name,
                            'missing':   missing,
                        })
            result['incomplete_farmers'] = incomplete

        ctx['result'] = result
        return render(request, self.template_name, ctx)


class FarmImportHistoryView(StaffRequiredMixin, View):
    template_name = 'suppliers/farms/import_history.html'

    def get(self, request):
        from .models import FarmImportLog
        logs = FarmImportLog.objects.filter(
            company=request.user.company
        ).select_related('uploaded_by', 'supplier')
        return render(request, self.template_name, {'logs': logs})


class FarmImportErrorsView(StaffRequiredMixin, View):
    """Download problem rows from a previous farm import as JSON."""
    def get(self, request):
        import json
        from django.http import HttpResponse
        session_key  = 'farm_import_problems'
        problem_rows = request.session.get(session_key, [])
        response = HttpResponse(
            json.dumps(problem_rows, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="AgriOps_Farm_Import_Problems.json"'
        return response


class FarmExportView(StaffRequiredMixin, View):
    def get(self, request):
        from .exports import farm_registry_csv, farm_registry_pdf, farm_registry_geojson
        fmt     = request.GET.get('format', 'csv')
        company = request.user.company
        base_qs = Farm.objects.filter(company=company)
        # Strip 'format' from params so it doesn't leak into filter logic
        filter_params = request.GET.copy()
        filter_params.pop('format', None)
        qs, _ = _farm_filter_qs(base_qs, filter_params)
        if fmt == 'pdf':
            return farm_registry_pdf(qs, company)
        if fmt == 'geojson':
            return farm_registry_geojson(qs, company)
        return farm_registry_csv(qs, company)


class FarmerDeleteView(AuditDeleteMixin, ManagerRequiredMixin, DeleteView):
    model = Farmer
    success_url = reverse_lazy('suppliers:farmer_list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


# ─────────────────────────────────────
# SUPPLIER VIEWS
# ─────────────────────────────────────

class SupplierListView(StaffRequiredMixin, ListView):
    model = Supplier
    template_name = 'suppliers/list.html'
    context_object_name = 'suppliers'
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)


class SupplierDetailView(StaffRequiredMixin, DetailView):
    model = Supplier
    template_name = 'suppliers/detail.html'
    context_object_name = 'supplier'

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['farms'] = self.object.farms.filter(
            company=self.request.user.company
        ).order_by('name')
        return context


class SupplierCreateView(OtherRevealMixin, AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = Supplier
    template_name = 'suppliers/form.html'
    fields = ['name', 'category', 'contact_person', 'phone', 'email',
              'country', 'city', 'address', 'is_active']
    other_reveal_fields = ['category']
    success_url = reverse_lazy('suppliers:list')

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)


class SupplierUpdateView(OtherRevealMixin, AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = Supplier
    template_name = 'suppliers/form.html'
    fields = ['name', 'category', 'contact_person', 'phone', 'email',
              'country', 'city', 'address', 'is_active']
    other_reveal_fields = ['category']
    success_url = reverse_lazy('suppliers:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class SupplierDeleteView(AuditDeleteMixin, ManagerRequiredMixin, DeleteView):
    model = Supplier
    template_name = 'suppliers/confirm_delete.html'
    success_url = reverse_lazy('suppliers:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


# ─────────────────────────────────────
# FARM VIEWS
# ─────────────────────────────────────

def _farm_filter_qs(base_qs, params):
    """Apply URL params to a Farm queryset. Returns (filtered_qs, active_filters_dict)."""
    filters     = {}
    supplier_id = params.get('supplier', '').strip()
    state       = params.get('state', '').strip()
    commodity   = params.get('commodity', '').strip()
    risk        = params.get('risk', '').strip()
    if supplier_id:
        base_qs = base_qs.filter(supplier_id=supplier_id)
        filters['supplier'] = supplier_id
    if state:
        base_qs = base_qs.filter(state_region__icontains=state)
        filters['state'] = state
    if commodity:
        base_qs = base_qs.filter(commodity__icontains=commodity)
        filters['commodity'] = commodity
    if risk and risk in ('low', 'standard', 'high'):
        base_qs = base_qs.filter(deforestation_risk_status=risk)
        filters['risk'] = risk
    return base_qs, filters


class FarmListView(StaffRequiredMixin, ListView):
    model = Farm
    template_name = 'suppliers/farms/list.html'
    context_object_name = 'farms'
    paginate_by = 50

    def get_queryset(self):
        qs = Farm.objects.filter(company=self.request.user.company).select_related('supplier', 'farmer')
        qs, _ = _farm_filter_qs(qs, self.request.GET)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        _, ctx['active_filters'] = _farm_filter_qs(Farm.objects.none(), self.request.GET)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['filter_qs'] = params.urlencode()
        ctx['suppliers'] = Supplier.objects.filter(
            company=self.request.user.company, is_active=True
        ).order_by('name')
        return ctx


class FarmDetailView(StaffRequiredMixin, DetailView):
    model = Farm
    template_name = 'suppliers/farms/detail.html'
    context_object_name = 'farm'

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['documents'] = self.object.documents.filter(is_current=True)
        context['certifications'] = self.object.certifications.all()
        return context


class FarmCreateView(DatePickerMixin, AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = Farm
    template_name = 'suppliers/farms/form.html'
    form_class = FarmForm
    success_url = reverse_lazy('suppliers:farm_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.request.user.company
        return kwargs

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)


class FarmUpdateView(DatePickerMixin, AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = Farm
    template_name = 'suppliers/farms/form.html'
    form_class = FarmUpdateForm
    success_url = reverse_lazy('suppliers:farm_list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.request.user.company
        return kwargs


class FarmDeleteView(AuditDeleteMixin, ManagerRequiredMixin, DeleteView):
    model = Farm
    template_name = 'suppliers/farms/confirm_delete.html'
    success_url = reverse_lazy('suppliers:farm_list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


# ─────────────────────────────────────
# FARM CERTIFICATION VIEWS
# ─────────────────────────────────────

class FarmCertificationCreateView(OtherRevealMixin, DatePickerMixin, AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = FarmCertification
    template_name = 'suppliers/farms/certification_form.html'
    fields = ['cert_type', 'certifying_body', 'certificate_number', 'issued_date', 'expiry_date', 'notes']
    other_reveal_fields = ['cert_type']

    def get_farm(self):
        farm = get_object_or_404(Farm, pk=self.kwargs['farm_pk'], company=self.request.user.company)
        return farm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['farm'] = self.get_farm()
        return context

    def form_valid(self, form):
        farm = self.get_farm()
        form.instance.farm = farm
        form.instance.company = self.request.user.company
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('suppliers:farm_detail', kwargs={'pk': self.kwargs['farm_pk']})


class FarmCertificationDeleteView(AuditDeleteMixin, ManagerRequiredMixin, DeleteView):
    model = FarmCertification

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_success_url(self):
        return reverse_lazy('suppliers:farm_detail', kwargs={'pk': self.object.farm_id})

