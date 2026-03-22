from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import SalesOrder
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin


class SalesOrderListView(StaffRequiredMixin, ListView):
    model = SalesOrder
    template_name = 'sales_orders/list.html'
    context_object_name = 'orders'

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)


class SalesOrderDetailView(StaffRequiredMixin, DetailView):
    model = SalesOrder
    template_name = 'sales_orders/detail.html'
    context_object_name = 'order'

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class SalesOrderCreateView(AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = SalesOrder
    template_name = 'sales_orders/form.html'
    fields = ['order_number', 'customer_name', 'customer_email',
              'customer_phone', 'status', 'nxp_reference', 'certificate_of_origin_ref', 'notes']
    success_url = reverse_lazy('sales_orders:list')

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)


class SalesOrderUpdateView(AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = SalesOrder
    template_name = 'sales_orders/form.html'
    fields = ['order_number', 'customer_name', 'customer_email',
              'customer_phone', 'status', 'nxp_reference', 'certificate_of_origin_ref', 'notes']
    success_url = reverse_lazy('sales_orders:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class SalesOrderDeleteView(AuditDeleteMixin, ManagerRequiredMixin, DeleteView):
    model = SalesOrder
    template_name = 'sales_orders/confirm_delete.html'
    success_url = reverse_lazy('sales_orders:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj
