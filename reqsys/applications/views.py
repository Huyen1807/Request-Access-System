from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model

from accounts.permissions import IsSubAdmin, IsDomainManager, IsSuperUser
from .models import Department, Domain, Application
from .serializers import (
    DepartmentSerializer,
    DomainSerializer,
    ApplicationSerializer,
    ApplicationAssignOwnerSerializer,
    DomainAssignSubAdminSerializer,
)

User = get_user_model()


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    CRUD Phòng ban (Department / PNL).
    Read: mọi user đã đăng nhập. Write: chỉ superuser.
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'code']
    ordering = ['name']

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsSuperUser()]


class DomainViewSet(viewsets.ModelViewSet):
    """
    CRUD Domain. Filter: ?department_id=<id>, ?mine=true
    Read: mọi user đã đăng nhập. Create: Sub-admin.
    Update/Delete: Sub-admin quản lý domain đó (IsDomainManager).
    """
    queryset = Domain.objects.select_related('department').prefetch_related('managers').all()
    serializer_class = DomainSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'department__name']
    ordering_fields = ['name', 'code']
    ordering = ['name']

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [IsAuthenticated()]
        if self.action == 'create':
            return [IsAuthenticated(), IsSubAdmin()]
        if self.action in ('assign_subadmin', 'remove_subadmin'):
            return [IsAuthenticated(), IsSubAdmin()]
        return [IsAuthenticated(), IsSubAdmin(), IsDomainManager()]

    def get_queryset(self):
        queryset = super().get_queryset()
        department_id = self.request.query_params.get('department_id')
        mine = self.request.query_params.get('mine')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        if mine is not None and mine.lower() == 'true':
            queryset = queryset.filter(managers=self.request.user)
        return queryset

    @action(detail=True, methods=['post'], url_path='assign-subadmin')
    def assign_subadmin(self, request, pk=None):
        """
        Gán sub-admin quản lý domain. Bất kỳ sub-admin nào cũng gọi được.
        POST /api/domains/{id}/assign-subadmin/
        Body: {"subadmin_id": <user_id>}
        """
        domain = self.get_object()
        serializer = DomainAssignSubAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subadmin = User.objects.get(pk=serializer.validated_data['subadmin_id'])
        domain.managers.add(subadmin)

        return Response(DomainSerializer(domain).data)

    @action(detail=True, methods=['post'], url_path='remove-subadmin')
    def remove_subadmin(self, request, pk=None):
        """
        Gỡ sub-admin khỏi domain.
        POST /api/domains/{id}/remove-subadmin/
        Body: {"subadmin_id": <user_id>}
        """
        domain = self.get_object()
        serializer = DomainAssignSubAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subadmin = User.objects.get(pk=serializer.validated_data['subadmin_id'])
        domain.managers.remove(subadmin)

        return Response(DomainSerializer(domain).data)


class ApplicationViewSet(viewsets.ModelViewSet):
    """
    CRUD Application. Filter: ?domain_id, ?owner_id, ?is_active
    Read: mọi user đã đăng nhập. Create: Sub-admin (domain phải do user quản lý, check ở serializer).
    Update/Delete/assign-owner/remove-owner: Sub-admin quản lý domain của Application đó.
    """
    queryset = Application.objects.select_related('domain', 'domain__department', 'owner').all()
    serializer_class = ApplicationSerializer

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'domain__name', 'domain__department__name']
    ordering_fields = ['name', 'code', 'domain__name']
    ordering = ['name']

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [IsAuthenticated()]
        if self.action == 'create':
            return [IsAuthenticated(), IsSubAdmin()]
        return [IsAuthenticated(), IsSubAdmin(), IsDomainManager()]

    def get_queryset(self):
        queryset = super().get_queryset()
        domain_id = self.request.query_params.get('domain_id')
        owner_id = self.request.query_params.get('owner_id')
        is_active = self.request.query_params.get('is_active')

        if domain_id:
            queryset = queryset.filter(domain_id=domain_id)
        if owner_id:
            queryset = queryset.filter(owner_id=owner_id)
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)

        return queryset

    @action(detail=True, methods=['patch'], url_path='assign-owner')
    def assign_owner(self, request, pk=None):
        """
        Gán owner cho application.
        PATCH /api/applications/{id}/assign-owner/
        Body: {"owner_id": <user_id>}
        User được gán phải có vai trò owner.
        """
        application = self.get_object()
        serializer = ApplicationAssignOwnerSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        owner_id = serializer.validated_data['owner_id']
        owner = User.objects.get(pk=owner_id)
        application.owner = owner
        application.save()

        return Response(
            ApplicationSerializer(application).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['patch'], url_path='remove-owner')
    def remove_owner(self, request, pk=None):
        """
        Gỡ owner khỏi application.
        PATCH /api/applications/{id}/remove-owner/
        """
        application = self.get_object()
        application.owner = None
        application.save()

        return Response(
            ApplicationSerializer(application).data,
            status=status.HTTP_200_OK
        )
