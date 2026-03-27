from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from .models import SalesOrder
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin, log_action


class SalesOrderListView(StaffRequiredMixin, ListView):
    model = SalesOrder
    template_name = 'sales_orders/list.html'
    context_object_name = 'orders'
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company).select_related('company')


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.select_related('product')
        context['linked_batch'] = self.object.batches.first()
        from apps.suppliers.models import Farm
        context['available_farms'] = Farm.objects.filter(
            company=self.request.user.company
        ).select_related('supplier').order_by('name')
        return context


class SalesOrderCreateView(AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = SalesOrder
    template_name = 'sales_orders/form.html'
    fields = ['order_number', 'customer_name', 'customer_email',
              'customer_phone', 'status', 'nxp_reference', 'certificate_of_origin_ref', 'is_eu_export', 'notes']
    success_url = reverse_lazy('sales_orders:list')

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)


class SalesOrderUpdateView(AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = SalesOrder
    template_name = 'sales_orders/form.html'
    fields = ['order_number', 'customer_name', 'customer_email',
              'customer_phone', 'status', 'nxp_reference', 'certificate_of_origin_ref', 'is_eu_export', 'notes']
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


class SalesOrderLinkFarmsView(StaffRequiredMixin, View):
    """
    Links farms to a sales order for EUDR traceability.
    Creates or updates the Batch transparently — the user just selects farms.
    """
    def post(self, request, pk):
        from apps.suppliers.models import Farm
        from apps.sales_orders.batch import Batch

        order = get_object_or_404(SalesOrder, pk=pk, company=request.user.company)
        farm_pks = request.POST.getlist('farm_pks')

        items = order.items.select_related('product')
        first_item = items.first()
        commodity = first_item.product.name if first_item else 'Unknown'
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
