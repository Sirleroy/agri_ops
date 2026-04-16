from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Product
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin, OtherRevealMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin


class ProductListView(StaffRequiredMixin, ListView):
    model = Product
    template_name = 'products/list.html'
    context_object_name = 'products'
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company).select_related('supplier')


class ProductDetailView(StaffRequiredMixin, DetailView):
    model = Product
    template_name = 'products/detail.html'
    context_object_name = 'product'

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class ProductCreateView(OtherRevealMixin, AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = Product
    template_name = 'products/form.html'
    fields = ['name', 'description', 'category', 'unit', 'unit_price', 'hs_code',
              'nafdac_registration_number', 'eu_novel_food_status', 'eu_novel_food_ref',
              'supplier', 'is_active']
    other_reveal_fields = ['category']

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('products:detail', kwargs={'pk': self.object.pk})


class ProductUpdateView(OtherRevealMixin, AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = Product
    template_name = 'products/form.html'
    fields = ['name', 'description', 'category', 'unit', 'unit_price', 'hs_code',
              'nafdac_registration_number', 'eu_novel_food_status', 'eu_novel_food_ref',
              'supplier', 'is_active']
    other_reveal_fields = ['category']

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy('products:detail', kwargs={'pk': self.object.pk})


class ProductDeleteView(AuditDeleteMixin, ManagerRequiredMixin, DeleteView):
    model = Product
    template_name = 'products/confirm_delete.html'
    success_url = reverse_lazy('products:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj
