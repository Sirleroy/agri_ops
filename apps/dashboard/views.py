from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import timedelta


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        company = user.company

        if not company:
            return context

        from apps.suppliers.models import Supplier, Farm
        from apps.products.models import Product
        from apps.inventory.models import Inventory
        from apps.purchase_orders.models import PurchaseOrder
        from apps.sales_orders.models import SalesOrder
        from apps.audit.models import AuditLog
        from apps.users.models import CustomUser
        from django.db.models import F

        # ── Core stats ───────────────────────────────────────
        context['total_suppliers'] = Supplier.objects.filter(company=company).count()
        context['total_products'] = Product.objects.filter(company=company, is_active=True).count()
        context['total_farms'] = Farm.objects.filter(company=company).count()
        context['total_users'] = CustomUser.objects.filter(company=company, is_active=True).count()

        # ── Orders ───────────────────────────────────────────
        context['total_purchase_orders'] = PurchaseOrder.objects.filter(company=company).count()
        context['total_sales_orders'] = SalesOrder.objects.filter(company=company).count()

        # ── EUDR compliance summary ───────────────────────────
        farms = Farm.objects.filter(company=company)
        context['farms_verified'] = farms.filter(is_eudr_verified=True).count()
        context['farms_pending'] = farms.filter(is_eudr_verified=False).count()
        context['farms_high_risk'] = farms.filter(deforestation_risk_status='high').count()

        # Farms with verification expiring in 30 days
        today = timezone.now().date()
        in_30 = today + timedelta(days=30)
        context['farms_expiring_soon'] = farms.filter(
            is_eudr_verified=True,
            verification_expiry__lte=in_30,
            verification_expiry__gte=today
        ).count()

        # ── Low stock alert ───────────────────────────────────
        context['low_stock_count'] = Inventory.objects.filter(
            company=company,
            quantity__lte=F('low_stock_threshold')
        ).count()

        context['low_stock_items'] = Inventory.objects.filter(
            company=company,
            quantity__lte=F('low_stock_threshold')
        ).select_related('product').order_by('quantity')[:5]

        # ── Upcoming PO deliveries (next 7 days) ──────────────
        in_7 = today + timedelta(days=7)
        context['upcoming_pos'] = PurchaseOrder.objects.filter(
            company=company,
            expected_delivery__gte=today,
            expected_delivery__lte=in_7,
        ).exclude(
            status__in=['received', 'cancelled']
        ).select_related('supplier').order_by('expected_delivery')[:5]

        # ── EUDR farms expiring soon (detailed list) ──────────
        context['expiring_farms_list'] = farms.filter(
            is_eudr_verified=True,
            verification_expiry__lte=in_30,
            verification_expiry__gte=today,
        ).select_related('supplier').order_by('verification_expiry')[:5]

        # ── Recent audit activity ─────────────────────────────
        context['recent_activity'] = AuditLog.objects.filter(
            company=company
        ).select_related('user').order_by('-timestamp')[:8]

        return context
