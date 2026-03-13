from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import PurchaseOrder
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin


class PurchaseOrderListView(StaffRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'purchase_orders/list.html'
    context_object_name = 'orders'

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)


class PurchaseOrderDetailView(StaffRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'purchase_orders/detail.html'
    context_object_name = 'order'

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class PurchaseOrderCreateView(AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = PurchaseOrder
    template_name = 'purchase_orders/form.html'
    fields = ['supplier', 'order_number', 'status', 'expected_delivery', 'notes']
    success_url = reverse_lazy('purchase_orders:list')

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)


class PurchaseOrderUpdateView(AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = PurchaseOrder
    template_name = 'purchase_orders/form.html'
    fields = ['supplier', 'order_number', 'status', 'expected_delivery', 'notes']
    success_url = reverse_lazy('purchase_orders:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class PurchaseOrderDeleteView(AuditDeleteMixin, ManagerRequiredMixin, DeleteView):
    model = PurchaseOrder
    template_name = 'purchase_orders/confirm_delete.html'
    success_url = reverse_lazy('purchase_orders:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj
