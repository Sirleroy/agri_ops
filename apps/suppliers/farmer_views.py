from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from .models import Farmer
from .forms import FarmerForm
from apps.users.permissions import (
    StaffRequiredMixin, ManagerRequiredMixin, DatePickerMixin,
    CompanyOwnedMixin, CompanySetMixin, TenantFormFieldsMixin,
)
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
        from django.db.models import Count
        qs = Farmer.objects.filter(company=self.request.user.company).annotate(
            farm_count=Count('farms')
        )
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


class FarmerDetailView(CompanyOwnedMixin, StaffRequiredMixin, DetailView):
    model = Farmer
    template_name = 'suppliers/farmers/detail.html'
    context_object_name = 'farmer'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['farms'] = self.object.farms.filter(
            company=self.request.user.company
        ).select_related('supplier').order_by('name')
        return context


class FarmerCreateView(DatePickerMixin, AuditCreateMixin, TenantFormFieldsMixin, CompanySetMixin, StaffRequiredMixin, CreateView):
    model = Farmer
    template_name = 'suppliers/farmers/form.html'
    form_class = FarmerForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.request.user.company
        return kwargs

    def get_success_url(self):
        return reverse_lazy('suppliers:farmer_detail', kwargs={'pk': self.object.pk})


class FarmerUpdateView(DatePickerMixin, AuditUpdateMixin, TenantFormFieldsMixin, CompanyOwnedMixin, StaffRequiredMixin, UpdateView):
    model = Farmer
    template_name = 'suppliers/farmers/form.html'
    form_class = FarmerForm

    def get_success_url(self):
        next_url = (self.request.POST.get('next') or self.request.GET.get('next', '')).strip()
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return reverse_lazy('suppliers:farmer_detail', kwargs={'pk': self.object.pk})

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
    """Download rejected rows from a previous import, sourced from FarmerImportLog."""
    def get(self, request, pk):
        import csv
        from django.http import HttpResponse
        from django.shortcuts import get_object_or_404
        from .models import FarmerImportLog
        log = get_object_or_404(
            FarmerImportLog, pk=pk, company=request.user.company
        )
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="AgriOps_Farmer_Import_Errors.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'row', 'first_name', 'last_name', 'gender', 'phone', 'village',
            'lga', 'nin', 'crops', 'consent_date', 'error_reason',
        ])
        for row in log.error_detail:
            writer.writerow([
                row.get('row', ''),
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
        from .farmer_import import run_farmer_import, MAX_FARMER_IMPORT_BYTES

        import_file = request.FILES.get('import_file')
        if not import_file:
            return render(request, self.template_name, {'form_error': 'Please select a file to upload.'})
        if import_file.size > MAX_FARMER_IMPORT_BYTES:
            mb = MAX_FARMER_IMPORT_BYTES // (1024 * 1024)
            return render(request, self.template_name, {
                'form_error': f'File is larger than {mb} MB. Split it into smaller batches and upload each separately.',
            })

        try:
            result = run_farmer_import(
                company=request.user.company,
                file_bytes=import_file.read(),
                filename=import_file.name,
                content_type=import_file.content_type,
                uploaded_by=request.user,
            )
        except ValueError as e:
            return render(request, self.template_name, {'form_error': str(e)})
        except UnicodeDecodeError:
            return render(request, self.template_name, {
                'form_error': 'Could not decode the file as text. Re-save it as UTF-8 CSV and try again.',
            })
        except Exception as e:  # noqa — last-resort safety net so the view never 500s on a bad file
            return render(request, self.template_name, {'form_error': f'Could not read file: {e}'})

        if result['created']:
            from apps.audit.models import AuditLog
            from apps.audit.mixins import get_client_ip
            AuditLog.objects.create(
                company=request.user.company,
                user=request.user,
                action='import',
                model_name='Farmer',
                object_repr=f'{result["created"]} farmer{"s" if result["created"] != 1 else ""} — {import_file.name}'[:255],
                changes={
                    'created':        result['created'],
                    'auto_corrected': result['auto_corrected'],
                    'duplicates':     result['duplicates'],
                    'errors':         result['errors'],
                    'warnings':       result['warning_count'],
                    'file':           import_file.name,
                },
                ip_address=get_client_ip(request),
            )

        return render(request, self.template_name, {'result': result})


class FarmerDeleteView(AuditDeleteMixin, CompanyOwnedMixin, ManagerRequiredMixin, DeleteView):
    model = Farmer
    success_url = reverse_lazy('suppliers:farmer_list')
