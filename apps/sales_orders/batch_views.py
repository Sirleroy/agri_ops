import html
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.core.cache import cache
from apps.users.permissions import StaffRequiredMixin, ManagerRequiredMixin, DatePickerMixin, OtherRevealMixin
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin
from .batch import Batch
from .quality import PhytosanitaryCertificate, BatchQualityTest


class BatchListView(StaffRequiredMixin, ListView):
    model = Batch
    template_name = 'sales_orders/batches/list.html'
    context_object_name = 'batches'
    paginate_by = 50

    def get_queryset(self):
        return Batch.objects.filter(company=self.request.user.company).select_related('sales_order')


class BatchDetailView(StaffRequiredMixin, DetailView):
    model = Batch
    template_name = 'sales_orders/batches/detail.html'
    context_object_name = 'batch'

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['phytosanitary_certs'] = self.object.phytosanitary_certs.all()
        context['quality_tests'] = self.object.quality_tests.all()
        return context


class BatchCreateView(AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = Batch
    template_name = 'sales_orders/batches/form.html'
    fields = ['sales_order', 'commodity', 'quantity_kg', 'farms', 'notes']
    success_url = reverse_lazy('sales_orders:batch_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        from apps.suppliers.models import Farm
        from apps.sales_orders.models import SalesOrder
        company = self.request.user.company
        form.fields['farms'].queryset = Farm.objects.filter(company=company)
        form.fields['sales_order'].queryset = SalesOrder.objects.filter(company=company)
        return form

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)


class BatchUpdateView(AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = Batch
    template_name = 'sales_orders/batches/form.html'
    fields = ['sales_order', 'commodity', 'quantity_kg', 'farms', 'notes']
    success_url = reverse_lazy('sales_orders:batch_list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.is_locked:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("This batch is locked and cannot be edited. Unlock it first (org admin only).")
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        from apps.suppliers.models import Farm
        from apps.sales_orders.models import SalesOrder
        company = self.request.user.company
        form.fields['farms'].queryset = Farm.objects.filter(company=company)
        form.fields['sales_order'].queryset = SalesOrder.objects.filter(company=company)
        return form


# ─────────────────────────────────────
# PHYTOSANITARY CERTIFICATE VIEWS
# ─────────────────────────────────────

class PhytosanitaryCertCreateView(DatePickerMixin, AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = PhytosanitaryCertificate
    template_name = 'sales_orders/batches/phytosanitary_form.html'
    fields = ['certificate_number', 'issuing_office', 'inspector_name',
              'inspection_date', 'issued_date', 'expiry_date', 'notes']

    def get_batch(self):
        return get_object_or_404(Batch, pk=self.kwargs['batch_pk'], company=self.request.user.company)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.get_batch()
        return context

    def form_valid(self, form):
        batch = self.get_batch()
        form.instance.batch = batch
        form.instance.company = self.request.user.company
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.kwargs['batch_pk']})


class PhytosanitaryCertUpdateView(DatePickerMixin, AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = PhytosanitaryCertificate
    template_name = 'sales_orders/batches/phytosanitary_form.html'
    fields = ['certificate_number', 'issuing_office', 'inspector_name',
              'inspection_date', 'issued_date', 'expiry_date', 'notes']

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.object.batch
        return context

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.object.batch_id})


class PhytosanitaryCertDeleteView(ManagerRequiredMixin, DeleteView):
    model = PhytosanitaryCertificate

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.object.batch_id})


# ─────────────────────────────────────
# BATCH QUALITY TEST VIEWS
# ─────────────────────────────────────

class BatchQualityTestCreateView(OtherRevealMixin, DatePickerMixin, AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = BatchQualityTest
    template_name = 'sales_orders/batches/quality_form.html'
    fields = ['test_type', 'lab_name', 'lab_certificate_ref', 'test_date', 'result', 'notes']
    other_reveal_fields = ['test_type']

    def get_batch(self):
        return get_object_or_404(Batch, pk=self.kwargs['batch_pk'], company=self.request.user.company)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.get_batch()
        return context

    def form_valid(self, form):
        batch = self.get_batch()
        form.instance.batch = batch
        form.instance.company = self.request.user.company
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.kwargs['batch_pk']})


class BatchQualityTestUpdateView(OtherRevealMixin, DatePickerMixin, AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = BatchQualityTest
    template_name = 'sales_orders/batches/quality_form.html'
    fields = ['test_type', 'lab_name', 'lab_certificate_ref', 'test_date', 'result', 'notes']
    other_reveal_fields = ['test_type']

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.object.batch
        return context

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.object.batch_id})


class BatchQualityTestDeleteView(ManagerRequiredMixin, DeleteView):
    model = BatchQualityTest

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.object.batch_id})


class BatchToggleLockView(ManagerRequiredMixin, View):
    """
    Lock or unlock a batch.
    Locking: manager or above.
    Unlocking: org_admin only — prevents managers from unlocking submitted DDS batches.
    """
    def post(self, request, pk):
        from django.shortcuts import redirect
        from django.core.exceptions import PermissionDenied
        batch = get_object_or_404(Batch, pk=pk, company=request.user.company)
        if batch.is_locked and not request.user.is_org_admin:
            raise PermissionDenied("Only an organisation admin can unlock a batch.")
        batch.is_locked = not batch.is_locked
        batch.save(update_fields=['is_locked', 'updated_at'])
        return redirect('sales_orders:batch_detail', pk=pk)


class BatchCertificateView(StaffRequiredMixin, View):
    """Download PDF certificate for a batch."""
    def get(self, request, pk):
        batch = get_object_or_404(Batch, pk=pk, company=request.user.company)
        from .certificate_pdf import generate_certificate
        buffer = generate_certificate(batch)
        filename = f"AgriOps_Certificate_{batch.batch_number}.pdf"
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class PublicTraceView(View):
    """
    Public-facing traceability page — no login required.
    Accessed via QR code: /trace/<public_token>/
    """
    def get(self, request, token):
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
        cache_key = f'public_trace_{ip}'
        hits = cache.get(cache_key, 0)
        if hits >= 60:
            return HttpResponse('Rate limit exceeded. Please try again later.', status=429, content_type='text/plain')
        cache.set(cache_key, hits + 1, timeout=3600)

        batch = get_object_or_404(Batch, public_token=token)
        farms = batch.farms.select_related('supplier').all()
        return HttpResponse(
            self._render(batch, farms),
            content_type='text/html'
        )

    def _e(self, value):
        return html.escape(str(value)) if value else '—'

    def _render(self, batch, farms):
        farm_rows = ""
        for farm in farms:
            status_color = "#22c55e" if farm.is_eudr_verified else "#f59e0b"
            status_text = "Verified" if farm.is_eudr_verified else "Pending"
            supplier_name = self._e(farm.supplier.name) if farm.supplier else '—'
            area = f"{self._e(farm.area_hectares)} ha" if farm.area_hectares else '—'
            farm_rows += f"""
            <tr>
              <td style="padding:12px;border-bottom:1px solid #1e2d40;">{self._e(farm.name)}</td>
              <td style="padding:12px;border-bottom:1px solid #1e2d40;">{supplier_name}</td>
              <td style="padding:12px;border-bottom:1px solid #1e2d40;">{self._e(farm.country)} / {self._e(farm.state_region)}</td>
              <td style="padding:12px;border-bottom:1px solid #1e2d40;">{area}</td>
              <td style="padding:12px;border-bottom:1px solid #1e2d40;color:{status_color};">{status_text}</td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Trace: {batch.batch_number} — AgriOps</title>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: Georgia, serif; background: #080d14; color: #e2e8f0; margin: 0; padding: 24px; }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    .header {{ background: #131f2e; border: 1px solid #1e2d40; border-radius: 16px; padding: 32px; margin-bottom: 24px; }}
    .badge {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #22c55e; letter-spacing: 0.2em; margin-bottom: 12px; }}
    h1 {{ font-family: 'Syne', sans-serif; font-size: 28px; color: #f8fafc; margin: 0 0 8px 0; }}
    .meta {{ font-size: 13px; color: #64748b; }}
    .card {{ background: #131f2e; border: 1px solid #1e2d40; border-radius: 12px; padding: 24px; margin-bottom: 16px; }}
    .card h2 {{ font-family: 'Syne', sans-serif; font-size: 14px; color: #22c55e; letter-spacing: 0.1em; margin: 0 0 16px 0; text-transform: uppercase; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ text-align: left; padding: 10px 12px; color: #64748b; font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; border-bottom: 1px solid #1e2d40; }}
    td {{ color: #cbd5e1; }}
    .footer {{ text-align: center; font-size: 11px; color: #334155; margin-top: 32px; font-family: 'JetBrains Mono', monospace; }}
    .verified-badge {{ display: inline-block; background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.3); color: #22c55e; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-family: 'JetBrains Mono', monospace; }}
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="badge">AGRIOPS · SUPPLY CHAIN TRACEABILITY</div>
    <h1>Batch: {html.escape(str(batch.batch_number))}</h1>
    <p class="meta">Commodity: {html.escape(str(batch.commodity))} &nbsp;·&nbsp; Created: {batch.created_at.strftime('%d %B %Y')}</p>
    {'<p class="meta">Sales Order: ' + html.escape(str(batch.sales_order.order_number)) + '</p>' if batch.sales_order else ''}
    <div style="margin-top:16px;">
      <span class="verified-badge">✓ Verified Supply Chain Record</span>
    </div>
  </div>

  <div class="card">
    <h2>Farm Traceability — {farms.count()} farms</h2>
    <table>
      <thead>
        <tr>
          <th>Farm</th>
          <th>Supplier</th>
          <th>Location</th>
          <th>Area</th>
          <th>Compliance Status</th>
        </tr>
      </thead>
      <tbody>
        {farm_rows if farm_rows else '<tr><td colspan="5" style="padding:12px;color:#475569;">No farms linked to this batch.</td></tr>'}
      </tbody>
    </table>
  </div>

  <div class="footer">
    AgriOps · app.agriops.io · Agricultural Supply Chain Intelligence<br>
    This record was generated from verified supply chain data and is intended for EU buyer compliance under EUDR 2023/1115.
  </div>
</div>
</body>
</html>"""
