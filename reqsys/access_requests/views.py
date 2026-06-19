from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from .models import AccessRequest, RequestItem, OwnerBatch
from .serializers import (
    AccessRequestListSerializer,
    AccessRequestDetailSerializer,
    AccessRequestCreateSerializer,
    AccessRequestReviewSerializer,
    AccessRequestDisputeSerializer,
    OwnerBatchListSerializer,
    OwnerBatchDetailSerializer,
    RequestItemReviewSerializer,
)
from accounts.permissions import IsSubAdmin, IsRequester, IsOwner

User = get_user_model()


def _notify_requester_rejected(access_request):
    requester = access_request.requester
    send_mail(
        subject='[Request Access System] Yêu cầu của bạn đã bị từ chối',
        message=(
            f"Xin chào {requester.first_name} {requester.last_name},\n\n"
            f"Yêu cầu #{access_request.pk} của bạn đã bị Sub-admin từ chối.\n\n"
            f"Lý do: {access_request.review_note or 'Không có ghi chú.'}\n\n"
            f"Trân trọng,\nBan Quản trị"
        ),
        from_email=None,
        recipient_list=[requester.email],
        fail_silently=True,
    )


def _notify_revert(access_request, previous_status):
    requester = access_request.requester
    new_status_display = access_request.get_status_display()

    send_mail(
        subject='[Request Access System] Yêu cầu của bạn đã được cập nhật trạng thái',
        message=(
            f"Xin chào {requester.first_name} {requester.last_name},\n\n"
            f"Yêu cầu #{access_request.pk} của bạn đã được chuyển sang trạng thái: {new_status_display}.\n\n"
            f"Ghi chú: {access_request.review_note or 'Không có ghi chú.'}\n\n"
            f"Trân trọng,\nBan Quản trị"
        ),
        from_email=None,
        recipient_list=[requester.email],
        fail_silently=True,
    )

    if previous_status == AccessRequest.Status.PENDING_OWNER:
        owners = (
            User.objects
            .filter(
                received_batches__status=OwnerBatch.Status.SENT,
                received_batches__items__access_request=access_request,
            )
            .distinct()
        )
        for owner in owners:
            send_mail(
                subject='[Request Access System] Thông báo: Yêu cầu liên quan đến batch của bạn đã bị revert',
                message=(
                    f"Xin chào {owner.first_name} {owner.last_name},\n\n"
                    f"Yêu cầu #{access_request.pk} mà bạn đang xử lý đã được Sub-admin revert "
                    f"về trạng thái: {new_status_display}.\n\n"
                    f"Lý do: {access_request.review_note or 'Không có ghi chú.'}\n\n"
                    f"Vui lòng liên hệ Sub-admin để biết thêm chi tiết.\n\n"
                    f"Trân trọng,\nBan Quản trị"
                ),
                from_email=None,
                recipient_list=[owner.email],
                fail_silently=True,
            )


def _build_item_result_lines(access_request):
    items = access_request.items.select_related('application').all()
    lines = []
    for item in items:
        app = item.application
        if item.status == RequestItem.Status.APPROVED:
            lines.append(f"  ✔ {app.name} ({app.code}) — Đã duyệt")
        elif item.status == RequestItem.Status.REJECTED_BY_OWNER:
            reason = item.owner_note or 'Không có lý do'
            lines.append(f"  ✘ {app.name} ({app.code}) — Từ chối: {reason}")
        else:
            lines.append(f"  ⏳ {app.name} ({app.code}) — Đang xử lý")
    return '\n'.join(lines)


def _notify_requester_completion(access_request):
    requester = access_request.requester
    result_lines = _build_item_result_lines(access_request)
    send_mail(
        subject=f'[Request Access System] Yêu cầu #{access_request.pk} của bạn đã được xử lý xong',
        message=(
            f"Xin chào {requester.first_name} {requester.last_name},\n\n"
            f"Yêu cầu #{access_request.pk} của bạn đã được xử lý xong.\n\n"
            f"Kết quả chi tiết:\n{result_lines}\n\n"
            f"Trân trọng,\nBan Quản trị"
        ),
        from_email=None,
        recipient_list=[requester.email],
        fail_silently=True,
    )


def _notify_requester_completion_updated(access_request):
    requester = access_request.requester
    result_lines = _build_item_result_lines(access_request)
    send_mail(
        subject=f'[Request Access System] Kết quả yêu cầu #{access_request.pk} đã được cập nhật',
        message=(
            f"Xin chào {requester.first_name} {requester.last_name},\n\n"
            f"Kết quả yêu cầu #{access_request.pk} đã được Owner cập nhật.\n\n"
            f"Kết quả mới:\n{result_lines}\n\n"
            f"Trân trọng,\nBan Quản trị"
        ),
        from_email=None,
        recipient_list=[requester.email],
        fail_silently=True,
    )


def _check_request_completion(access_request):
    has_unfinished = access_request.items.filter(
        status__in=[RequestItem.Status.WAITING_BATCH, RequestItem.Status.PENDING_OWNER]
    ).exists()
    if not has_unfinished:
        access_request.status = AccessRequest.Status.COMPLETED
        access_request.reviewed_at = timezone.now()
        access_request.save(update_fields=['status', 'reviewed_at'])
        _notify_requester_completion(access_request)


class AccessRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """Quản lý các Access Request dành cho Sub-admin"""

    queryset = (
        AccessRequest.objects
        .select_related('requester', 'reviewed_by')
        .prefetch_related('items__application__domain__department', 'items__batch__owner')
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
            batch = OwnerBatch.objects.filter(
                owner=group['owner'],
                status=OwnerBatch.Status.WAITING,
            ).first()
            if batch is None:
                batch = OwnerBatch.objects.create(owner=group['owner'])
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

        # Cập nhật trạng thái của tất cả item bên trong
        access_request.items.update(status=RequestItem.Status.REJECTED_BY_ADMIN, batch=None)

        _notify_requester_rejected(access_request)

        return Response(AccessRequestDetailSerializer(access_request).data)

    @action(detail=True, methods=['patch'], serializer_class=AccessRequestReviewSerializer)
    def revert(self, request, pk=None):
        access_request = self.get_object()
        serializer = self.get_serializer(access_request, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        revert_note = serializer.validated_data.get('review_note', '').strip()
        if not revert_note:
            return Response(
                {"detail": "Phải cung cấp lý do khi revert request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_status = access_request.status

        if access_request.status == AccessRequest.Status.PENDING_OWNER:
            access_request.status = AccessRequest.Status.REJECTED_BY_ADMIN
        elif access_request.status == AccessRequest.Status.REJECTED_BY_ADMIN:
            access_request.status = AccessRequest.Status.PENDING_OWNER
        else:
            return Response(
                {"detail": "Chỉ có thể revert các request đang ở trạng thái pending_owner hoặc rejected_by_admin."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if access_request.review_note:
            access_request.review_note += f"\n\n[REVERT] {revert_note}"
        else:
            access_request.review_note = f"[REVERT] {revert_note}"
        access_request.save()

        if previous_status == AccessRequest.Status.PENDING_OWNER:
            # Thu hồi toàn bộ items (kể cả đã được owner duyệt/từ chối)
            access_request.items.exclude(
                status=RequestItem.Status.REJECTED_BY_ADMIN
            ).update(status=RequestItem.Status.REJECTED_BY_ADMIN, batch=None)
        else:
            # Khôi phục items bị thu hồi về WAITING_BATCH và re-batch theo owner
            revoked_items = list(
                access_request.items
                .filter(status=RequestItem.Status.REJECTED_BY_ADMIN)
                .select_related('application__owner')
            )
            owner_groups = {}
            for item in revoked_items:
                owner = item.application.owner
                key = owner.id if owner else None
                if key not in owner_groups:
                    owner_groups[key] = {'owner': owner, 'items': []}
                owner_groups[key]['items'].append(item)

            for group in owner_groups.values():
                batch = OwnerBatch.objects.filter(
                    owner=group['owner'],
                    status=OwnerBatch.Status.WAITING,
                ).first()
                if batch is None:
                    batch = OwnerBatch.objects.create(owner=group['owner'])
                for item in group['items']:
                    item.batch = batch
                    item.status = RequestItem.Status.WAITING_BATCH
                RequestItem.objects.bulk_update(group['items'], ['batch', 'status'])

        _notify_revert(access_request, previous_status)

        return Response(AccessRequestDetailSerializer(access_request).data)

    @action(detail=True, methods=['post'])
    def remind_owner(self, request, pk=None):
        access_request = self.get_object()

        if access_request.status != AccessRequest.Status.PENDING_OWNER:
            return Response(
                {"detail": "Chỉ có thể giục Owner khi request ở trạng thái pending_owner."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        owners = (
            User.objects
            .filter(
                received_batches__items__access_request=access_request,
                received_batches__items__status=RequestItem.Status.PENDING_OWNER,
            )
            .distinct()
        )

        if not owners.exists():
            return Response(
                {"detail": "Không có Owner nào đang chờ xử lý item của request này."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _notify_owners_reminder(access_request, owners)

        return Response({"detail": "Đã gửi email nhắc nhở đến Owner."})


class SubAdminBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Quản lý Batch dành cho Sub-admin: xem và gửi batch cho Owner"""

    permission_classes = [IsAuthenticated, IsSubAdmin]

    def get_queryset(self):
        return (
            OwnerBatch.objects
            .select_related('owner')
            .prefetch_related('items__application__domain__department', 'items__access_request')
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
            .select_related('owner')
            .prefetch_related('items__application__domain__department', 'items__access_request__requester')
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

        _check_request_completion(item.access_request)

        return Response({"detail": "Đã duyệt item.", "item_id": item.id, "status": item.status})

    @action(detail=True, methods=['patch'], serializer_class=RequestItemReviewSerializer)
    def reject_item(self, request, pk=None):
        batch = self.get_object()
        serializer = RequestItemReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item_id = serializer.validated_data['item_id']
        owner_note = serializer.validated_data['owner_note'].strip()

        if not owner_note:
            return Response(
                {"detail": "Phải cung cấp lý do khi từ chối item."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            item = batch.items.get(id=item_id, status=RequestItem.Status.PENDING_OWNER)
        except RequestItem.DoesNotExist:
            return Response(
                {"detail": "Item không tồn tại trong batch này hoặc không ở trạng thái pending_owner."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item.status = RequestItem.Status.REJECTED_BY_OWNER
        item.owner_note = owner_note
        item.save()

        _check_request_completion(item.access_request)

        return Response({"detail": "Đã từ chối item.", "item_id": item.id, "status": item.status})

    @action(detail=True, methods=['patch'], serializer_class=RequestItemReviewSerializer)
    def revert_item(self, request, pk=None):
        batch = self.get_object()
        serializer = RequestItemReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item_id = serializer.validated_data['item_id']

        try:
            item = batch.items.select_related('access_request').get(
                id=item_id,
                status__in=[RequestItem.Status.APPROVED, RequestItem.Status.REJECTED_BY_OWNER],
            )
        except RequestItem.DoesNotExist:
            return Response(
                {"detail": "Item không tồn tại trong batch này hoặc không ở trạng thái approved/rejected_by_owner."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        access_request = item.access_request
        was_completed = access_request.status == AccessRequest.Status.COMPLETED

        item.status = RequestItem.Status.PENDING_OWNER
        item.owner_note = ''
        item.save()

        if was_completed:
            access_request.status = AccessRequest.Status.PENDING_OWNER
            access_request.reviewed_at = None
            access_request.save(update_fields=['status', 'reviewed_at'])
            _notify_requester_completion_updated(access_request)

        return Response({"detail": "Đã revert item.", "item_id": item.id, "status": item.status})


def _notify_owners_revoke_access(access_request, approved_items):
    owner_groups = {}
    for item in approved_items:
        owner = item.application.owner
        if owner is None:
            continue
        if owner.id not in owner_groups:
            owner_groups[owner.id] = {'owner': owner, 'items': []}
        owner_groups[owner.id]['items'].append(item)

    requester = access_request.requester
    for group in owner_groups.values():
        owner = group['owner']
        app_list = '\n'.join(
            f"  - {item.application.name} ({item.application.code})"
            for item in group['items']
        )
        send_mail(
            subject=f'[Request Access System] Thu hồi quyền truy cập - Yêu cầu #{access_request.pk}',
            message=(
                f"Xin chào {owner.first_name} {owner.last_name},\n\n"
                f"Requester {requester.first_name} {requester.last_name} ({requester.email}) "
                f"đã hủy yêu cầu cấp quyền #{access_request.pk}.\n\n"
                f"Vui lòng thu hồi quyền truy cập của các ứng dụng sau:\n"
                f"{app_list}\n\n"
                f"Trân trọng,\nHệ thống Request Access System"
            ),
            from_email=None,
            recipient_list=[owner.email],
            fail_silently=True,
        )


def _notify_subadmin_reminder(access_request):
    requester = access_request.requester
    sub_admins = User.objects.filter(groups__name='sub-admin', is_active=True)
    for sub_admin in sub_admins:
        send_mail(
            subject=f'[Request Access System] Nhắc nhở: Yêu cầu #{access_request.pk} cần được xử lý',
            message=(
                f"Xin chào {sub_admin.first_name} {sub_admin.last_name},\n\n"
                f"Requester {requester.first_name} {requester.last_name} ({requester.email}) "
                f"đã giục xử lý yêu cầu #{access_request.pk} đang chờ Sub-admin duyệt.\n\n"
                f"Vui lòng đăng nhập hệ thống để xem xét yêu cầu này.\n\n"
                f"Trân trọng,\nHệ thống Request Access System"
            ),
            from_email=None,
            recipient_list=[sub_admin.email],
            fail_silently=True,
        )


def _notify_owners_reminder(access_request, owners):
    requester = access_request.requester
    for owner in owners:
        send_mail(
            subject=f'[Request Access System] Nhắc nhở: Yêu cầu #{access_request.pk} cần được xử lý',
            message=(
                f"Xin chào {owner.first_name} {owner.last_name},\n\n"
                f"Sub-admin đã giục bạn xử lý các item đang chờ duyệt thuộc yêu cầu #{access_request.pk} "
                f"(người yêu cầu: {requester.first_name} {requester.last_name} - {requester.email}).\n\n"
                f"Vui lòng đăng nhập hệ thống để xem xét các item này.\n\n"
                f"Trân trọng,\nHệ thống Request Access System"
            ),
            from_email=None,
            recipient_list=[owner.email],
            fail_silently=True,
        )


def _notify_subadmin_dispute(access_request):
    if not access_request.reviewed_by:
        return

    requester = access_request.requester
    send_mail(
        subject=f'[Request Access System] Khiếu nại yêu cầu #{access_request.pk}',
        message=(
            f"Xin chào {access_request.reviewed_by.first_name} {access_request.reviewed_by.last_name},\n\n"
            f"Requester đã khiếu nại quyết định từ chối của bạn.\n\n"
            f"Thông tin yêu cầu:\n"
            f"- ID: {access_request.pk}\n"
            f"- Người yêu cầu: {requester.first_name} {requester.last_name} ({requester.email})\n"
            f"- Ghi chú từ chối trước đó: {access_request.review_note or 'Không có'}\n\n"
            f"Lý do khiếu nại:\n{access_request.dispute_reason}\n\n"
            f"Vui lòng đăng nhập hệ thống để xem xét lại yêu cầu này.\n\n"
            f"Trân trọng,\nHệ thống Request Access System"
        ),
        from_email=None,
        recipient_list=[access_request.reviewed_by.email],
        fail_silently=True,
    )


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

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        access_request = self.get_object()

        non_cancellable = [AccessRequest.Status.CANCELED, AccessRequest.Status.REJECTED_BY_ADMIN]
        if access_request.status in non_cancellable:
            return Response(
                {"detail": "Không thể hủy yêu cầu ở trạng thái hiện tại."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        approved_items = list(
            access_request.items
            .filter(status=RequestItem.Status.APPROVED)
            .select_related('application__owner')
        )

        if approved_items:
            _notify_owners_revoke_access(access_request, approved_items)

        access_request.items.update(status=RequestItem.Status.CANCELED, batch=None)
        access_request.status = AccessRequest.Status.CANCELED
        access_request.save(update_fields=['status'])

        access_request.refresh_from_db()
        return Response(AccessRequestDetailSerializer(access_request).data)

    @action(detail=True, methods=['post'])
    def remind(self, request, pk=None):
        access_request = self.get_object()

        non_remindable = [
            AccessRequest.Status.COMPLETED,
            AccessRequest.Status.CANCELED,
            AccessRequest.Status.REJECTED_BY_ADMIN,
        ]
        if access_request.status in non_remindable:
            return Response(
                {"detail": "Không thể giục Sub-admin khi request đã được xử lý xong, hủy hoặc bị từ chối."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _notify_subadmin_reminder(access_request)

        return Response({"detail": "Đã gửi email nhắc nhở đến Sub-admin."})

    @action(detail=True, methods=['post'], serializer_class=AccessRequestDisputeSerializer)
    def dispute(self, request, pk=None):
        access_request = self.get_object()

        if access_request.status != AccessRequest.Status.REJECTED_BY_ADMIN:
            return Response(
                {"detail": "Chỉ có thể khiếu nại yêu cầu đang ở trạng thái bị từ chối bởi Sub-admin."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(access_request, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        access_request.dispute_reason = serializer.validated_data['dispute_reason']
        access_request.disputed_at = timezone.now()
        access_request.status = AccessRequest.Status.PENDING_ADMIN
        access_request.save(update_fields=['dispute_reason', 'disputed_at', 'status'])

        _notify_subadmin_dispute(access_request)

        return Response(AccessRequestDetailSerializer(access_request).data)
