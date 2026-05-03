from apps.audit.mixins import AuditUpdateMixin, AuditDeleteMixin
from django.views.generic import ListView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from .models import CustomUser
from .permissions import OrgAdminRequiredMixin, ManagerRequiredMixin, CompanyOwnedMixin


class UserListView(ManagerRequiredMixin, ListView):
    model = CustomUser
    template_name = 'users/list.html'
    context_object_name = 'users'
    ordering = ['last_name', 'first_name']
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)


class UserDetailView(CompanyOwnedMixin, ManagerRequiredMixin, DetailView):
    model = CustomUser
    template_name = 'users/detail.html'
    context_object_name = 'profile'


class UserUpdateView(AuditUpdateMixin, CompanyOwnedMixin, OrgAdminRequiredMixin, UpdateView):
    model = CustomUser
    template_name = 'users/form.html'
    fields = ['username', 'first_name', 'last_name', 'email',
              'job_title', 'phone', 'is_active']

    def get_success_url(self):
        next_url = self.request.GET.get('next', '').strip()
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return reverse_lazy('users:detail', kwargs={'pk': self.object.pk})


class UserSystemRoleUpdateView(AuditUpdateMixin, CompanyOwnedMixin, OrgAdminRequiredMixin, UpdateView):
    """
    Separate view for changing system_role.
    OrgAdmin only. Isolated so system_role is never
    exposed in the general profile edit form.
    """
    model = CustomUser
    template_name = 'users/role_form.html'
    fields = ['system_role']
    success_url = reverse_lazy('users:list')


class UserDeleteView(AuditDeleteMixin, CompanyOwnedMixin, OrgAdminRequiredMixin, DeleteView):
    model = CustomUser
    template_name = 'users/confirm_delete.html'
    success_url = reverse_lazy('users:list')
