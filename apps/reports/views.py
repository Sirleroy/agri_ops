from django.http import HttpResponse
from django.views import View
from django.utils import timezone
from apps.users.permissions import StaffRequiredMixin
from .pdf import generate_compliance_report


class ReportsIndexView(StaffRequiredMixin, View):
    def get(self, request):
        company = request.user.company
        if not company:
            from django.http import Http404
            raise Http404

        buffer = generate_compliance_report(company, request.user)

        filename = f"AgriOps_Compliance_Report_{company.name.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d')}.pdf"

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
