from django.contrib.auth.models import User, Group
from rest_framework import serializers
from .models import Organization, UserOrganization


def get_user_role(user):
    """Get the primary role name for a user (legacy group-based)."""
    if user.is_superuser:
        return 'Owner'
    group = user.groups.first()
    return group.name if group else None


def get_user_orgs(user):
    """Get list of organizations the user belongs to."""
    memberships = UserOrganization.objects.filter(user=user).select_related('organization')
    return [
        {
            'id': m.organization.id,
            'name': m.organization.name,
            'slug': m.organization.slug,
            'role': m.role,
        }
        for m in memberships
    ]


class OrgSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ('id', 'name', 'slug')


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    organizations = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'role', 'organizations')
        read_only_fields = ('id',)

    def get_role(self, obj):
        return get_user_role(obj)

    def get_organizations(self, obj):
        return get_user_orgs(obj)


class CreateUserSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(min_length=8, write_only=True)
    email = serializers.EmailField(required=False, default='')
    first_name = serializers.CharField(max_length=150, required=False, default='')
    last_name = serializers.CharField(max_length=150, required=False, default='')
    role = serializers.ChoiceField(choices=['owner', 'editor', 'viewer'])

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value

    def create(self, validated_data, organization=None):
        role = validated_data.pop('role')
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        if organization:
            UserOrganization.objects.create(user=user, organization=organization, role=role)
        return user


class UpdateUserSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    role = serializers.ChoiceField(choices=['owner', 'editor', 'viewer'], required=False)
    is_active = serializers.BooleanField(required=False)


class CreateOrgSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ('name', 'slug', 'shopify_store', 'shopify_access_token', 'shopify_webhook_secret')
        extra_kwargs = {
            'shopify_store': {'required': False},
            'shopify_access_token': {'required': False},
            'shopify_webhook_secret': {'required': False},
        }
