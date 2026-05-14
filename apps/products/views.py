from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from .models import Product
from apps.users.permissions import (
    StaffRequiredMixin, ManagerRequiredMixin, OtherRevealMixin,
    CompanyOwnedMixin, CompanySetMixin,
)
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin


class ProductListView(StaffRequiredMixin, ListView):
    model = Product
    template_name = 'products/list.html'
    context_object_name = 'products'
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().filter(company=self.request.user.company).select_related('supplier')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['filter_qs'] = params.urlencode()
        return ctx


class ProductDetailView(CompanyOwnedMixin, StaffRequiredMixin, DetailView):
    model = Product
    template_name = 'products/detail.html'
    context_object_name = 'product'


class ProductCreateView(OtherRevealMixin, AuditCreateMixin, CompanySetMixin, StaffRequiredMixin, CreateView):
    model = Product
    template_name = 'products/form.html'
    fields = ['name', 'description', 'category', 'unit', 'unit_price', 'hs_code',
              'nafdac_registration_number', 'eu_novel_food_status', 'eu_novel_food_ref',
              'supplier', 'is_active']
    other_reveal_fields = ['category']

    def get_success_url(self):
        return reverse_lazy('products:detail', kwargs={'pk': self.object.pk})


class ProductUpdateView(OtherRevealMixin, AuditUpdateMixin, CompanyOwnedMixin, StaffRequiredMixin, UpdateView):
    model = Product
    template_name = 'products/form.html'
    fields = ['name', 'description', 'category', 'unit', 'unit_price', 'hs_code',
              'nafdac_registration_number', 'eu_novel_food_status', 'eu_novel_food_ref',
              'supplier', 'is_active']
    other_reveal_fields = ['category']

    def get_success_url(self):
        next_url = self.request.GET.get('next', '').strip()
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return reverse_lazy('products:detail', kwargs={'pk': self.object.pk})


class ProductDeleteView(AuditDeleteMixin, CompanyOwnedMixin, ManagerRequiredMixin, DeleteView):
    model = Product
    success_url = reverse_lazy('products:list')

    def get(self, request, *args, **kwargs):
        return redirect(self.success_url)
