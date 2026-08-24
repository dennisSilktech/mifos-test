from rest_framework.permissions import BasePermission

from .models import User

PLATFORM_STAFF_ROLES = {User.Role.SUPER_ADMIN, User.Role.SUPPORT, User.Role.AUDITOR, User.Role.FINANCE}


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == User.Role.SUPER_ADMIN)


class IsPlatformSupportOrAbove(BasePermission):
    """Super Admin, Support, or Auditor — read/manage scope over tenants & audit data."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {User.Role.SUPER_ADMIN, User.Role.SUPPORT, User.Role.AUDITOR}
        )


class IsFinanceOrSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {User.Role.SUPER_ADMIN, User.Role.FINANCE}
        )


class IsAuditorOrSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {User.Role.SUPER_ADMIN, User.Role.AUDITOR, User.Role.SUPPORT}
        )


class IsTenantCEOOrAdmin(BasePermission):
    """Scoped to the resolved tenant — CEO/org admin only."""

    def has_permission(self, request, view):
        tenant = getattr(request, "tenant", None)
        return bool(
            request.user
            and request.user.is_authenticated
            and tenant
            and str(request.user.tenant_id) == str(tenant.id)
            and request.user.role == User.Role.CEO
        )


class IsTenantBranchManagerOrAbove(BasePermission):
    def has_permission(self, request, view):
        tenant = getattr(request, "tenant", None)
        return bool(
            request.user
            and request.user.is_authenticated
            and tenant
            and str(request.user.tenant_id) == str(tenant.id)
            and request.user.role in {User.Role.CEO, User.Role.BRANCH_MANAGER}
        )


class IsSameTenant(BasePermission):
    """Generic guard: the authenticated user must belong to the resolved tenant."""

    def has_permission(self, request, view):
        tenant = getattr(request, "tenant", None)
        return bool(
            request.user
            and request.user.is_authenticated
            and tenant
            and str(request.user.tenant_id) == str(tenant.id)
        )
