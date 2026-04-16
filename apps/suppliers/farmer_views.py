from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import render
from .models import Farmer
from .forms import FarmerForm
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin, DatePickerMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin


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


class FarmerDeleteView(AuditDeleteMixin, ManagerRequiredMixin, DeleteView):
    model = Farmer
    success_url = reverse_lazy('suppliers:farmer_list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj
