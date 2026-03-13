from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Inventory
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin


class InventoryListView(StaffRequiredMixin, ListView):
    model = Inventory
    template_name = 'inventory/list.html'
    context_object_name = 'inventory_items'

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)


class InventoryDetailView(StaffRequiredMixin, DetailView):
    model = Inventory
    template_name = 'inventory/detail.html'
    context_object_name = 'item'

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class InventoryCreateView(AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = Inventory
    template_name = 'inventory/form.html'
    fields = ['product', 'quantity', 'warehouse_location', 'low_stock_threshold']
    success_url = reverse_lazy('inventory:list')

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)


class InventoryUpdateView(AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = Inventory
    template_name = 'inventory/form.html'
    fields = ['product', 'quantity', 'warehouse_location', 'low_stock_threshold']
    success_url = reverse_lazy('inventory:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class InventoryDeleteView(AuditDeleteMixin, ManagerRequiredMixin, DeleteView):
    model = Inventory
    template_name = 'inventory/confirm_delete.html'
    success_url = reverse_lazy('inventory:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj
