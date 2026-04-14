from accounts.models import UserOrganization, AuditLog


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


def log_audit(request, action, instance, changes=None):
    """Log an action to the audit trail."""
    org, _ = resolve_org(request)
    if not org:
        return
    AuditLog.objects.create(
        organization=org,
        user=request.user if request.user.is_authenticated else None,
        action=action,
        model_name=instance.__class__.__name__,
        object_id=instance.pk,
        object_repr=str(instance)[:255],
        changes=changes or {},
    )


def get_model_changes(instance):
    """Get changed fields by comparing with DB state."""
    if not instance.pk:
        return {}
    try:
        db_instance = instance.__class__.objects.get(pk=instance.pk)
    except instance.__class__.DoesNotExist:
        return {}
    changes = {}
    for field in instance._meta.fields:
        name = field.name
        old_val = getattr(db_instance, name)
        new_val = getattr(instance, name)
        if old_val != new_val:
            changes[name] = {'old': str(old_val), 'new': str(new_val)}
    return changes


class OrgQuerysetMixin:
    """
    Mixin for ViewSets that auto-filters querysets by the current organization,
    injects organization on create, and logs all mutations to the audit trail.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        org, _ = resolve_org(self.request)
        if org:
            qs = qs.filter(organization=org)
        return qs

    def perform_create(self, serializer):
        org, _ = resolve_org(self.request)
        instance = serializer.save(organization=org)
        log_audit(self.request, 'create', instance)

    def perform_update(self, serializer):
        changes = get_model_changes(serializer.instance)
        instance = serializer.save()
        log_audit(self.request, 'update', instance, changes)

    def perform_destroy(self, instance):
        log_audit(self.request, 'delete', instance)
        super().perform_destroy(instance)
