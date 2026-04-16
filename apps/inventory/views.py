from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from decimal import Decimal, InvalidOperation
from .models import Inventory
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin, log_action


class InventoryListView(StaffRequiredMixin, ListView):
    model = Inventory
    template_name = 'inventory/list.html'
    context_object_name = 'inventory_items'
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company).select_related('product', 'company')


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
    fields = ['product', 'quantity', 'warehouse_location', 'low_stock_threshold',
              'moisture_content', 'quality_grade', 'harvest_date', 'origin_state']

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('inventory:detail', kwargs={'pk': self.object.pk})


class InventoryUpdateView(AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = Inventory
    template_name = 'inventory/form.html'
    fields = ['product', 'quantity', 'warehouse_location', 'low_stock_threshold',
              'lot_number', 'moisture_content', 'quality_grade', 'harvest_date', 'origin_state']

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
        return reverse_lazy('inventory:detail', kwargs={'pk': self.object.pk})


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


class InventoryAdjustView(StaffRequiredMixin, View):
    """Quick stock adjustment — add or subtract quantity with an optional note."""
    def post(self, request, pk):
        item = get_object_or_404(Inventory, pk=pk, company=request.user.company)
        direction = request.POST.get('direction')
        try:
            amount = Decimal(request.POST.get('amount', ''))
            if amount <= 0:
                raise InvalidOperation
        except InvalidOperation:
            return redirect('inventory:detail', pk=pk)

        old_qty = item.quantity
        if direction == 'add':
            item.quantity += amount
        elif direction == 'subtract':
            item.quantity = max(Decimal('0'), item.quantity - amount)
        else:
            return redirect('inventory:detail', pk=pk)

        item.save(update_fields=['quantity', 'last_updated'])
        note = request.POST.get('note', '')[:255]
        log_action(request, 'update', item, changes={
            'quantity': {'from': str(old_qty), 'to': str(item.quantity)},
            'adjustment': f"{'+'if direction == 'add' else '-'}{amount}",
            **(({'note': note}) if note else {}),
        })
        return redirect('inventory:detail', pk=pk)
