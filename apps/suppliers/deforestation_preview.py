"""
Deforestation checks view — status board on GET, engine trigger on POST.
"""
from django.views import View
from django.shortcuts import render

from apps.users.permissions import StaffRequiredMixin
from .models import Farm, Supplier
from .deforestation_engine import run_check


def _current_status(company, supplier_id=None):
    """
    Return per-farm check status from existing DeforestationCheck records.
    Used for both the GET (status board) and POST (after running checks).
    """
    farms_qs = (
        Farm.objects
        .filter(company=company)
        .select_related('supplier', 'farmer')
        .prefetch_related('deforestation_checks')
        .order_by('name')
    )
    if supplier_id:
        farms_qs = farms_qs.filter(supplier_id=supplier_id)

    rows      = []
    no_geom   = 0
    flagged   = clear = errors = inconclusive = unchecked = 0

    for farm in farms_qs:
        latest = farm.deforestation_checks.order_by('-created_at').first()

        if not farm.geolocation:
            no_geom += 1
            continue

        if latest is None:
            unchecked += 1
            rows.append({'farm': farm, 'check': None})
            continue

        if latest.risk_status == 'clear':
            clear += 1
        elif latest.risk_status == 'flagged':
            flagged += 1
        elif latest.risk_status == 'error':
            errors += 1
        else:
            inconclusive += 1

        rows.append({'farm': farm, 'check': latest})

    return {
        'rows':         rows,
        'flagged':      flagged,
        'clear':        clear,
        'errors':       errors,
        'inconclusive': inconclusive,
        'unchecked':    unchecked,
        'no_geom':      no_geom,
        'total':        len(rows),
    }


class DeforestationPreviewView(StaffRequiredMixin, View):

    def _suppliers(self, request):
        return Supplier.objects.filter(company=request.user.company).order_by('name')

    def get(self, request):
        supplier_id = request.GET.get('supplier_id') or None
        ctx = _current_status(request.user.company, supplier_id)
        ctx['suppliers']   = self._suppliers(request)
        ctx['selected_id'] = int(supplier_id) if supplier_id else None
        ctx['ran_now']     = False
        return render(request, 'suppliers/farms/deforestation_preview.html', ctx)

    def post(self, request):
        supplier_id = request.POST.get('supplier_id') or None
        company     = request.user.company

        farms_qs = (
            Farm.objects
            .filter(company=company)
            .select_related('supplier', 'farmer')
            .order_by('name')
        )
        if supplier_id:
            farms_qs = farms_qs.filter(supplier_id=supplier_id)

        for farm in farms_qs:
            if not farm.geolocation:
                continue
            run_check(farm, user=request.user)

        ctx = _current_status(company, supplier_id)
        ctx['suppliers']   = self._suppliers(request)
        ctx['selected_id'] = int(supplier_id) if supplier_id else None
        ctx['ran_now']     = True
        return render(request, 'suppliers/farms/deforestation_preview.html', ctx)
