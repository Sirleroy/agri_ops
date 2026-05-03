from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from decimal import Decimal, InvalidOperation
from .models import SalesOrder, SalesOrderItem
from apps.products.models import Product
from apps.users.permissions import (
    StaffRequiredMixin, ManagerRequiredMixin,
    CompanyOwnedMixin, CompanySetMixin,
)
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin, log_action


class SalesOrderListView(StaffRequiredMixin, ListView):
    model = SalesOrder
    template_name = 'sales_orders/list.html'
    context_object_name = 'orders'
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company).select_related('company')


class SalesOrderDetailView(CompanyOwnedMixin, StaffRequiredMixin, DetailView):
    model = SalesOrder
    template_name = 'sales_orders/detail.html'
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        items = list(self.object.items.select_related('product', 'product__supplier'))
        context['items'] = items
        context['order_total'] = sum(item.total_price for item in items)
        context['linked_batch'] = self.object.batches.first()
        context['products'] = Product.objects.filter(
            company=self.request.user.company, is_active=True
        ).order_by('name')
        from apps.suppliers.models import Farm
        # Narrow farm list to suppliers that appear in this order's line items.
        # Falls back to all company farms if no products have a linked supplier.
        supplier_pks = {item.product.supplier_id for item in items if item.product.supplier_id}
        all_farms = Farm.objects.filter(
            company=self.request.user.company,
        ).select_related('supplier').order_by('name')
        if supplier_pks:
            context['matched_farms'] = [f for f in all_farms if f.supplier_id in supplier_pks]
            context['direct_farms']  = [f for f in all_farms if not f.supplier_id]
            context['farm_filter_suppliers'] = sorted(
                {item.product.supplier.name for item in items if item.product.supplier}
            )
        else:
            context['matched_farms'] = []
            context['direct_farms']  = list(all_farms)
            context['farm_filter_suppliers'] = []
        # keep available_farms for the all-farms fallback used by batch form
        context['available_farms'] = all_farms
        return context


class SalesOrderCreateView(AuditCreateMixin, CompanySetMixin, StaffRequiredMixin, CreateView):
    model = SalesOrder
    template_name = 'sales_orders/form.html'
    fields = ['customer_name', 'customer_email', 'customer_phone', 'is_eu_export', 'nxp_reference', 'notes']

    def form_valid(self, form):
        company = self.request.user.company
        year = timezone.now().year
        count = SalesOrder.objects.filter(company=company).count()
        form.instance.order_number = f"{year}-{count + 1:04d}"
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('sales_orders:detail', kwargs={'pk': self.object.pk})


class SalesOrderUpdateView(AuditUpdateMixin, CompanyOwnedMixin, StaffRequiredMixin, UpdateView):
    model = SalesOrder
    template_name = 'sales_orders/form.html'
    fields = ['order_number', 'customer_name', 'customer_email', 'customer_phone',
              'status', 'nxp_reference', 'certificate_of_origin_ref', 'is_eu_export', 'notes']

    def get_success_url(self):
        next_url = self.request.GET.get('next', '').strip()
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return reverse_lazy('sales_orders:detail', kwargs={'pk': self.object.pk})


class SalesOrderDeleteView(AuditDeleteMixin, CompanyOwnedMixin, ManagerRequiredMixin, DeleteView):
    model = SalesOrder
    template_name = 'sales_orders/confirm_delete.html'
    success_url = reverse_lazy('sales_orders:list')


class SalesOrderItemCreateView(StaffRequiredMixin, View):
    """Add a line item to an open sales order."""
    def post(self, request, pk):
        order = get_object_or_404(SalesOrder, pk=pk, company=request.user.company)
        if order.status in ('completed', 'cancelled'):
            return redirect('sales_orders:detail', pk=pk)

        product_id = request.POST.get('product')
        try:
            quantity = Decimal(request.POST.get('quantity', ''))
            unit_price = Decimal(request.POST.get('unit_price', ''))
            if quantity <= 0 or unit_price < 0:
                raise InvalidOperation
        except InvalidOperation:
            return redirect('sales_orders:detail', pk=pk)

        product = get_object_or_404(Product, pk=product_id, company=request.user.company)
        SalesOrderItem.objects.create(
            sales_order=order,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
        )
        log_action(request, 'update', order, changes={'item_added': str(product)})
        return redirect('sales_orders:detail', pk=pk)


class SalesOrderItemDeleteView(ManagerRequiredMixin, View):
    """Remove a line item from an open sales order."""
    def post(self, request, item_pk):
        item = get_object_or_404(
            SalesOrderItem, pk=item_pk,
            sales_order__company=request.user.company
        )
        order = item.sales_order
        if order.status in ('completed', 'cancelled'):
            return redirect('sales_orders:detail', pk=order.pk)

        log_action(request, 'update', order, changes={'item_removed': str(item.product)})
        item.delete()
        return redirect('sales_orders:detail', pk=order.pk)


class SalesOrderLinkFarmsView(StaffRequiredMixin, View):
    """
    Links farms to a sales order for EUDR traceability.
    Creates or updates the Batch transparently — the user just selects farms.
    Requires at least one line item so commodity is known.
    """
    def post(self, request, pk):
        from apps.suppliers.models import Farm
        from apps.sales_orders.batch import Batch

        order = get_object_or_404(SalesOrder, pk=pk, company=request.user.company)
        farm_pks = request.POST.getlist('farm_pks')

        items = list(order.items.select_related('product'))
        if not items:
            return redirect('sales_orders:detail', pk=pk)

        first_item = items[0]
        commodity = first_item.product.name
        quantity_kg = sum(item.quantity for item in items)

        batch = order.batches.first()
        if not batch:
            batch = Batch(
                company=request.user.company,
                sales_order=order,
                commodity=commodity,
                quantity_kg=quantity_kg,
            )
            batch.save()
            log_action(request, 'create', batch)
        else:
            batch.commodity = commodity
            batch.quantity_kg = quantity_kg
            batch.save(update_fields=['commodity', 'quantity_kg', 'updated_at'])

        farms = Farm.objects.filter(pk__in=farm_pks, company=request.user.company)
        batch.farms.set(farms)
        log_action(request, 'update', batch, changes={'farms': f"linked {farms.count()} farm(s)"})

        return redirect('sales_orders:detail', pk=pk)
