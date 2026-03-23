from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from .models import Supplier, Farm, FarmCertification
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin, DatePickerMixin, OtherRevealMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin


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
    fields = ['supplier', 'name', 'farmer_name', 'country', 'state_region',
              'commodity', 'area_hectares', 'harvest_year',
              'deforestation_risk_status', 'deforestation_reference_date', 'land_cleared_after_cutoff',
              'mapping_date', 'mapped_by', 'geolocation']
    success_url = reverse_lazy('suppliers:farm_list')

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Scope supplier dropdown to current company only
        form.fields['supplier'].queryset = Supplier.objects.filter(
            company=self.request.user.company
        )
        # Scope mapped_by to current company only
        from apps.users.models import CustomUser
        form.fields['mapped_by'].queryset = CustomUser.objects.filter(
            company=self.request.user.company
        )
        return form


class FarmUpdateView(DatePickerMixin, AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = Farm
    template_name = 'suppliers/farms/form.html'
    fields = ['supplier', 'name', 'farmer_name', 'country', 'state_region',
              'commodity', 'area_hectares', 'harvest_year',
              'deforestation_risk_status', 'deforestation_reference_date', 'land_cleared_after_cutoff',
              'mapping_date', 'mapped_by', 'geolocation',
              'is_eudr_verified', 'verified_by', 'verified_date', 'verification_expiry']
    success_url = reverse_lazy('suppliers:farm_list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['supplier'].queryset = Supplier.objects.filter(
            company=self.request.user.company
        )
        from apps.users.models import CustomUser
        form.fields['mapped_by'].queryset = CustomUser.objects.filter(
            company=self.request.user.company
        )
        form.fields['verified_by'].queryset = CustomUser.objects.filter(
            company=self.request.user.company
        )
        return form


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


class FarmCertificationDeleteView(ManagerRequiredMixin, DeleteView):
    model = FarmCertification

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_success_url(self):
        return reverse_lazy('suppliers:farm_detail', kwargs={'pk': self.object.farm_id})

