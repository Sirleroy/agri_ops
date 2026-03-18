from apps.audit.mixins import AuditUpdateMixin
from django.views.generic import ListView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import CustomUser
from .permissions import OrgAdminRequiredMixin, StaffRequiredMixin


class UserListView(StaffRequiredMixin, ListView):
    model = CustomUser
    template_name = 'users/list.html'
    context_object_name = 'users'
    ordering = ['last_name', 'first_name']

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)


class UserDetailView(StaffRequiredMixin, DetailView):
    model = CustomUser
    template_name = 'users/detail.html'
    context_object_name = 'profile'

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class UserUpdateView(OrgAdminRequiredMixin, UpdateView):
    model = CustomUser
    template_name = 'users/form.html'
    fields = ['username', 'first_name', 'last_name', 'email',
              'job_title', 'phone', 'is_active']
    success_url = reverse_lazy('users:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class UserSystemRoleUpdateView(AuditUpdateMixin, OrgAdminRequiredMixin, UpdateView):
    """
    Separate view for changing system_role.
    OrgAdmin only. Isolated so system_role is never
    exposed in the general profile edit form.
    """
    model = CustomUser
    template_name = 'users/role_form.html'
    fields = ['system_role']
    success_url = reverse_lazy('users:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj


class UserDeleteView(OrgAdminRequiredMixin, DeleteView):
    model = CustomUser
    template_name = 'users/confirm_delete.html'
    success_url = reverse_lazy('users:list')

    def get_object(self):
        obj = super().get_object()
        if obj.company != self.request.user.company:
            from django.http import Http404
            raise Http404
        return obj
