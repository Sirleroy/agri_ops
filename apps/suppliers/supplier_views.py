from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
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
        return super().get_queryset().filter(company=self.request.user.company)


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
    template_name = 'suppliers/confirm_delete.html'
    success_url = reverse_lazy('suppliers:list')
