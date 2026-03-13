from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class ReportsIndexView(LoginRequiredMixin, TemplateView):
    template_name = 'coming_soon.html'
