from rest_framework.permissions import BasePermission

ROLE_HIERARCHY = {
    'viewer':    1,
    'staff':     2,
    'manager':   3,
    'org_admin': 4,
}


class IsTenantMember(BasePermission):
    """Request user must belong to an active company."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.company_id
            and request.user.company.is_active
        )


class IsStaffOrAbove(IsTenantMember):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return ROLE_HIERARCHY.get(request.user.system_role, 0) >= 2


class IsManagerOrAbove(IsTenantMember):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return ROLE_HIERARCHY.get(request.user.system_role, 0) >= 3


class IsOrgAdmin(IsTenantMember):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.system_role == 'org_admin'
