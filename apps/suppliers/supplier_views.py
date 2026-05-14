from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q
from .models import Supplier
from apps.users.permissions import (
    StaffRequiredMixin, ManagerRequiredMixin, OtherRevealMixin,
    CompanyOwnedMixin, CompanySetMixin,
)
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin


class SupplierListView(StaffRequiredMixin, ListView):
    model = Supplier
    template_name = 'suppliers/list.html'
    context_object_name = 'suppliers'
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().filter(company=self.request.user.company)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(contact_person__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['filter_qs'] = params.urlencode()
        return ctx


class SupplierDetailView(CompanyOwnedMixin, StaffRequiredMixin, DetailView):
    model = Supplier
    template_name = 'suppliers/detail.html'
    context_object_name = 'supplier'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['farms'] = self.object.farms.filter(
            company=self.request.user.company
        ).order_by('name')
        return context


class SupplierCreateView(OtherRevealMixin, AuditCreateMixin, CompanySetMixin, StaffRequiredMixin, CreateView):
    model = Supplier
    template_name = 'suppliers/form.html'
    fields = ['name', 'category', 'contact_person', 'phone', 'email',
              'country', 'city', 'address', 'is_active']
    other_reveal_fields = ['category']

    def get_success_url(self):
        return reverse_lazy('suppliers:detail', kwargs={'pk': self.object.pk})


class SupplierUpdateView(OtherRevealMixin, AuditUpdateMixin, CompanyOwnedMixin, StaffRequiredMixin, UpdateView):
    model = Supplier
    template_name = 'suppliers/form.html'
    fields = ['name', 'category', 'contact_person', 'phone', 'email',
              'country', 'city', 'address', 'is_active']
    other_reveal_fields = ['category']

    def get_success_url(self):
        next_url = (self.request.POST.get('next') or self.request.GET.get('next', '')).strip()
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return reverse_lazy('suppliers:detail', kwargs={'pk': self.object.pk})


class SupplierDeleteView(AuditDeleteMixin, CompanyOwnedMixin, ManagerRequiredMixin, DeleteView):
    model = Supplier
    success_url = reverse_lazy('suppliers:list')

    def get(self, request, *args, **kwargs):
        return redirect(self.success_url)
