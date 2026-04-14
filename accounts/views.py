from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Organization, UserOrganization
from .permissions import IsOwnerGroup
from .serializers import (
    get_user_role, get_user_orgs,
    UserSerializer, CreateUserSerializer, UpdateUserSerializer,
    OrgSerializer, CreateOrgSerializer,
)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        orgs = get_user_orgs(self.user)
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'role': get_user_role(self.user),
            'organizations': orgs,
        }
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        org = getattr(request, 'organization', None)
        org_role = getattr(request, 'org_role', None)
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': get_user_role(user),
            'organizations': get_user_orgs(user),
            'current_organization': {
                'id': org.id,
                'name': org.name,
                'slug': org.slug,
                'role': org_role,
            } if org else None,
        })


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not old_password or not new_password:
            return Response(
                {'error': 'old_password and new_password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.check_password(old_password):
            return Response(
                {'error': 'Current password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(new_password) < 8:
            return Response(
                {'error': 'New password must be at least 8 characters'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()
        return Response({'message': 'Password changed successfully'})


class UserListCreateView(APIView):
    """List and create users scoped to the current organization."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = getattr(request, 'organization', None)
        if not org:
            return Response({'error': 'No organization selected'}, status=status.HTTP_400_BAD_REQUEST)

        # Only org owners can manage users
        if getattr(request, 'org_role', None) != 'owner':
            return Response({'error': 'Only organization owners can manage users'}, status=status.HTTP_403_FORBIDDEN)

        memberships = UserOrganization.objects.filter(organization=org).select_related('user')
        users = []
        for m in memberships:
            u = m.user
            users.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'first_name': u.first_name,
                'last_name': u.last_name,
                'is_active': u.is_active,
                'role': m.role,
            })
        return Response(users)

    def post(self, request):
        org = getattr(request, 'organization', None)
        if not org:
            return Response({'error': 'No organization selected'}, status=status.HTTP_400_BAD_REQUEST)

        if getattr(request, 'org_role', None) != 'owner':
            return Response({'error': 'Only organization owners can create users'}, status=status.HTTP_403_FORBIDDEN)

        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.create(serializer.validated_data, organization=org)

        membership = UserOrganization.objects.get(user=user, organization=org)
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'role': membership.role,
        }, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        org = getattr(request, 'organization', None)
        if not org or getattr(request, 'org_role', None) != 'owner':
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        try:
            membership = UserOrganization.objects.select_related('user').get(user_id=pk, organization=org)
        except UserOrganization.DoesNotExist:
            return Response({'error': 'User not found in this organization'}, status=status.HTTP_404_NOT_FOUND)

        u = membership.user
        return Response({
            'id': u.id, 'username': u.username, 'email': u.email,
            'first_name': u.first_name, 'last_name': u.last_name,
            'is_active': u.is_active, 'role': membership.role,
        })

    def put(self, request, pk):
        org = getattr(request, 'organization', None)
        if not org or getattr(request, 'org_role', None) != 'owner':
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        try:
            membership = UserOrganization.objects.select_related('user').get(user_id=pk, organization=org)
        except UserOrganization.DoesNotExist:
            return Response({'error': 'User not found in this organization'}, status=status.HTTP_404_NOT_FOUND)

        serializer = UpdateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = membership.user
        if 'email' in data:
            user.email = data['email']
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'is_active' in data:
            user.is_active = data['is_active']
        user.save()

        if 'role' in data:
            membership.role = data['role']
            membership.save()

        return Response({
            'id': user.id, 'username': user.username, 'email': user.email,
            'first_name': user.first_name, 'last_name': user.last_name,
            'is_active': user.is_active, 'role': membership.role,
        })

    def delete(self, request, pk):
        org = getattr(request, 'organization', None)
        if not org or getattr(request, 'org_role', None) != 'owner':
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        if pk == request.user.id:
            return Response({'error': 'Cannot remove yourself'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            membership = UserOrganization.objects.get(user_id=pk, organization=org)
        except UserOrganization.DoesNotExist:
            return Response({'error': 'User not found in this organization'}, status=status.HTTP_404_NOT_FOUND)

        user = membership.user
        user.is_active = False
        user.save()
        return Response({'message': 'User deactivated'})


class ResetPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org = getattr(request, 'organization', None)
        if not org or getattr(request, 'org_role', None) != 'owner':
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        try:
            membership = UserOrganization.objects.get(user_id=pk, organization=org)
        except UserOrganization.DoesNotExist:
            return Response({'error': 'User not found in this organization'}, status=status.HTTP_404_NOT_FOUND)

        new_password = request.data.get('new_password')
        if not new_password or len(new_password) < 8:
            return Response(
                {'error': 'new_password is required (min 8 characters)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        membership.user.set_password(new_password)
        membership.user.save()
        return Response({'message': 'Password reset successfully'})


class OrganizationListCreateView(APIView):
    """List user's orgs or create a new one."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orgs = get_user_orgs(request.user)
        return Response(orgs)

    def post(self, request):
        serializer = CreateOrgSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = serializer.save()
        # Creator becomes owner
        UserOrganization.objects.create(user=request.user, organization=org, role='owner')
        return Response(OrgSerializer(org).data, status=status.HTTP_201_CREATED)
