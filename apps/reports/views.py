from django.http import HttpResponse, Http404
from django.views import View
from django.utils import timezone
from apps.users.permissions import StaffRequiredMixin
from .pdf import generate_compliance_report


class ReportsIndexView(StaffRequiredMixin, View):
    def get(self, request):
        company = request.user.company
        if not company:
            raise Http404

        # ── Parse filter parameters ───────────────────────────
        order_number = request.GET.get('order', '').strip()
        date_from    = request.GET.get('from', '').strip()
        date_to      = request.GET.get('to', '').strip()

        filters = {}

        if order_number:
            from apps.sales_orders.models import SalesOrder
            try:
                so = SalesOrder.objects.get(
                    order_number=order_number,
                    company=company
                )
                filters['sales_order'] = so
                filters['label'] = f"Order_{order_number}"
            except SalesOrder.DoesNotExist:
                raise Http404(f"Sales order {order_number} not found.")

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

        # ── Generate PDF ──────────────────────────────────────
        buffer = generate_compliance_report(company, request.user, filters=filters)

        # ── Build filename ────────────────────────────────────
        label = filters.get('label', 'Full')
        if date_from or date_to:
            label = f"{date_from or 'start'}_to_{date_to or 'today'}"

        filename = (
            f"AgriOps_Compliance_Report_"
            f"{company.name.replace(' ', '_')}_"
            f"{label}_"
            f"{timezone.now().strftime('%Y%m%d')}.pdf"
        )

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
