from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from .models import PurchaseOrder, PurchaseOrderItem
from apps.products.models import Product
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
        items = list(self.object.items.select_related('product'))
        context['items'] = items
        context['order_total'] = sum(item.total_price for item in items)
        context['products'] = Product.objects.filter(
            company=self.request.user.company, is_active=True
        ).order_by('name')
        # For received POs: attach _inventory_pk to each item so the template
        # can link directly to the inventory record that holds its stock.
        # mark_received always uses warehouse_location='' so there is at most
        # one matching record per product.
        if self.object.status == 'received':
            from apps.inventory.models import Inventory
            product_ids = [item.product_id for item in items]
            inv_map = {
                inv.product_id: inv.pk
                for inv in Inventory.objects.filter(
                    company=self.request.user.company,
                    product_id__in=product_ids,
                    warehouse_location='',
                ).only('pk', 'product_id')
            }
            for item in items:
                item.inventory_pk = inv_map.get(item.product_id)
        return context


class PurchaseOrderCreateView(DatePickerMixin, AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = PurchaseOrder
    template_name = 'purchase_orders/form.html'
    fields = ['supplier', 'expected_delivery', 'notes']
    success_url = reverse_lazy('purchase_orders:list')

    def get_success_url(self):
        return reverse_lazy('purchase_orders:detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        company = self.request.user.company
        year = timezone.now().year
        count = PurchaseOrder.objects.filter(company=company).count()
        form.instance.order_number = f"{year}-{count + 1:04d}"
        form.instance.company = company
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

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy('purchase_orders:detail', kwargs={'pk': self.object.pk})


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
            old_qty = inv.quantity
            inv.quantity += item.quantity
            inv.save(update_fields=['quantity', 'last_updated'])
            log_action(request, 'update', inv, changes={
                'quantity': {'from': str(old_qty), 'to': str(inv.quantity)},
                'source': f'PO-{order.order_number}',
            })

        return redirect('purchase_orders:detail', pk=pk)


class PurchaseOrderItemCreateView(StaffRequiredMixin, View):
    """Add a line item to an open PO."""
    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk, company=request.user.company)

        if order.status in ('received', 'cancelled'):
            return redirect('purchase_orders:detail', pk=pk)

        product_id = request.POST.get('product')
        try:
            quantity = Decimal(request.POST.get('quantity', ''))
            unit_price = Decimal(request.POST.get('unit_price', ''))
            if quantity <= 0 or unit_price < 0:
                raise InvalidOperation
        except InvalidOperation:
            return redirect('purchase_orders:detail', pk=pk)

        product = get_object_or_404(Product, pk=product_id, company=request.user.company)
        PurchaseOrderItem.objects.create(
            purchase_order=order,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
        )
        log_action(request, 'update', order, changes={'item_added': str(product)})
        return redirect('purchase_orders:detail', pk=pk)


class PurchaseOrderItemDeleteView(ManagerRequiredMixin, View):
    """Remove a line item from an open PO."""
    def post(self, request, item_pk):
        item = get_object_or_404(
            PurchaseOrderItem, pk=item_pk,
            purchase_order__company=request.user.company
        )
        order = item.purchase_order
        if order.status in ('received', 'cancelled'):
            return redirect('purchase_orders:detail', pk=order.pk)

        log_action(request, 'update', order, changes={'item_removed': str(item.product)})
        item.delete()
        return redirect('purchase_orders:detail', pk=order.pk)
