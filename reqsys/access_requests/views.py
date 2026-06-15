from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import AccessRequest
from .serializers import (
    AccessRequestListSerializer,
    AccessRequestDetailSerializer,
    AccessRequestCreateSerializer,
    AccessRequestReviewSerializer
)
from accounts.permissions import IsSubAdmin, IsRequester

class AccessRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Quản lý các Access Request dành cho Sub-admin
    """
    queryset = AccessRequest.objects.select_related('requester', 'reviewed_by').prefetch_related('items__application__domain__department').all()
    permission_classes = [IsAuthenticated, IsSubAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['requester__email']
    ordering_fields = ['created_at', 'deadline', 'status']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return AccessRequestListSerializer
        return AccessRequestDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset

    @action(detail=True, methods=['patch'], serializer_class=AccessRequestReviewSerializer)
    def approve(self, request, pk=None):
        access_request = self.get_object()
        serializer = self.get_serializer(access_request, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        access_request.status = AccessRequest.Status.PENDING_OWNER
        access_request.review_note = serializer.validated_data.get('review_note', access_request.review_note)
        access_request.reviewed_by = request.user
        access_request.reviewed_at = timezone.now()
        access_request.save()
        
        return Response(AccessRequestDetailSerializer(access_request).data)

    @action(detail=True, methods=['patch'], serializer_class=AccessRequestReviewSerializer)
    def reject(self, request, pk=None):
        access_request = self.get_object()
        serializer = self.get_serializer(access_request, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        access_request.status = AccessRequest.Status.REJECTED_BY_ADMIN
        access_request.review_note = serializer.validated_data.get('review_note', access_request.review_note)
        access_request.reviewed_by = request.user
        access_request.reviewed_at = timezone.now()
        access_request.save()
        
        return Response(AccessRequestDetailSerializer(access_request).data)

    @action(detail=True, methods=['patch'])
    def revert(self, request, pk=None):
        access_request = self.get_object()
        
        if access_request.status == AccessRequest.Status.PENDING_OWNER:
            access_request.status = AccessRequest.Status.REJECTED_BY_ADMIN
        elif access_request.status == AccessRequest.Status.REJECTED_BY_ADMIN:
            access_request.status = AccessRequest.Status.PENDING_OWNER
        else:
            return Response(
                {"detail": "Chỉ có thể revert các request đang ở trạng thái pending_owner hoặc rejected_by_admin."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        access_request.save()
        
        return Response(AccessRequestDetailSerializer(access_request).data)


class RequesterAccessRequestViewSet(viewsets.ModelViewSet):
    """
    Quản lý các Access Request của chính Requester (chỉ List, Retrieve, Create)
    """
    permission_classes = [IsAuthenticated, IsRequester]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'deadline', 'status']
    ordering = ['-created_at']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return AccessRequest.objects.select_related('requester', 'reviewed_by').prefetch_related('items__application__domain__department').filter(requester=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return AccessRequestCreateSerializer
        elif self.action == 'list':
            return AccessRequestListSerializer
        return AccessRequestDetailSerializer

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)
