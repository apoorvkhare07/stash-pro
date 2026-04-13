from rest_framework.permissions import BasePermission


class HasModelPermission(BasePermission):
    """Check Django's built-in model permissions based on request method."""

    METHOD_PERMISSION_MAP = {
        'GET': 'view',
        'HEAD': 'view',
        'OPTIONS': 'view',
        'POST': 'add',
        'PUT': 'change',
        'PATCH': 'change',
        'DELETE': 'delete',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        model = getattr(view, 'queryset', None)
        if model is not None:
            model = model.model

        if model is None:
            return True

        action = self.METHOD_PERMISSION_MAP.get(request.method)
        if action is None:
            return False

        app_label = model._meta.app_label
        model_name = model._meta.model_name
        perm = f'{app_label}.{action}_{model_name}'
        return request.user.has_perm(perm)


class IsOwnerGroup(BasePermission):
    """Only users in the 'Owner' group can access."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name='Owner').exists()
