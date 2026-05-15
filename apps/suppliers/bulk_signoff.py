"""
Bulk Compliance Readiness sign-off — reviewed bulk action.

Mirrors the deforestation_preview pattern: GET shows farms eligible for
sign-off (awaiting_signoff or expired); POST applies sign-off, re-checking
the evidence gate per farm server-side so a stale browser tab cannot push an
unready farm through.
"""
import datetime

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from apps.audit.mixins import log_action
from apps.users.permissions import ManagerRequiredMixin

from .models import Farm, Supplier


def _eligible_rows(company, supplier_id=None):
    """Return (awaiting, expired) lists — farms in those states whose evidence
    still passes (no readiness_blockers, not disqualified). Pulls
    deforestation_checks so per-row latest result renders without N+1."""
    qs = (
        Farm.objects
        .filter(company=company)
        .select_related('supplier', 'farmer', 'verified_by')
        .prefetch_related('deforestation_checks')
        .order_by('supplier__name', 'name')
    )
    if supplier_id:
        qs = qs.filter(supplier_id=supplier_id)

    awaiting, expired = [], []
    for farm in qs:
        state = farm.readiness_state
        if state == 'awaiting_signoff':
            awaiting.append(farm)
        elif state == 'expired' and not farm.readiness_blockers:
            expired.append(farm)
    return awaiting, expired


class BulkComplianceReadinessView(ManagerRequiredMixin, View):
    """Manager-only: review and sign off many farms at once."""

    template_name = 'suppliers/farms/bulk_signoff.html'

    def _suppliers(self, request):
        return Supplier.objects.filter(company=request.user.company).order_by('name')

    def _ctx(self, request, supplier_id):
        awaiting, expired = _eligible_rows(request.user.company, supplier_id)
        return {
            'awaiting':       awaiting,
            'expired':        expired,
            'awaiting_count': len(awaiting),
            'expired_count':  len(expired),
            'eligible_count': len(awaiting) + len(expired),
            'suppliers':      self._suppliers(request),
            'selected_id':    int(supplier_id) if supplier_id else None,
            'signed_off_now': 0,
            'skipped_now':    0,
        }

    def get(self, request):
        supplier_id = request.GET.get('supplier_id') or None
        return render(request, self.template_name, self._ctx(request, supplier_id))

    def post(self, request):
        supplier_id  = request.POST.get('supplier_id') or None
        selected_pks = request.POST.getlist('farm_pks')

        if not selected_pks:
            messages.warning(request, 'No farms selected.')
            return redirect(request.path + (f'?supplier_id={supplier_id}' if supplier_id else ''))

        farms = (
            Farm.objects
            .filter(company=request.user.company, pk__in=selected_pks)
            .select_related('supplier')
            .prefetch_related('deforestation_checks')
        )

        today  = datetime.date.today()
        expiry = today + datetime.timedelta(days=365)

        signed_off, skipped = [], []
        for farm in farms:
            # Re-check the evidence gate at submit — the browser tab may be
            # stale (a check was re-run, the polygon was re-saved, etc).
            if farm.is_disqualified or farm.readiness_blockers:
                skipped.append(farm)
                continue
            if farm.is_eudr_verified and farm.is_verification_current:
                # Already current — no-op rather than refresh the expiry silently.
                skipped.append(farm)
                continue

            farm.is_eudr_verified   = True
            farm.verified_by        = request.user
            farm.verified_date      = today
            farm.verification_expiry = expiry
            farm.save(update_fields=[
                'is_eudr_verified', 'verified_by', 'verified_date', 'verification_expiry',
            ])

            log_action(request, 'update', farm, changes={
                'compliance_readiness': 'signed off (bulk)',
                'verified_by':          request.user.get_username(),
                'verified_date':        today.isoformat(),
                'verification_expiry':  expiry.isoformat(),
            })
            signed_off.append(farm)

        if signed_off:
            messages.success(
                request,
                f'Compliance Readiness signed off for {len(signed_off)} '
                f'farm{"s" if len(signed_off) != 1 else ""}.'
            )
        if skipped:
            preview = ', '.join(f.name for f in skipped[:5])
            more    = '' if len(skipped) <= 5 else f' (and {len(skipped) - 5} more)'
            messages.warning(
                request,
                f'{len(skipped)} farm{"s" if len(skipped) != 1 else ""} skipped — '
                f'evidence had changed or sign-off already current: {preview}{more}.'
            )

        ctx = self._ctx(request, supplier_id)
        ctx['signed_off_now'] = len(signed_off)
        ctx['skipped_now']    = len(skipped)
        return render(request, self.template_name, ctx)
