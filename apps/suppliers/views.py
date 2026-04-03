from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, render
from .models import Supplier, Farm, FarmCertification, Farmer
from .forms import FarmerForm, FarmForm, FarmUpdateForm
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin, DatePickerMixin, OtherRevealMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin


# ─────────────────────────────────────
# FARMER VIEWS
# ─────────────────────────────────────

class FarmerListView(StaffRequiredMixin, ListView):
    model = Farmer
    template_name = 'suppliers/farmers/list.html'
    context_object_name = 'farmers'
    paginate_by = 50

    def get_queryset(self):
        return Farmer.objects.filter(company=self.request.user.company)


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
        fmt = request.GET.get('format', 'csv')
        company = request.user.company
        if fmt == 'pdf':
            return farmer_registry_pdf(company)
        return farmer_registry_csv(company)


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
        session_key = request.GET.get('session_key', 'farmer_import_errors')
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
            first_name = (row.get('first_name') or '').strip()
            last_name  = (row.get('last_name') or '').strip()
            gender     = (row.get('gender') or '').strip().upper()
            phone      = (row.get('phone') or '').strip()
            village    = (row.get('village') or '').strip()
            lga        = (row.get('lga') or '').strip()
            nin        = (row.get('nin') or '').strip()
            crops      = (row.get('crops') or '').strip()
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
        return render(request, self.template_name, {'result': result})


def run_farm_geojson_import(company, supplier, features, default_commodity=''):
    """
    Core GeoJSON import pipeline — called by both the web view and the API endpoint.
    Runs all 4 validation layers and bulk-creates passing farms.
    Returns a result dict: {total, created, duplicates, blocked, errors, error_detail, blocked_detail}
    """
    import json
    from django import forms as django_forms
    from django.db import transaction
    from shapely.geometry import mapping
    from .models import Farm, Farmer
    from .forms import _validate_geojson_polygon, _find_overlapping_farm, _geojson_to_shape, strip_z_coordinates

    to_create  = []
    duplicates = []
    blocked    = []
    errors     = []

    for i, feature in enumerate(features):
        row = i + 1
        raw_props = feature.get('properties') or {}
        props     = {k.strip(): v for k, v in raw_props.items()}
        geometry  = feature.get('geometry')

        name = (
            props.get('NAME') or props.get('name') or
            props.get('farm_name') or props.get('Farm Name') or
            f"Farm {row}"
        ).strip()

        first_name   = (props.get('First Name') or props.get('first_name') or '').strip()
        last_name    = (props.get('Last Name')  or props.get('last_name')  or '').strip()
        farmer_label = f"{first_name} {last_name}".strip()
        village      = (props.get('Village') or props.get('village') or '').strip()
        lga          = (props.get('LGA')     or props.get('lga')     or '').strip()
        phone_raw    = props.get('Phone Number') or props.get('phone') or ''
        phone        = '' if str(phone_raw).strip() in ('', '0', '0.0', 'None') else str(phone_raw).strip()
        commodity    = (props.get('Commodity') or props.get('commodity') or default_commodity or 'Unknown').strip()
        state_region = (props.get('State') or props.get('state_region') or props.get('Region') or '').strip()

        area = None
        try:
            ha_raw = props.get('Area_Hectares') or props.get('area_ha')
            sm_raw = props.get('AREA') or props.get('area')
            if ha_raw and float(ha_raw) > 0:
                area = round(float(ha_raw), 4)
            elif sm_raw and float(sm_raw) > 0:
                area = round(float(sm_raw) / 10000, 4)
        except (ValueError, TypeError):
            pass

        if geometry:
            geometry = strip_z_coordinates(geometry)

        try:
            _validate_geojson_polygon(geometry)
        except django_forms.ValidationError as e:
            errors.append({'row': row, 'name': name, 'reason': e.messages[0]})
            continue

        shape = _geojson_to_shape(geometry)
        if shape is not None and not shape.is_valid:
            repaired = shape.buffer(0)
            if repaired.is_valid and repaired.area > 0:
                geometry = strip_z_coordinates(dict(mapping(repaired)))
            else:
                errors.append({'row': row, 'name': name,
                               'reason': 'Polygon is self-intersecting and could not be repaired automatically.'})
                continue

        if Farm.objects.filter(company=company, supplier=supplier, name__iexact=name).exists():
            duplicates.append({'row': row, 'name': name})
            continue

        overlapping = _find_overlapping_farm(geometry, company)
        if overlapping:
            blocked.append({'row': row, 'name': name,
                            'reason': f"Overlaps with existing farm '{overlapping.name}' ({overlapping.supplier.name})"})
            continue

        linked_farmer = None
        if first_name and village and lga:
            linked_farmer = Farmer.objects.filter(
                company=company,
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                village__iexact=village,
                lga__iexact=lga,
            ).first()

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
    with transaction.atomic():
        for j in range(0, len(to_create), 50):
            batch = to_create[j:j + 50]
            Farm.objects.bulk_create(batch)
            created_count += len(batch)

    return {
        'total':          len(features),
        'created':        created_count,
        'duplicates':     len(duplicates),
        'blocked':        len(blocked),
        'errors':         len(errors),
        'error_detail':   errors,
        'blocked_detail': blocked,
    }


class FarmImportView(StaffRequiredMixin, View):
    template_name = 'suppliers/farms/import.html'

    def _get_context(self, request):
        return {
            'suppliers': Supplier.objects.filter(
                company=request.user.company, is_active=True
            )
        }

    def get(self, request):
        return render(request, self.template_name, self._get_context(request))

    def post(self, request):
        import json
        company     = request.user.company
        supplier_id = request.POST.get('supplier')
        default_commodity = request.POST.get('default_commodity', '').strip()
        ctx = self._get_context(request)

        if not supplier_id:
            ctx['form_error'] = 'Please select a supplier.'
            return render(request, self.template_name, ctx)

        supplier = Supplier.objects.filter(pk=supplier_id, company=company).first()
        if not supplier:
            ctx['form_error'] = 'Invalid supplier.'
            return render(request, self.template_name, ctx)

        geojson_file = request.FILES.get('geojson_file')
        if not geojson_file:
            ctx['form_error'] = 'Please select a GeoJSON file.'
            return render(request, self.template_name, ctx)

        try:
            data = json.loads(geojson_file.read().decode('utf-8'))
        except Exception as e:
            ctx['form_error'] = f'Could not read file: {e}'
            return render(request, self.template_name, ctx)

        if data.get('type') != 'FeatureCollection':
            ctx['form_error'] = 'File must be a GeoJSON FeatureCollection.'
            return render(request, self.template_name, ctx)

        features = data.get('features') or []
        if not features:
            ctx['form_error'] = 'FeatureCollection contains no features.'
            return render(request, self.template_name, ctx)

        result = run_farm_geojson_import(company, supplier, features, default_commodity)

        session_key = 'farm_import_problems'
        request.session[session_key] = result['error_detail'] + result['blocked_detail']
        result['session_key'] = session_key

        ctx['result'] = result
        return render(request, self.template_name, ctx)


class FarmImportErrorsView(StaffRequiredMixin, View):
    """Download problem rows from a previous farm import as JSON."""
    def get(self, request):
        import json
        from django.http import HttpResponse
        session_key  = request.GET.get('session_key', 'farm_import_problems')
        problem_rows = request.session.get(session_key, [])
        response = HttpResponse(
            json.dumps(problem_rows, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="AgriOps_Farm_Import_Problems.json"'
        return response


class FarmExportView(StaffRequiredMixin, View):
    def get(self, request):
        from .exports import farm_registry_csv, farm_registry_pdf
        fmt = request.GET.get('format', 'csv')
        company = request.user.company
        if fmt == 'pdf':
            return farm_registry_pdf(company)
        return farm_registry_csv(company)


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

class FarmListView(StaffRequiredMixin, ListView):
    model = Farm
    template_name = 'suppliers/farms/list.html'
    context_object_name = 'farms'
    paginate_by = 50

    def get_queryset(self):
        return Farm.objects.filter(company=self.request.user.company).select_related('supplier')


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

