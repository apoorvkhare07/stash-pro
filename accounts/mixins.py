class OrgQuerysetMixin:
    """
    Mixin for ViewSets that auto-filters querysets by the current organization
    and injects organization on create.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        org = getattr(self.request, 'organization', None)
        if org:
            qs = qs.filter(organization=org)
        return qs

    def perform_create(self, serializer):
        org = getattr(self.request, 'organization', None)
        serializer.save(organization=org)

    def perform_update(self, serializer):
        serializer.save()
