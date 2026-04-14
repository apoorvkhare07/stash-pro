from accounts.models import UserOrganization


def resolve_org(request):
    """Resolve organization from X-Organization header for authenticated user."""
    if not request.user or not request.user.is_authenticated:
        return None, None

    cached = getattr(request, '_org_resolved', False)
    if cached:
        return request.organization, request.org_role

    org = None
    org_role = None
    org_slug = request.META.get('HTTP_X_ORGANIZATION', '')

    if org_slug:
        membership = UserOrganization.objects.filter(
            user=request.user,
            organization__slug=org_slug,
        ).select_related('organization').first()
        if membership:
            org = membership.organization
            org_role = membership.role

    # Fallback: first org
    if not org:
        membership = UserOrganization.objects.filter(
            user=request.user,
        ).select_related('organization').order_by('id').first()
        if membership:
            org = membership.organization
            org_role = membership.role

    request.organization = org
    request.org_role = org_role
    request._org_resolved = True
    return org, org_role


class OrgQuerysetMixin:
    """
    Mixin for ViewSets that auto-filters querysets by the current organization
    and injects organization on create.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        org, _ = resolve_org(self.request)
        if org:
            qs = qs.filter(organization=org)
        return qs

    def perform_create(self, serializer):
        org, _ = resolve_org(self.request)
        serializer.save(organization=org)

    def perform_update(self, serializer):
        serializer.save()
