from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin):
    """
    Base mixin for role-based access control.
    Set required_role on any view to restrict access.

    Role hierarchy: org_admin > manager > staff > viewer
    """
    required_role = None

    ROLE_HIERARCHY = {
        'viewer':    1,
        'staff':     2,
        'manager':   3,
        'org_admin': 4,
    }

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.required_role:
            user_level = self.ROLE_HIERARCHY.get(request.user.system_role, 0)
            required_level = self.ROLE_HIERARCHY.get(self.required_role, 0)
            if user_level < required_level:
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class StaffRequiredMixin(RoleRequiredMixin):
    """Staff, Manager, or OrgAdmin only. Viewers are blocked."""
    required_role = 'staff'


class ManagerRequiredMixin(RoleRequiredMixin):
    """Manager or OrgAdmin only."""
    required_role = 'manager'


class OrgAdminRequiredMixin(RoleRequiredMixin):
    """OrgAdmin only."""
    required_role = 'org_admin'
