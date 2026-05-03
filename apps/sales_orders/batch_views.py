import html
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.core.cache import cache
from django.utils.http import url_has_allowed_host_and_scheme
from apps.users.permissions import (
    StaffRequiredMixin, ManagerRequiredMixin, DatePickerMixin, OtherRevealMixin,
    CompanyOwnedMixin, CompanySetMixin,
)
from apps.audit.mixins import AuditCreateMixin, AuditUpdateMixin, AuditDeleteMixin
from .batch import Batch
from .quality import PhytosanitaryCertificate, BatchQualityTest


class BatchListView(StaffRequiredMixin, ListView):
    model = Batch
    template_name = 'sales_orders/batches/list.html'
    context_object_name = 'batches'
    paginate_by = 50

    def get_queryset(self):
        return Batch.objects.filter(company=self.request.user.company).select_related('sales_order')


class BatchDetailView(CompanyOwnedMixin, StaffRequiredMixin, DetailView):
    model = Batch
    template_name = 'sales_orders/batches/detail.html'
    context_object_name = 'batch'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        farms = list(self.object.farms.all())
        phyto_certs = list(self.object.phytosanitary_certs.all())
        quality_tests = list(self.object.quality_tests.all())
        context['phytosanitary_certs'] = phyto_certs
        context['quality_tests'] = quality_tests
        batch_pos = list(
            self.object.purchase_orders
            .select_related('supplier')
            .prefetch_related('items__product')
            .order_by('order_date')
        )
        context['batch_purchase_orders'] = batch_pos
        context['readiness'] = self.object.certificate_readiness(
            farms=farms,
            phyto_certs=phyto_certs,
            quality_tests=quality_tests,
            purchase_orders=batch_pos,
        )
        return context


class BatchCreateView(AuditCreateMixin, CompanySetMixin, StaffRequiredMixin, CreateView):
    model = Batch
    template_name = 'sales_orders/batches/form.html'
    fields = ['sales_order', 'commodity', 'quantity_kg', 'farms', 'purchase_orders', 'notes']

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        from apps.suppliers.models import Farm
        from apps.sales_orders.models import SalesOrder
        from apps.purchase_orders.models import PurchaseOrder
        company = self.request.user.company
        form.fields['farms'].queryset = Farm.objects.filter(company=company)
        form.fields['sales_order'].queryset = SalesOrder.objects.filter(company=company)
        form.fields['purchase_orders'].queryset = PurchaseOrder.objects.filter(
            company=company
        ).select_related('supplier').prefetch_related('items__product').order_by('-order_date')
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_farms'] = context['form'].fields['farms'].queryset
        context['selected_farm_ids'] = set()
        context['all_purchase_orders'] = context['form'].fields['purchase_orders'].queryset
        context['selected_po_ids'] = set()
        return context

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.object.pk})


class BatchUpdateView(AuditUpdateMixin, CompanyOwnedMixin, StaffRequiredMixin, UpdateView):
    model = Batch
    template_name = 'sales_orders/batches/form.html'
    fields = ['sales_order', 'commodity', 'quantity_kg', 'farms', 'purchase_orders', 'notes']

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
        from apps.purchase_orders.models import PurchaseOrder
        company = self.request.user.company
        form.fields['farms'].queryset = Farm.objects.filter(company=company)
        form.fields['sales_order'].queryset = SalesOrder.objects.filter(company=company)
        form.fields['purchase_orders'].queryset = PurchaseOrder.objects.filter(
            company=company
        ).select_related('supplier').prefetch_related('items__product').order_by('-order_date')
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_farms'] = context['form'].fields['farms'].queryset
        context['selected_farm_ids'] = set(
            str(pk) for pk in self.object.farms.values_list('pk', flat=True)
        )
        context['all_purchase_orders'] = context['form'].fields['purchase_orders'].queryset
        context['selected_po_ids'] = set(
            str(pk) for pk in self.object.purchase_orders.values_list('pk', flat=True)
        )
        return context

    def get_success_url(self):
        next_url = self.request.GET.get('next', '').strip()
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.object.pk})


# ─────────────────────────────────────
# PHYTOSANITARY CERTIFICATE VIEWS
# ─────────────────────────────────────

class PhytosanitaryCertCreateView(DatePickerMixin, AuditCreateMixin, CompanySetMixin, StaffRequiredMixin, CreateView):
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
        form.instance.batch = self.get_batch()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.kwargs['batch_pk']})


class PhytosanitaryCertUpdateView(DatePickerMixin, AuditUpdateMixin, CompanyOwnedMixin, StaffRequiredMixin, UpdateView):
    model = PhytosanitaryCertificate
    template_name = 'sales_orders/batches/phytosanitary_form.html'
    fields = ['certificate_number', 'issuing_office', 'inspector_name',
              'inspection_date', 'issued_date', 'expiry_date', 'notes']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.object.batch
        return context

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.object.batch_id})


class PhytosanitaryCertDeleteView(AuditDeleteMixin, CompanyOwnedMixin, ManagerRequiredMixin, DeleteView):
    model = PhytosanitaryCertificate

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.object.batch_id})


# ─────────────────────────────────────
# BATCH QUALITY TEST VIEWS
# ─────────────────────────────────────

class BatchQualityTestCreateView(OtherRevealMixin, DatePickerMixin, AuditCreateMixin, CompanySetMixin, StaffRequiredMixin, CreateView):
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
        form.instance.batch = self.get_batch()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.kwargs['batch_pk']})


class BatchQualityTestUpdateView(OtherRevealMixin, DatePickerMixin, AuditUpdateMixin, CompanyOwnedMixin, StaffRequiredMixin, UpdateView):
    model = BatchQualityTest
    template_name = 'sales_orders/batches/quality_form.html'
    fields = ['test_type', 'lab_name', 'lab_certificate_ref', 'test_date', 'result', 'notes']
    other_reveal_fields = ['test_type']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.object.batch
        return context

    def get_success_url(self):
        return reverse_lazy('sales_orders:batch_detail', kwargs={'pk': self.object.batch_id})


class BatchQualityTestDeleteView(AuditDeleteMixin, CompanyOwnedMixin, ManagerRequiredMixin, DeleteView):
    model = BatchQualityTest

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
        readiness = batch.certificate_readiness()
        if not readiness['can_download_certificate']:
            from django.contrib import messages
            messages.error(request, "Certificate download blocked: " + " ".join(readiness['blockers']))
            return redirect('sales_orders:batch_detail', pk=pk)
        from .certificate_pdf import generate_certificate
        buffer = generate_certificate(batch)
        filename = f"AgriOps_Certificate_{batch.batch_number}.pdf"
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class NeutralCertificateView(StaffRequiredMixin, View):
    """Download buyer-neutral Supply Chain Traceability Certificate (no EUDR branding)."""
    def get(self, request, pk):
        batch = get_object_or_404(Batch, pk=pk, company=request.user.company)
        if request.user.company.plan_tier != 'enterprise':
            from django.contrib import messages
            messages.error(request, "Supply Chain Traceability Certificates are available on the Enterprise plan.")
            return redirect('sales_orders:batch_detail', pk=pk)
        readiness = batch.certificate_readiness()
        if not readiness['can_download_certificate']:
            from django.contrib import messages
            messages.error(request, "Certificate download blocked: " + " ".join(readiness['blockers']))
            return redirect('sales_orders:batch_detail', pk=pk)
        from .certificate_pdf import generate_neutral_certificate
        buffer = generate_neutral_certificate(batch)
        filename = f"AgriOps_TraceabilityCert_{batch.batch_number}.pdf"
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
        farms        = list(batch.farms.select_related('supplier', 'verified_by').prefetch_related('certifications').all())
        phyto_certs  = list(batch.phytosanitary_certs.all())
        quality_tests = list(batch.quality_tests.all())
        readiness = batch.certificate_readiness(
            farms=farms, phyto_certs=phyto_certs, quality_tests=quality_tests
        )
        return HttpResponse(
            self._render(batch, farms, readiness),
            content_type='text/html'
        )

    def _e(self, value):
        return html.escape(str(value)) if value else '—'

    def _centroid(self, geolocation):
        if not geolocation:
            return None
        try:
            coords = geolocation.get('coordinates', [[]])[0]
            if not coords:
                return None
            lngs = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            lat = sum(lats) / len(lats)
            lng = sum(lngs) / len(lngs)
            lat_str = f"{abs(lat):.5f}°{'N' if lat >= 0 else 'S'}"
            lng_str = f"{abs(lng):.5f}°{'E' if lng >= 0 else 'W'}"
            return f"{lat_str}, {lng_str}"
        except (KeyError, IndexError, TypeError, ZeroDivisionError):
            return None

    def _render(self, batch, farms, readiness):
        farm_count = len(farms)

        # ── Farm overview rows / cards ────────────────────────
        farm_rows = ""
        farm_cards = ""
        for farm in farms:
            status_color = "#22c55e" if farm.is_eudr_verified else "#f59e0b"
            status_text  = "Verified" if farm.is_eudr_verified else "Pending"
            supplier_name = self._e(farm.supplier.name) if farm.supplier else '—'
            area          = f"{self._e(farm.area_hectares)} ha" if farm.area_hectares else '—'
            location      = f"{self._e(farm.country)} / {self._e(farm.state_region)}"

            farm_rows += f"""
            <tr>
              <td class="td">{self._e(farm.name)}</td>
              <td class="td">{supplier_name}</td>
              <td class="td">{location}</td>
              <td class="td">{area}</td>
              <td class="td" style="color:{status_color};font-weight:600;">{status_text}</td>
            </tr>"""

            farm_cards += f"""
            <div class="farm-card">
              <div class="farm-card-name">{self._e(farm.name)}</div>
              <div class="ev-grid">
                <span class="ev-label">Supplier</span><span class="ev-value">{supplier_name}</span>
                <span class="ev-label">Location</span><span class="ev-value">{location}</span>
                <span class="ev-label">Area</span><span class="ev-value">{area}</span>
                <span class="ev-label">Status</span><span class="ev-value" style="color:{status_color};font-weight:600;">{status_text}</span>
              </div>
            </div>"""

        # ── Verification evidence blocks ──────────────────────
        evidence_html = ""
        from datetime import date as _date
        for farm in farms:
            if not farm.is_eudr_verified:
                continue
            verifier  = self._e(farm.verified_by.get_full_name() or farm.verified_by.username) if farm.verified_by else '—'
            v_date    = farm.verified_date.strftime('%d %b %Y') if farm.verified_date else '—'
            v_expiry  = farm.verification_expiry.strftime('%d %b %Y') if farm.verification_expiry else '—'
            centroid  = self._centroid(farm.geolocation) or '—'
            ref_date  = farm.deforestation_reference_date.strftime('%d %b %Y') if farm.deforestation_reference_date else '—'
            fvf = ('Signed ' + farm.fvf_consent_date.strftime('%d %b %Y')) if (farm.fvf_consent_given and farm.fvf_consent_date) else \
                  ('Signed — date not recorded' if farm.fvf_consent_given else 'Not recorded')

            certs_html = ""
            for c in farm.certifications.all():
                is_active   = not c.expiry_date or c.expiry_date >= _date.today()
                exp_color   = "#22c55e" if is_active else "#f87171"
                exp_text    = c.expiry_date.strftime('%d %b %Y') if c.expiry_date else '—'
                issued_text = c.issued_date.strftime('%d %b %Y') if c.issued_date else '—'
                certs_html += f"""
                <div class="cert-row">
                  <span class="cert-type">{self._e(c.get_cert_type_display())}</span>
                  <div class="ev-grid">
                    <span class="ev-label">Certifying body</span><span class="ev-value">{self._e(c.certifying_body)}</span>
                    <span class="ev-label">Cert number</span><span class="ev-value">{self._e(c.certificate_number) if c.certificate_number else '—'}</span>
                    <span class="ev-label">Issued</span><span class="ev-value">{issued_text}</span>
                    <span class="ev-label">Expires</span><span class="ev-value" style="color:{exp_color};">{exp_text}</span>
                  </div>
                </div>"""

            evidence_html += f"""
            <div class="ev-block">
              <div class="ev-farm-name">{self._e(farm.name)}</div>
              <div class="ev-grid">
                <span class="ev-label">Verified by</span><span class="ev-value">{verifier}</span>
                <span class="ev-label">Verified date</span><span class="ev-value">{v_date}</span>
                <span class="ev-label">Expiry</span><span class="ev-value">{v_expiry}</span>
                <span class="ev-label">GPS centroid</span><span class="ev-value mono">{centroid}</span>
                <span class="ev-label">Deforestation ref.</span><span class="ev-value">{ref_date}</span>
                <span class="ev-label">FVF consent</span><span class="ev-value">{fvf}</span>
              </div>
              {('<div class="cert-section"><p class="cert-heading">Certifications</p>' + certs_html + '</div>') if certs_html else ''}
            </div>"""

        evidence_card = f"""
  <div class="card">
    <h2>Verification Evidence</h2>
    <p class="ev-intro">The records below substantiate the Verified status shown in the farm table. Each entry was recorded in the AgriOps platform by a named operator and is retained for audit.</p>
    {evidence_html}
  </div>""" if evidence_html else ""

        so_line = (
            f'<p class="meta">Sales Order: {html.escape(str(batch.sales_order.order_number))}</p>'
            if batch.sales_order else ''
        )
        empty_row  = '<tr><td colspan="5" style="padding:16px;color:#475569;text-align:center;">No farms linked to this batch.</td></tr>'
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
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #080d14; color: #e2e8f0; margin: 0; padding: 16px; }}
    .container {{ max-width: 900px; margin: 0 auto; }}

    /* Header */
    .header {{ background: #131f2e; border: 1px solid #1e2d40; border-radius: 16px; padding: 24px; margin-bottom: 16px; }}
    .badge {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #22c55e; letter-spacing: 0.15em; margin-bottom: 10px; word-break: break-word; }}
    h1 {{ font-family: 'Syne', sans-serif; font-size: clamp(20px, 5vw, 28px); color: #f8fafc; margin: 0 0 8px 0; word-break: break-word; line-height: 1.2; }}
    .meta {{ font-size: 13px; color: #64748b; margin: 4px 0; word-break: break-word; }}
    .verified-badge {{ display: inline-flex; align-items: center; gap: 6px; background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.3); color: #22c55e; padding: 5px 12px; border-radius: 6px; font-size: 12px; font-family: 'JetBrains Mono', monospace; margin-top: 14px; }}
    .pending-badge  {{ display: inline-flex; align-items: center; gap: 6px; background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.3); color: #f59e0b; padding: 5px 12px; border-radius: 6px; font-size: 12px; font-family: 'JetBrains Mono', monospace; margin-top: 14px; }}

    /* Cards */
    .card {{ background: #131f2e; border: 1px solid #1e2d40; border-radius: 12px; padding: 20px; margin-bottom: 16px; overflow: hidden; }}
    .card h2 {{ font-family: 'Syne', sans-serif; font-size: 12px; color: #22c55e; letter-spacing: 0.12em; margin: 0 0 16px 0; text-transform: uppercase; }}

    /* Farm overview table (desktop) */
    .table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; min-width: 480px; }}
    th {{ text-align: left; padding: 10px 12px; color: #64748b; font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; border-bottom: 1px solid #1e2d40; white-space: nowrap; }}
    .td {{ color: #cbd5e1; padding: 12px; border-bottom: 1px solid #1e2d40; word-break: break-word; vertical-align: top; font-size: 13px; }}

    /* Farm overview mobile cards */
    .farm-cards {{ display: none; }}
    .farm-card {{ background: #0d1520; border: 1px solid #1e2d40; border-radius: 10px; padding: 14px; margin-bottom: 10px; }}
    .farm-card-name {{ font-family: 'Syne', sans-serif; font-size: 15px; color: #f1f5f9; font-weight: 700; margin-bottom: 10px; word-break: break-word; }}

    /* Shared label/value grid — used in farm cards AND evidence blocks */
    .ev-grid {{ display: grid; grid-template-columns: max-content 1fr; gap: 5px 14px; align-items: baseline; }}
    .ev-label {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #475569; text-transform: uppercase; letter-spacing: 0.08em; white-space: nowrap; }}
    .ev-value {{ font-size: 13px; color: #cbd5e1; word-break: break-word; }}
    .ev-value.mono {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; }}

    /* Verification evidence section */
    .ev-intro {{ font-size: 12px; color: #475569; margin: -4px 0 16px 0; line-height: 1.5; }}
    .ev-block {{ background: #0d1520; border: 1px solid #1e2d40; border-radius: 10px; padding: 14px; margin-bottom: 12px; }}
    .ev-farm-name {{ font-family: 'Syne', sans-serif; font-size: 14px; color: #f1f5f9; font-weight: 700; margin-bottom: 10px; word-break: break-word; }}

    /* Certifications within evidence */
    .cert-section {{ margin-top: 12px; padding-top: 12px; border-top: 1px solid #1e2d40; }}
    .cert-heading {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #475569; text-transform: uppercase; letter-spacing: 0.1em; margin: 0 0 8px 0; }}
    .cert-row {{ background: #131f2e; border: 1px solid #1e2d40; border-radius: 8px; padding: 10px; margin-bottom: 8px; }}
    .cert-type {{ display: block; font-size: 12px; font-weight: 600; color: #94a3b8; margin-bottom: 6px; }}

    /* Footer */
    .footer {{ text-align: center; font-size: 11px; color: #334155; margin-top: 28px; font-family: 'JetBrains Mono', monospace; line-height: 1.6; word-break: break-word; padding-bottom: 16px; }}

    @media (max-width: 600px) {{
      body {{ padding: 12px; }}
      .header {{ padding: 18px; border-radius: 12px; }}
      .card {{ padding: 16px; border-radius: 10px; }}
      .table-wrap table {{ display: none; }}
      .farm-cards {{ display: block; }}
      .ev-grid {{ gap: 4px 10px; }}
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
    {'<div class="verified-badge">✓ Verified Supply Chain Record</div>' if readiness['can_download_certificate'] else '<div class="pending-badge">⚠ Compliance Pending</div>'}
  </div>

  <div class="card">
    <h2>Farm Traceability — {farm_count} farm{'s' if farm_count != 1 else ''}</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Farm</th><th>Supplier</th><th>Location</th><th>Area</th><th>Compliance Status</th></tr>
        </thead>
        <tbody>{farm_rows if farm_rows else empty_row}</tbody>
      </table>
    </div>
    <div class="farm-cards">
      {farm_cards if farm_cards else empty_card}
    </div>
  </div>

  {evidence_card}

  <div class="footer">
    AgriOps &middot; app.agriops.io &middot; Agricultural Supply Chain Intelligence<br>
    {'This record was generated from verified supply chain data and is intended for EU buyer compliance under EUDR (Regulation (EU) 2023/1115 as amended by Regulation (EU) 2025/2650).' if readiness['can_download_certificate'] else 'This supply chain record is maintained in AgriOps. Compliance verification for this batch is ongoing.'}
  </div>

</div>
</body>
</html>"""
