from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class Organization(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Shopify credentials per org
    shopify_store = models.CharField(max_length=255, blank=True, default='')
    shopify_access_token = models.CharField(max_length=255, blank=True, default='')
    shopify_webhook_secret = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return self.name


class UserOrganization(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner', _('Owner')
        EDITOR = 'editor', _('Editor')
        VIEWER = 'viewer', _('Viewer')

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='org_memberships')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EDITOR)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'organization')

    def __str__(self):
        return f"{self.user.username} @ {self.organization.name} ({self.role})"
