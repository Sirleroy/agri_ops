import csv
from django.http import HttpResponse, Http404
from django.views import View
from django.views.generic import TemplateView
from django.utils import timezone
from apps.users.permissions import StaffRequiredMixin
from .pdf import generate_compliance_report


class ReportsLandingView(StaffRequiredMixin, TemplateView):
    template_name = 'reports/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.request.user.company
        if not company:
            return context

        from apps.sales_orders.models import SalesOrder
        context['customers'] = (
            SalesOrder.objects
            .filter(company=company)
            .values_list('customer_name', flat=True)
            .distinct()
            .order_by('customer_name')
        )
        context['active_tab'] = self.request.GET.get('tab', 'eudr')
        return context


class EUDRReportView(StaffRequiredMixin, View):
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

        if date_from:
            try:
                from datetime import date
                filters['date_from'] = date.fromisoformat(date_from)
            except ValueError:
                pass

        if date_to:
            try:
                from datetime import date
                filters['date_to'] = date.fromisoformat(date_to)
            except ValueError:
                pass

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

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


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

        return handler(request, company, date_from, date_to)

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
                farm.supplier.name,
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
