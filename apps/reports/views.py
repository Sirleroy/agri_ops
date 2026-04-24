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


class CorridorExportView(StaffRequiredMixin, View):

    def get(self, request):
        company = request.user.company
        if not company:
            raise Http404

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

        fmt = request.GET.get('format', 'csv')
        if fmt == 'pdf':
            return self._pdf(company, corridors)
        return self._csv(company, corridors)

    def _csv(self, company, corridors):
        filename = f"AgriOps_Corridor_Summary_{company.name.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d')}.csv"
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow(['AgriOps — Corridor Compliance Summary'])
        writer.writerow([f'Company: {company.name}'])
        writer.writerow([f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M UTC")}'])
        writer.writerow([])
        writer.writerow(['Corridor', 'Total Farms', 'Low Risk', 'Pending Check', 'High Risk', 'EUDR Verified', 'Verified %', 'Area (ha)'])
        for c in corridors:
            label = f"{c['state_region'] or 'Unknown'} · {c['commodity'].title() if c['commodity'] else 'Unknown'}"
            writer.writerow([
                label,
                c['total'],
                c['low_risk'],
                c['pending'],
                c['high_risk'],
                c['eudr_verified'],
                f"{c['verified_pct']}%",
                f"{c['total_area']:.1f}" if c['total_area'] else '—',
            ])
        writer.writerow([])
        writer.writerow(['Note: Pending Check = farms not yet processed by the deforestation intersection engine.'])
        return response

    def _pdf(self, company, corridors):
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import ParagraphStyle

        GREEN      = colors.HexColor('#16a34a')
        INK        = colors.HexColor('#0f172a')
        MUTED      = colors.HexColor('#64748b')
        DARK_HDR   = colors.HexColor('#131f2e')
        HDR_BG     = colors.HexColor('#f1f5f9')
        ROW_ALT    = colors.HexColor('#f8fafc')
        RULE       = colors.HexColor('#e2e8f0')

        buf = BytesIO()
        # A4 portrait: 210mm wide, 20mm margins each side → 170mm usable
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=20*mm, rightMargin=20*mm,
                                topMargin=18*mm, bottomMargin=18*mm)

        brand    = ParagraphStyle('brand',   fontName='Helvetica-Bold', fontSize=10, textColor=GREEN,   spaceAfter=2,  leading=14)
        heading  = ParagraphStyle('heading', fontName='Helvetica-Bold', fontSize=16, textColor=INK,     spaceAfter=3,  leading=20)
        subhead  = ParagraphStyle('sub',     fontName='Helvetica',      fontSize=9,  textColor=MUTED,   spaceAfter=0,  leading=12)
        footnote = ParagraphStyle('fn',      fontName='Helvetica',      fontSize=7,  textColor=MUTED,   spaceBefore=6, leading=10)

        total_farms    = sum(c['total'] for c in corridors)
        total_verified = sum(c['eudr_verified'] for c in corridors)
        platform_pct   = round(total_verified / total_farms * 100) if total_farms else 0
        total_area     = sum(c['total_area'] or 0 for c in corridors)

        story = [
            Paragraph('AGRIOPS', brand),
            Paragraph('Corridor Compliance Summary', heading),
            Paragraph(f"{company.name}  ·  Generated {timezone.now().strftime('%d %b %Y')}", subhead),
            Spacer(1, 4*mm),
            HRFlowable(width='100%', thickness=1, color=GREEN, spaceAfter=5*mm),
        ]

        # Summary strip — 170mm / 4 = 42.5mm per cell
        summary_data = [
            ['TOTAL FARMS', 'CORRIDORS', 'EUDR VERIFIED', 'TOTAL AREA'],
            [str(total_farms), str(len(corridors)), f'{platform_pct}%', f'{total_area:.1f} ha'],
        ]
        summary_table = Table(summary_data, colWidths=[42.5*mm] * 4)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), HDR_BG),
            ('TEXTCOLOR',     (0, 0), (-1, 0), MUTED),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica'),
            ('FONTSIZE',      (0, 0), (-1, 0), 7),
            ('TEXTCOLOR',     (0, 1), (-1, 1), GREEN),
            ('FONTNAME',      (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 1), (-1, 1), 18),
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BOX',           (0, 0), (-1, -1), 0.5, RULE),
            ('INNERGRID',     (0, 0), (-1, -1), 0.5, RULE),
        ]))
        story += [summary_table, Spacer(1, 6*mm)]

        # Corridor table — col widths must sum to exactly 170mm
        # Corridor(54) + Total(13) + LowRisk(18) + Pending(16) + HighRisk(18) + Verified(18) + Verified%(17) + Area(16) = 170
        headers = ['Corridor', 'Total', 'Low Risk', 'Pending', 'High Risk', 'Verified', 'Verified %', 'Area (ha)']
        rows = [headers]
        for c in corridors:
            label = f"{c['state_region'] or 'Unknown'} · {c['commodity'].title() if c['commodity'] else 'Unknown'}"
            rows.append([
                label,
                str(c['total']),
                str(c['low_risk']),
                str(c['pending']),
                str(c['high_risk']),
                str(c['eudr_verified']),
                f"{c['verified_pct']}%",
                f"{c['total_area']:.1f}" if c['total_area'] else '—',
            ])

        col_widths = [54*mm, 13*mm, 18*mm, 16*mm, 18*mm, 18*mm, 17*mm, 16*mm]
        corridor_table = Table(rows, colWidths=col_widths, repeatRows=1)

        ts = TableStyle([
            # Dark header — institutional authority
            ('BACKGROUND',    (0, 0), (-1, 0),  DARK_HDR),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
            ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
            # Body rows
            ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
            ('TEXTCOLOR',     (0, 1), (-1, -1), INK),
            ('FONTSIZE',      (0, 0), (-1, -1), 8),
            # Alignment
            ('ALIGN',         (0, 0), (0, -1),  'LEFT'),
            ('ALIGN',         (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            # Breathing room
            ('TOPPADDING',    (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            # Grid — subtle slate lines
            ('BOX',           (0, 0), (-1, -1), 0.5, RULE),
            ('INNERGRID',     (0, 0), (-1, -1), 0.3, RULE),
        ])
        # Zebra stripes on body rows (reliable explicit adds)
        for i in range(1, len(rows)):
            if i % 2 == 0:
                ts.add('BACKGROUND', (0, i), (-1, i), ROW_ALT)
        corridor_table.setStyle(ts)

        story += [corridor_table]

        story.append(Paragraph(
            'Pending Check: farms at default risk status, not yet processed by the deforestation '
            'intersection engine.  ·  Generated by AgriOps — app.agriops.io',
            footnote
        ))

        doc.build(story)
        buf.seek(0)

        filename = f"AgriOps_Corridor_Summary_{company.name.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d')}.pdf"
        response = HttpResponse(buf, content_type='application/pdf')
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
