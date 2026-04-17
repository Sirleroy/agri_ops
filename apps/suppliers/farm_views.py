from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, render
from .models import Supplier, Farm, FarmCertification
from .forms import FarmForm, FarmUpdateForm
from .import_pipeline import parse_file_to_features, run_farm_geojson_import  # noqa: F401
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin, DatePickerMixin, OtherRevealMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin


# ─────────────────────────────────────
# SHARED HELPERS
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



# ─────────────────────────────────────
# FARM IMPORT / EXPORT VIEWS
# ─────────────────────────────────────

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
                file_features, err = parse_file_to_features(f)
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
            transformation_log=result['transformations'],
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
        filter_params = request.GET.copy()
        filter_params.pop('format', None)
        qs, _ = _farm_filter_qs(base_qs, filter_params)
        if fmt == 'pdf':
            return farm_registry_pdf(qs, company)
        if fmt == 'geojson':
            return farm_registry_geojson(qs, company)
        return farm_registry_csv(qs, company)


# ─────────────────────────────────────
# FARM CRUD VIEWS
# ─────────────────────────────────────

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
        return get_object_or_404(Farm, pk=self.kwargs['farm_pk'], company=self.request.user.company)

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
