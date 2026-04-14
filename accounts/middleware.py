from accounts.models import Organization, UserOrganization


class OrganizationMiddleware:
    """
    Resolves the current organization from the X-Organization header.
    Sets request.organization and request.org_role.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None
        request.org_role = None

        if request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated:
            org_slug = request.META.get('HTTP_X_ORGANIZATION', '')

            if org_slug:
                membership = UserOrganization.objects.filter(
                    user=request.user,
                    organization__slug=org_slug,
                ).select_related('organization').first()

                if membership:
                    request.organization = membership.organization
                    request.org_role = membership.role

            # Fallback: if no header or no match, use first org
            if not request.organization:
                membership = UserOrganization.objects.filter(
                    user=request.user,
                ).select_related('organization').order_by('id').first()

                if membership:
                    request.organization = membership.organization
                    request.org_role = membership.role

        response = self.get_response(request)
        return response
