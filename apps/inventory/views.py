from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Inventory


class InventoryListView(LoginRequiredMixin, ListView):
    model = Inventory
    template_name = 'inventory/list.html'
    context_object_name = 'inventory_items'
    paginate_by = 20


class InventoryDetailView(LoginRequiredMixin, DetailView):
    model = Inventory
    template_name = 'inventory/detail.html'
    context_object_name = 'item'


class InventoryCreateView(LoginRequiredMixin, CreateView):
    model = Inventory
    template_name = 'inventory/form.html'
    fields = ['company', 'product', 'quantity', 'warehouse_location', 'low_stock_threshold']
    success_url = reverse_lazy('inventory:list')


class InventoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Inventory
    template_name = 'inventory/form.html'
    fields = ['company', 'product', 'quantity', 'warehouse_location', 'low_stock_threshold']
    success_url = reverse_lazy('inventory:list')


class InventoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Inventory
    template_name = 'inventory/confirm_delete.html'
    success_url = reverse_lazy('inventory:list')
