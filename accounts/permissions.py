from rest_framework.permissions import BasePermission
from accounts.mixins import resolve_org


class HasModelPermission(BasePermission):
    """
    Check permissions based on org role:
    - owner: full access
    - editor: full access
    - viewer: read-only (GET, HEAD, OPTIONS)
    """

    SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        _, org_role = resolve_org(request)

        if not org_role:
            return False

        if org_role in ('owner', 'editor'):
            return True

        if org_role == 'viewer' and request.method in self.SAFE_METHODS:
            return True

        return False


class IsOwnerGroup(BasePermission):
    """Only org owners can access."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True

        _, org_role = resolve_org(request)
        return org_role == 'owner'
