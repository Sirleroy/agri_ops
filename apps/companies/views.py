from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Company
from apps.users.permissions import OrgAdminRequiredMixin, StaffRequiredMixin, DatePickerMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin


class CompanyListView(StaffRequiredMixin, ListView):
    model = Company
    template_name = 'companies/list.html'
    context_object_name = 'companies'

    def get_queryset(self):
        return Company.objects.filter(id=self.request.user.company_id)


class CompanyDetailView(StaffRequiredMixin, DetailView):
    model = Company
    template_name = 'companies/detail.html'
    context_object_name = 'company'

    def get_object(self):
        obj = super().get_object()
        if obj.id != self.request.user.company_id:
            from django.http import Http404
            raise Http404
        return obj


class CompanyCreateView(DatePickerMixin, AuditCreateMixin, OrgAdminRequiredMixin, CreateView):
    model = Company
    template_name = 'companies/form.html'
    fields = ['name', 'country', 'city', 'address', 'phone', 'email',
              'nepc_registration_number', 'nepc_registration_expiry']
    success_url = reverse_lazy('companies:list')


class CompanyUpdateView(DatePickerMixin, AuditUpdateMixin, OrgAdminRequiredMixin, UpdateView):
    model = Company
    template_name = 'companies/form.html'
    fields = ['name', 'country', 'city', 'address', 'phone', 'email',
              'nepc_registration_number', 'nepc_registration_expiry']
    success_url = reverse_lazy('companies:list')

    def get_object(self):
        obj = super().get_object()
        if obj.id != self.request.user.company_id:
            from django.http import Http404
            raise Http404
        return obj


class CompanyDeleteView(AuditDeleteMixin, OrgAdminRequiredMixin, DeleteView):
    model = Company
    template_name = 'companies/confirm_delete.html'
    success_url = reverse_lazy('companies:list')

    def get_object(self):
        obj = super().get_object()
        if obj.id != self.request.user.company_id:
            from django.http import Http404
            raise Http404
        return obj
