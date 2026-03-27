from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from .models import PurchaseOrder
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin, DatePickerMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin
from apps.audit.mixins import log_action


class PurchaseOrderListView(StaffRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'purchase_orders/list.html'
    context_object_name = 'orders'
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company).select_related('supplier', 'company')


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.select_related('product')
        return context


class PurchaseOrderCreateView(DatePickerMixin, AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = PurchaseOrder
    template_name = 'purchase_orders/form.html'
    fields = ['supplier', 'order_number', 'status', 'expected_delivery', 'notes']
    success_url = reverse_lazy('purchase_orders:list')

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)


class PurchaseOrderUpdateView(DatePickerMixin, AuditUpdateMixin, StaffRequiredMixin, UpdateView):
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


class PurchaseOrderMarkReceivedView(StaffRequiredMixin, View):
    """
    One-click "Mark as Received" — sets status to received and automatically
    adds each line item's quantity into inventory. Idempotent: does nothing
    if the PO is already received.
    """
    def post(self, request, pk):
        from apps.inventory.models import Inventory
        order = get_object_or_404(PurchaseOrder, pk=pk, company=request.user.company)

        if order.status == 'received':
            return redirect('purchase_orders:detail', pk=pk)

        old_status = order.status
        order.status = 'received'
        order.save(update_fields=['status', 'updated_at'])
        log_action(request, 'update', order, changes={'status': {'from': old_status, 'to': 'received'}})

        for item in order.items.select_related('product'):
            inv, _ = Inventory.objects.get_or_create(
                company=request.user.company,
                product=item.product,
                warehouse_location='',
                defaults={'quantity': 0}
            )
            inv.quantity += item.quantity
            inv.save(update_fields=['quantity', 'last_updated'])

        return redirect('purchase_orders:detail', pk=pk)
