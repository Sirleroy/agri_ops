from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import SalesOrder


class SalesOrderListView(LoginRequiredMixin, ListView):
    model = SalesOrder
    template_name = 'sales_orders/list.html'
    context_object_name = 'orders'
    paginate_by = 20


class SalesOrderDetailView(LoginRequiredMixin, DetailView):
    model = SalesOrder
    template_name = 'sales_orders/detail.html'
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.select_related('product')
        return context


class SalesOrderCreateView(LoginRequiredMixin, CreateView):
    model = SalesOrder
    template_name = 'sales_orders/form.html'
    fields = ['company', 'order_number', 'customer_name', 'customer_email', 'customer_phone', 'status', 'notes']
    success_url = reverse_lazy('sales_orders:list')


class SalesOrderUpdateView(LoginRequiredMixin, UpdateView):
    model = SalesOrder
    template_name = 'sales_orders/form.html'
    fields = ['company', 'order_number', 'customer_name', 'customer_email', 'customer_phone', 'status', 'notes']
    success_url = reverse_lazy('sales_orders:list')


class SalesOrderDeleteView(LoginRequiredMixin, DeleteView):
    model = SalesOrder
    template_name = 'sales_orders/confirm_delete.html'
    success_url = reverse_lazy('sales_orders:list')
