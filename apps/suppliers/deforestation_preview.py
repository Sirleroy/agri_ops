"""
Deforestation check view — runs the engine per farm and persists results.
"""
from django.views import View
from django.shortcuts import render

from apps.users.permissions import StaffRequiredMixin
from .models import Farm, Supplier
from .deforestation_engine import run_check


class DeforestationPreviewView(StaffRequiredMixin, View):

    def _suppliers(self, request):
        return Supplier.objects.filter(company=request.user.company).order_by('name')

    def get(self, request):
        return render(request, 'suppliers/farms/deforestation_preview.html', {
            'suppliers': self._suppliers(request),
        })

    def post(self, request):
        supplier_id = request.POST.get('supplier_id') or None
        company     = request.user.company

        farms_qs = Farm.objects.filter(company=company).select_related('supplier', 'farmer')
        if supplier_id:
            farms_qs = farms_qs.filter(supplier_id=supplier_id)

        checks   = []
        no_geom  = 0

        for farm in farms_qs.order_by('name'):
            if not farm.geolocation:
                no_geom += 1
                continue
            check = run_check(farm, user=request.user)
            checks.append({'farm': farm, 'check': check})

        flagged = sum(1 for c in checks if c['check'].risk_status == 'flagged')
        clear   = sum(1 for c in checks if c['check'].risk_status == 'clear')
        errors  = sum(1 for c in checks if c['check'].risk_status == 'error')

        return render(request, 'suppliers/farms/deforestation_preview.html', {
            'suppliers':   self._suppliers(request),
            'selected_id': int(supplier_id) if supplier_id else None,
            'checks':      checks,
            'flagged':     flagged,
            'clear':       clear,
            'errors':      errors,
            'no_geom':     no_geom,
            'total':       len(checks),
        })
