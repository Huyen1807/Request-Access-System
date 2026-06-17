from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model

from accounts.permissions import IsSubAdmin
from .models import Department, Domain, Application
from .serializers import (
    DepartmentSerializer,
    DomainSerializer,
    ApplicationSerializer,
    ApplicationAssignOwnerSerializer,
)

User = get_user_model()


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    CRUD Phòng ban (Department / PNL).
    Read: mọi user đã đăng nhập. Write: chỉ Sub-admin.
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
        return [IsAuthenticated(), IsSubAdmin()]


class DomainViewSet(viewsets.ModelViewSet):
    """
    CRUD Domain. Filter: ?department_id=<id>
    Read: mọi user đã đăng nhập. Write: chỉ Sub-admin.
    """
    queryset = Domain.objects.select_related('department').all()
    serializer_class = DomainSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'department__name']
    ordering_fields = ['name', 'code']
    ordering = ['name']

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsSubAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        department_id = self.request.query_params.get('department_id')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return queryset


class ApplicationViewSet(viewsets.ModelViewSet):
    """
    CRUD Application. Filter: ?domain_id, ?owner_id, ?is_active
    Read: mọi user đã đăng nhập. Write: chỉ Sub-admin.
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
        return [IsAuthenticated(), IsSubAdmin()]

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
        User được gán phải thuộc nhóm 'owner'.
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
