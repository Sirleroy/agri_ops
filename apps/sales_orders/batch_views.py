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
        phyto_certs = list(self.object.phytosanitary_certs.all())
        quality_tests = self.object.quality_tests.all()
        context['phytosanitary_certs'] = phyto_certs
        context['quality_tests'] = quality_tests
        context['readiness'] = {
            'farms': self.object.farms.exists(),
            'quantity': bool(self.object.quantity_kg),
            'phyto': any(c.is_current for c in phyto_certs),
            'quality': quality_tests.filter(result='pass').exists(),
        }
        return context


class BatchCreateView(AuditCreateMixin, StaffRequiredMixin, CreateView):
    model = Batch
    template_name = 'sales_orders/batches/form.html'
    fields = ['sales_order', 'commodity', 'quantity_kg', 'farms', 'notes']

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        from apps.suppliers.models import Farm
        from apps.sales_orders.models import SalesOrder
        company = self.request.user.company
        form.fields['farms'].queryset = Farm.objects.filter(company=company)
        form.fields['sales_order'].queryset = SalesOrder.objects.filter(company=company)
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_farms'] = context['form'].fields['farms'].queryset
        context['selected_farm_ids'] = set()
        return context

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.object.pk})


class BatchUpdateView(AuditUpdateMixin, StaffRequiredMixin, UpdateView):
    model = Batch
    template_name = 'sales_orders/batches/form.html'
    fields = ['sales_order', 'commodity', 'quantity_kg', 'farms', 'notes']

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_farms'] = context['form'].fields['farms'].queryset
        context['selected_farm_ids'] = set(
            str(pk) for pk in self.object.farms.values_list('pk', flat=True)
        )
        return context

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.object.pk})


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
        farm_cards = ""
        farms_list = list(farms)
        farm_count = len(farms_list)

        for farm in farms_list:
            status_color = "#22c55e" if farm.is_eudr_verified else "#f59e0b"
            status_text = "Verified" if farm.is_eudr_verified else "Pending"
            supplier_name = self._e(farm.supplier.name) if farm.supplier else '—'
            area = f"{self._e(farm.area_hectares)} ha" if farm.area_hectares else '—'
            location = f"{self._e(farm.country)} / {self._e(farm.state_region)}"

            # Desktop table rows
            farm_rows += f"""
            <tr>
              <td class="td" data-label="Farm">{self._e(farm.name)}</td>
              <td class="td" data-label="Supplier">{supplier_name}</td>
              <td class="td" data-label="Location">{location}</td>
              <td class="td" data-label="Area">{area}</td>
              <td class="td" data-label="Compliance Status" style="color:{status_color};">{status_text}</td>
            </tr>"""

            # Mobile cards
            farm_cards += f"""
            <div class="farm-card">
              <div class="farm-card-name">{self._e(farm.name)}</div>
              <div class="farm-card-grid">
                <span class="farm-label">Supplier</span><span class="farm-value">{supplier_name}</span>
                <span class="farm-label">Location</span><span class="farm-value">{location}</span>
                <span class="farm-label">Area</span><span class="farm-value">{area}</span>
                <span class="farm-label">Status</span><span class="farm-value" style="color:{status_color};">{status_text}</span>
              </div>
            </div>"""

        so_line = (
            f'<p class="meta">Sales Order: {html.escape(str(batch.sales_order.order_number))}</p>'
            if batch.sales_order else ''
        )
        empty_row = '<tr><td colspan="5" style="padding:16px;color:#475569;text-align:center;">No farms linked to this batch.</td></tr>'
        empty_card = '<p style="color:#475569;text-align:center;padding:16px 0;">No farms linked to this batch.</p>'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Trace: {html.escape(str(batch.batch_number))} — AgriOps</title>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: Georgia, serif; background: #080d14; color: #e2e8f0; margin: 0; padding: 16px; }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    .header {{ background: #131f2e; border: 1px solid #1e2d40; border-radius: 16px; padding: 24px; margin-bottom: 16px; }}
    .badge {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #22c55e; letter-spacing: 0.15em; margin-bottom: 10px; word-break: break-word; }}
    h1 {{ font-family: 'Syne', sans-serif; font-size: clamp(20px, 5vw, 28px); color: #f8fafc; margin: 0 0 8px 0; word-break: break-word; }}
    .meta {{ font-size: 13px; color: #64748b; margin: 4px 0; word-break: break-word; }}
    .card {{ background: #131f2e; border: 1px solid #1e2d40; border-radius: 12px; padding: 20px; margin-bottom: 16px; overflow: hidden; }}
    .card h2 {{ font-family: 'Syne', sans-serif; font-size: 13px; color: #22c55e; letter-spacing: 0.1em; margin: 0 0 16px 0; text-transform: uppercase; }}
    .verified-badge {{ display: inline-flex; align-items: center; gap: 6px; background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.3); color: #22c55e; padding: 5px 12px; border-radius: 6px; font-size: 12px; font-family: 'JetBrains Mono', monospace; margin-top: 14px; }}

    /* Desktop table */
    .table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; min-width: 480px; }}
    th {{ text-align: left; padding: 10px 12px; color: #64748b; font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; border-bottom: 1px solid #1e2d40; white-space: nowrap; }}
    .td {{ color: #cbd5e1; padding: 12px; border-bottom: 1px solid #1e2d40; word-break: break-word; vertical-align: top; }}

    /* Mobile farm cards (hidden on desktop) */
    .farm-cards {{ display: none; }}
    .farm-card {{ background: #0d1520; border: 1px solid #1e2d40; border-radius: 10px; padding: 14px; margin-bottom: 10px; }}
    .farm-card-name {{ font-family: 'Syne', sans-serif; font-size: 15px; color: #f1f5f9; font-weight: 700; margin-bottom: 10px; word-break: break-word; }}
    .farm-card-grid {{ display: grid; grid-template-columns: max-content 1fr; gap: 6px 12px; align-items: baseline; }}
    .farm-label {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #475569; text-transform: uppercase; letter-spacing: 0.08em; white-space: nowrap; }}
    .farm-value {{ font-size: 13px; color: #cbd5e1; word-break: break-word; }}

    .footer {{ text-align: center; font-size: 11px; color: #334155; margin-top: 28px; font-family: 'JetBrains Mono', monospace; line-height: 1.6; word-break: break-word; padding-bottom: 16px; }}

    @media (max-width: 600px) {{
      body {{ padding: 12px; }}
      .header {{ padding: 18px; }}
      .card {{ padding: 16px; }}
      .table-wrap table {{ display: none; }}
      .farm-cards {{ display: block; }}
    }}
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="badge">AGRIOPS · SUPPLY CHAIN TRACEABILITY</div>
    <h1>Batch: {html.escape(str(batch.batch_number))}</h1>
    <p class="meta">Commodity: {html.escape(str(batch.commodity))} &nbsp;·&nbsp; Created: {batch.created_at.strftime('%d %B %Y')}</p>
    {so_line}
    <div class="verified-badge">✓ Verified Supply Chain Record</div>
  </div>

  <div class="card">
    <h2>Farm Traceability — {farm_count} farm{'s' if farm_count != 1 else ''}</h2>

    <div class="table-wrap">
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
          {farm_rows if farm_rows else empty_row}
        </tbody>
      </table>
    </div>

    <div class="farm-cards">
      {farm_cards if farm_cards else empty_card}
    </div>
  </div>

  <div class="footer">
    AgriOps &middot; app.agriops.io &middot; Agricultural Supply Chain Intelligence<br>
    This record was generated from verified supply chain data and is intended for EU buyer compliance under EUDR 2023/1115.
  </div>
</div>
</body>
</html>"""
