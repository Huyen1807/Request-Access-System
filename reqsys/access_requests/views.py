from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import AccessRequest, RequestItem, OwnerBatch
from .serializers import (
    AccessRequestListSerializer,
    AccessRequestDetailSerializer,
    AccessRequestCreateSerializer,
    AccessRequestReviewSerializer,
    OwnerBatchListSerializer,
    OwnerBatchDetailSerializer,
    RequestItemReviewSerializer,
)
from accounts.permissions import IsSubAdmin, IsRequester, IsOwner


def _check_request_completion(access_request):
    """Mark AccessRequest as completed when all items are processed by owners."""
    has_unfinished = access_request.items.filter(
        status__in=[RequestItem.Status.WAITING_BATCH, RequestItem.Status.PENDING_OWNER]
    ).exists()
    if not has_unfinished:
        access_request.status = AccessRequest.Status.COMPLETED
        access_request.save(update_fields=['status'])


class AccessRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """Quản lý các Access Request dành cho Sub-admin"""

    queryset = (
        AccessRequest.objects
        .select_related('requester', 'reviewed_by')
        .prefetch_related('items__application__domain__department', 'batches__owner')
        .all()
    )
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

        if access_request.status != AccessRequest.Status.PENDING_ADMIN:
            return Response(
                {"detail": "Chỉ có thể duyệt request ở trạng thái pending_admin."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(access_request, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        access_request.status = AccessRequest.Status.PENDING_OWNER
        access_request.review_note = serializer.validated_data.get('review_note', access_request.review_note)
        access_request.reviewed_by = request.user
        access_request.reviewed_at = timezone.now()
        access_request.save()

        # Group items by owner and create batches
        items = list(
            access_request.items
            .select_related('application__owner')
            .all()
        )
        owner_groups = {}
        for item in items:
            owner = item.application.owner
            key = owner.id if owner else None
            if key not in owner_groups:
                owner_groups[key] = {'owner': owner, 'items': []}
            owner_groups[key]['items'].append(item)

        for group in owner_groups.values():
            batch = OwnerBatch.objects.create(
                access_request=access_request,
                owner=group['owner'],
            )
            for item in group['items']:
                item.batch = batch
                item.status = RequestItem.Status.WAITING_BATCH
            RequestItem.objects.bulk_update(group['items'], ['batch', 'status'])

        access_request.refresh_from_db()
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
                status=status.HTTP_400_BAD_REQUEST,
            )

        access_request.save()
        return Response(AccessRequestDetailSerializer(access_request).data)


class SubAdminBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Quản lý Batch dành cho Sub-admin: xem và gửi batch cho Owner"""

    permission_classes = [IsAuthenticated, IsSubAdmin]

    def get_queryset(self):
        return (
            OwnerBatch.objects
            .select_related('owner', 'access_request')
            .prefetch_related('items__application__domain__department')
            .all()
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return OwnerBatchListSerializer
        return OwnerBatchDetailSerializer

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        batch = self.get_object()

        if batch.status != OwnerBatch.Status.WAITING:
            return Response(
                {"detail": "Batch này đã được gửi rồi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if batch.access_request.status != AccessRequest.Status.PENDING_OWNER:
            return Response(
                {"detail": "Request liên quan không ở trạng thái pending_owner."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch.status = OwnerBatch.Status.SENT
        batch.sent_at = timezone.now()
        batch.save()

        batch.items.update(status=RequestItem.Status.PENDING_OWNER)

        batch.refresh_from_db()
        return Response(OwnerBatchDetailSerializer(batch).data)


class OwnerBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Quản lý Batch dành cho Owner: xem và xử lý các item được giao"""

    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        return (
            OwnerBatch.objects
            .filter(owner=self.request.user, status=OwnerBatch.Status.SENT)
            .select_related('access_request__requester')
            .prefetch_related('items__application__domain__department')
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return OwnerBatchListSerializer
        return OwnerBatchDetailSerializer

    @action(detail=True, methods=['patch'], serializer_class=RequestItemReviewSerializer)
    def approve_item(self, request, pk=None):
        batch = self.get_object()
        serializer = RequestItemReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item_id = serializer.validated_data['item_id']
        owner_note = serializer.validated_data['owner_note']

        try:
            item = batch.items.get(id=item_id, status=RequestItem.Status.PENDING_OWNER)
        except RequestItem.DoesNotExist:
            return Response(
                {"detail": "Item không tồn tại trong batch này hoặc không ở trạng thái pending_owner."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item.status = RequestItem.Status.APPROVED
        item.owner_note = owner_note
        item.save()

        _check_request_completion(batch.access_request)

        return Response({"detail": "Đã duyệt item.", "item_id": item.id, "status": item.status})

    @action(detail=True, methods=['patch'], serializer_class=RequestItemReviewSerializer)
    def reject_item(self, request, pk=None):
        batch = self.get_object()
        serializer = RequestItemReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item_id = serializer.validated_data['item_id']
        owner_note = serializer.validated_data['owner_note']

        try:
            item = batch.items.get(id=item_id, status=RequestItem.Status.PENDING_OWNER)
        except RequestItem.DoesNotExist:
            return Response(
                {"detail": "Item không tồn tại trong batch này hoặc không ở trạng thái pending_owner."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item.status = RequestItem.Status.REJECTED
        item.owner_note = owner_note
        item.save()

        _check_request_completion(batch.access_request)

        return Response({"detail": "Đã từ chối item.", "item_id": item.id, "status": item.status})


class RequesterAccessRequestViewSet(viewsets.ModelViewSet):
    """Quản lý các Access Request của chính Requester (chỉ List, Retrieve, Create)"""

    permission_classes = [IsAuthenticated, IsRequester]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'deadline', 'status']
    ordering = ['-created_at']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return (
            AccessRequest.objects
            .select_related('requester', 'reviewed_by')
            .prefetch_related('items__application__domain__department')
            .filter(requester=self.request.user)
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return AccessRequestCreateSerializer
        elif self.action == 'list':
            return AccessRequestListSerializer
        return AccessRequestDetailSerializer

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)
