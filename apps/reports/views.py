import csv
from datetime import timedelta
from django.contrib import messages
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
from django.utils import timezone
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin
from apps.audit.models import AuditLog
from apps.audit.mixins import get_client_ip
from .pdf import generate_compliance_report


class ReportsLandingView(StaffRequiredMixin, TemplateView):
    template_name = 'reports/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.request.user.company
        if not company:
            return context

        tab = self.request.GET.get('tab', 'eudr')
        context['active_tab'] = tab if tab in ('eudr', 'ops') else 'eudr'

        from apps.sales_orders.models import SalesOrder
        context['customers'] = (
            SalesOrder.objects
            .filter(company=company)
            .values_list('customer_name', flat=True)
            .distinct()
            .order_by('customer_name')
        )
        context['sales_orders'] = (
            SalesOrder.objects
            .filter(company=company)
            .order_by('-order_date')
            .values('order_number', 'customer_name', 'order_date')
        )

        self._add_financial_summary(context, company)
        return context

    def _add_financial_summary(self, context, company):
        from apps.purchase_orders.models import PurchaseOrderItem
        from apps.sales_orders.models import SalesOrderItem
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField

        today = timezone.now().date()
        period = self.request.GET.get('period', 'this_month')

        if period == 'last_month':
            last_day = today.replace(day=1) - timedelta(days=1)
            first_day = last_day.replace(day=1)
            period_label = last_day.strftime('%b %Y')
        elif period == 'this_quarter':
            q_start_month = ((today.month - 1) // 3) * 3 + 1
            first_day = today.replace(month=q_start_month, day=1)
            last_day = today
            period_label = f"Q{(today.month - 1) // 3 + 1} {today.year}"
        else:  # this_month
            period = 'this_month'
            first_day = today.replace(day=1)
            last_day = today
            period_label = today.strftime('%b %Y')

        line_total = ExpressionWrapper(
            F('quantity') * F('unit_price'),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )

        procurement = (
            PurchaseOrderItem.objects
            .filter(
                purchase_order__company=company,
                purchase_order__status='received',
                purchase_order__order_date__gte=first_day,
                purchase_order__order_date__lte=last_day,
            )
            .aggregate(total=Sum(line_total))['total'] or 0
        )

        revenue = (
            SalesOrderItem.objects
            .filter(
                sales_order__company=company,
                sales_order__status='completed',
                sales_order__order_date__gte=first_day,
                sales_order__order_date__lte=last_day,
            )
            .aggregate(total=Sum(line_total))['total'] or 0
        )

        margin = revenue - procurement
        margin_pct = round(float(margin) / float(revenue) * 100) if revenue else 0

        open_po = (
            PurchaseOrderItem.objects
            .filter(purchase_order__company=company)
            .exclude(purchase_order__status__in=['received', 'cancelled'])
            .aggregate(total=Sum(line_total))['total'] or 0
        )

        def fmt(n):
            n = float(n)
            sign = '-' if n < 0 else ''
            n = abs(n)
            if n >= 1_000_000:
                return f'{sign}₦{n / 1_000_000:.1f}M'
            if n >= 1_000:
                return f'{sign}₦{n / 1_000:.0f}K'
            return f'{sign}₦{n:.0f}'

        context.update({
            'summary_period': period,
            'summary_period_label': period_label,
            'summary_procurement': fmt(procurement),
            'summary_revenue': fmt(revenue),
            'summary_margin': fmt(margin),
            'summary_margin_pct': margin_pct,
            'summary_margin_positive': margin >= 0,
            'summary_open_po': fmt(open_po),
        })


class EUDRReportView(ManagerRequiredMixin, View):
    def get(self, request):
        company = request.user.company
        if not company:
            raise Http404

        customer_name = request.GET.get('customer', '').strip()
        order_number  = request.GET.get('order', '').strip()
        date_from     = request.GET.get('from', '').strip()
        date_to       = request.GET.get('to', '').strip()

        filters = {}

        if order_number:
            from apps.sales_orders.models import SalesOrder
            try:
                so = SalesOrder.objects.get(order_number=order_number, company=company)
                filters['sales_order'] = so
                filters['label'] = f"Order_{order_number}"
            except SalesOrder.DoesNotExist:
                raise Http404(f"Sales order {order_number} not found.")

        if customer_name:
            filters['customer_name'] = customer_name
            if 'label' not in filters:
                filters['label'] = f"Customer_{customer_name.replace(' ', '_')}"

        date_error = False
        if date_from:
            try:
                from datetime import date
                filters['date_from'] = date.fromisoformat(date_from)
            except ValueError:
                date_error = True
        if date_to:
            try:
                from datetime import date
                filters['date_to'] = date.fromisoformat(date_to)
            except ValueError:
                date_error = True

        if date_error:
            messages.error(request, 'Invalid date — use YYYY-MM-DD format (or use the date picker).')
            return HttpResponseRedirect(reverse('reports:landing') + '?tab=eudr')

        buffer = generate_compliance_report(company, request.user, filters=filters)

        label = filters.get('label', 'Full')
        if label == 'Full' and (date_from or date_to):
            label = f"{date_from or 'start'}_to_{date_to or 'today'}"

        filename = (
            f"AgriOps_EUDR_Report_"
            f"{company.name.replace(' ', '_')}_"
            f"{label}_"
            f"{timezone.now().strftime('%Y%m%d')}.pdf"
        )

        AuditLog.objects.create(
            company=company,
            user=request.user,
            action='download',
            model_name='EUDRReport',
            object_repr=filename[:255],
            changes={
                'label': label,
                'customer': customer_name or None,
                'order': order_number or None,
                'date_from': date_from or None,
                'date_to': date_to or None,
            },
            ip_address=get_client_ip(request),
        )

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class CorridorComplianceView(StaffRequiredMixin, TemplateView):
    template_name = 'reports/corridor.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.request.user.company
        if not company:
            return context

        from apps.suppliers.models import Farm
        from django.db.models import Count, Q, Sum

        corridors = list(
            Farm.objects
            .filter(company=company)
            .values('state_region', 'commodity')
            .annotate(
                total=Count('id'),
                low_risk=Count('id', filter=Q(deforestation_risk_status='low')),
                pending=Count('id', filter=Q(deforestation_risk_status='standard')),
                high_risk=Count('id', filter=Q(deforestation_risk_status='high')),
                eudr_verified=Count('id', filter=Q(is_eudr_verified=True)),
                total_area=Sum('area_hectares'),
            )
            .order_by('state_region', 'commodity')
        )

        for c in corridors:
            c['verified_pct'] = round(c['eudr_verified'] / c['total'] * 100) if c['total'] else 0
            c['label'] = f"{c['state_region'] or 'Unknown Region'} · {c['commodity'].title() if c['commodity'] else 'Unknown'}"

        total_farms = sum(c['total'] for c in corridors)
        total_area  = sum(c['total_area'] or 0 for c in corridors)

        context['corridors']    = corridors
        context['total_farms']  = total_farms
        context['total_area']   = round(total_area, 1)
        context['corridor_count'] = len(corridors)
        return context


class OpsReportView(StaffRequiredMixin, View):

    REPORT_TYPES = {
        'suppliers':       'Supplier Performance',
        'sales':           'Sales Summary',
        'inventory':       'Inventory Stock',
        'purchase-orders': 'Purchase Order Status',
        'farms':           'Farm Registry',
    }

    def get(self, request):
        company = request.user.company
        if not company:
            raise Http404

        report_type = request.GET.get('type', '')
        date_from   = request.GET.get('from', '').strip()
        date_to     = request.GET.get('to', '').strip()

        handlers = {
            'suppliers':       self._suppliers_report,
            'sales':           self._sales_report,
            'inventory':       self._inventory_report,
            'purchase-orders': self._po_report,
            'farms':           self._farms_report,
        }

        handler = handlers.get(report_type)
        if not handler:
            raise Http404("Unknown report type.")

        response = handler(request, company, date_from, date_to)

        AuditLog.objects.create(
            company=company,
            user=request.user,
            action='download',
            model_name='OpsReport',
            object_repr=self.REPORT_TYPES.get(report_type, report_type),
            changes={
                'type': report_type,
                'date_from': date_from or None,
                'date_to': date_to or None,
            },
            ip_address=get_client_ip(request),
        )

        return response

    # ── Helpers ───────────────────────────────────────────────

    def _csv_response(self, filename):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def _parse_dates(self, date_from, date_to):
        from datetime import date
        df = dt = None
        try:
            if date_from:
                df = date.fromisoformat(date_from)
        except ValueError:
            pass
        try:
            if date_to:
                dt = date.fromisoformat(date_to)
        except ValueError:
            pass
        return df, dt

    # ── Report handlers ───────────────────────────────────────

    def _suppliers_report(self, request, company, date_from, date_to):
        from apps.suppliers.models import Supplier
        from apps.purchase_orders.models import PurchaseOrder
        from django.db.models import Count

        suppliers = Supplier.objects.filter(company=company, is_active=True)
        po_qs = PurchaseOrder.objects.filter(company=company)
        df, dt = self._parse_dates(date_from, date_to)
        if df:
            po_qs = po_qs.filter(order_date__gte=df)
        if dt:
            po_qs = po_qs.filter(order_date__lte=dt)

        po_counts = {
            row['supplier_id']: row['count']
            for row in po_qs.values('supplier_id').annotate(count=Count('id'))
        }
        received_counts = {
            row['supplier_id']: row['count']
            for row in po_qs.filter(status='received').values('supplier_id').annotate(count=Count('id'))
        }

        filename = f"AgriOps_Supplier_Performance_{timezone.now().strftime('%Y%m%d')}.csv"
        response = self._csv_response(filename)
        writer = csv.writer(response)
        writer.writerow([
            'Supplier', 'Category', 'Country', 'City',
            'Reliability Score', 'Total POs', 'Received POs', 'Delivery Rate %'
        ])
        for s in suppliers:
            total    = po_counts.get(s.pk, 0)
            received = received_counts.get(s.pk, 0)
            rate     = f"{round(received / total * 100)}%" if total else '—'
            writer.writerow([
                s.name, s.get_category_display(), s.country, s.city or '—',
                s.reliability_score or '—', total, received, rate,
            ])
        return response

    def _sales_report(self, request, company, date_from, date_to):
        from apps.sales_orders.models import SalesOrder

        qs = SalesOrder.objects.filter(company=company)
        df, dt = self._parse_dates(date_from, date_to)
        if df:
            qs = qs.filter(order_date__gte=df)
        if dt:
            qs = qs.filter(order_date__lte=dt)

        filename = f"AgriOps_Sales_Summary_{timezone.now().strftime('%Y%m%d')}.csv"
        response = self._csv_response(filename)
        writer = csv.writer(response)
        writer.writerow([
            'Order Number', 'Customer', 'Status', 'Order Date', 'Items', 'Total Value'
        ])
        for so in qs.order_by('-order_date'):
            items       = so.items.all()
            total_value = sum(i.quantity * i.unit_price for i in items)
            writer.writerow([
                so.order_number, so.customer_name, so.get_status_display(),
                so.order_date, items.count(), f"{total_value:.2f}",
            ])
        return response

    def _inventory_report(self, request, company, date_from, date_to):
        from apps.inventory.models import Inventory

        qs = Inventory.objects.filter(company=company).select_related('product')

        filename = f"AgriOps_Inventory_{timezone.now().strftime('%Y%m%d')}.csv"
        response = self._csv_response(filename)
        writer = csv.writer(response)
        writer.writerow([
            'Product', 'Unit', 'Lot Number', 'Quantity', 'Low Stock Threshold',
            'Status', 'Warehouse', 'Quality Grade', 'Origin State', 'Last Updated',
        ])
        for item in qs:
            writer.writerow([
                item.product.name,
                item.product.unit,
                item.lot_number,
                item.quantity,
                item.low_stock_threshold,
                'LOW STOCK' if item.is_low_stock else 'OK',
                item.warehouse_location or '—',
                item.get_quality_grade_display() if item.quality_grade else '—',
                item.origin_state or '—',
                item.last_updated.strftime('%Y-%m-%d %H:%M'),
            ])
        return response

    def _po_report(self, request, company, date_from, date_to):
        from apps.purchase_orders.models import PurchaseOrder

        qs = PurchaseOrder.objects.filter(company=company).select_related('supplier')
        df, dt = self._parse_dates(date_from, date_to)
        if df:
            qs = qs.filter(order_date__gte=df)
        if dt:
            qs = qs.filter(order_date__lte=dt)

        filename = f"AgriOps_PO_Status_{timezone.now().strftime('%Y%m%d')}.csv"
        response = self._csv_response(filename)
        writer = csv.writer(response)
        writer.writerow([
            'Order Number', 'Supplier', 'Status', 'Order Date',
            'Expected Delivery', 'Items', 'Total Value',
        ])
        for po in qs.order_by('-order_date'):
            items       = po.items.all()
            total_value = sum(i.quantity * i.unit_price for i in items)
            writer.writerow([
                po.order_number,
                po.supplier.name if po.supplier else '—',
                po.get_status_display(),
                po.order_date,
                po.expected_delivery or '—',
                items.count(),
                f"{total_value:.2f}",
            ])
        return response

    def _farms_report(self, request, company, date_from, date_to):
        from apps.suppliers.models import Farm

        qs = Farm.objects.filter(company=company).select_related('supplier')

        filename = f"AgriOps_Farm_Registry_{timezone.now().strftime('%Y%m%d')}.csv"
        response = self._csv_response(filename)
        writer = csv.writer(response)
        writer.writerow([
            'Farm Name', 'Supplier', 'Farmer', 'Commodity', 'Country', 'Region',
            'Area (ha)', 'Risk Status', 'EUDR Verified', 'Compliance Status',
            'Verification Expiry', 'GeoJSON Present',
        ])
        for farm in qs:
            writer.writerow([
                farm.name,
                farm.supplier.name if farm.supplier else '—',
                farm.farmer_name or '—',
                farm.commodity,
                farm.country,
                farm.state_region or '—',
                farm.area_hectares or '—',
                farm.get_deforestation_risk_status_display(),
                'YES' if farm.is_eudr_verified else 'NO',
                farm.compliance_status.upper(),
                farm.verification_expiry or '—',
                'YES' if farm.geolocation else 'NO',
            ])
        return response
