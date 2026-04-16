import csv
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.utils import timezone
from django.views.generic import ListView

from .models import AuditLog


class AuditLogListView(LoginRequiredMixin, ListView):
    model = AuditLog
    template_name = 'audit/audit_log.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_queryset(self):
        qs = (
            AuditLog.objects
            .filter(company=self.request.user.company)
            .select_related('user')
        )

        action = self.request.GET.get('action', '').strip()
        if action in ('create', 'update', 'delete', 'import'):
            qs = qs.filter(action=action)

        model = self.request.GET.get('model', '').strip()
        if model:
            qs = qs.filter(model_name__iexact=model)

        user_id = self.request.GET.get('user', '').strip()
        if user_id.isdigit():
            qs = qs.filter(user_id=int(user_id))

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(object_repr__icontains=q)

        date_range = self.request.GET.get('range', '').strip()
        if date_range == 'today':
            qs = qs.filter(timestamp__date=timezone.now().date())
        elif date_range == '7d':
            qs = qs.filter(timestamp__gte=timezone.now() - timedelta(days=7))
        elif date_range == '30d':
            qs = qs.filter(timestamp__gte=timezone.now() - timedelta(days=30))

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        ctx['company_users'] = User.objects.filter(
            company=self.request.user.company, is_active=True
        ).order_by('first_name', 'last_name')
        ctx['distinct_models'] = (
            AuditLog.objects
            .filter(company=self.request.user.company)
            .values_list('model_name', flat=True)
            .distinct()
            .order_by('model_name')
        )
        ctx['current_filters'] = {
            'action':   self.request.GET.get('action', ''),
            'model':    self.request.GET.get('model', ''),
            'user':     self.request.GET.get('user', ''),
            'q':        self.request.GET.get('q', ''),
            'range':    self.request.GET.get('range', ''),
        }
        return ctx

    def get(self, request, *args, **kwargs):
        if request.GET.get('export') == 'csv':
            return self._export_csv(request)
        return super().get(request, *args, **kwargs)

    def _export_csv(self, request):
        qs = self.get_queryset()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit-log.csv"'
        writer = csv.writer(response)
        writer.writerow(['Timestamp', 'User', 'Action', 'Model', 'Object', 'IP Address'])
        for log in qs:
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                str(log.user) if log.user else '—',
                log.get_action_display(),
                log.model_name,
                log.object_repr,
                log.ip_address or '—',
            ])
        return response
