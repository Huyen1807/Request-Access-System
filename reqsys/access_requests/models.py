from django.db import models
from django.contrib.auth import get_user_model
from applications.models import Application
from utils import PrefixedIdGenerator

User = get_user_model()


class AccessRequest(models.Model):
    """Yêu cầu cấp quyền truy cập ứng dụng từ Requester"""

    id = models.CharField(primary_key=True, max_length=40, default=PrefixedIdGenerator('req'), editable=False)

    class Status(models.TextChoices):
        PENDING_ADMIN = 'pending_admin', 'Chờ Sub-admin xử lý'
        PENDING_OWNER = 'pending_owner', 'Chờ Owner xử lý'
        REJECTED_BY_ADMIN = 'rejected_by_admin', 'Sub-admin từ chối'
        COMPLETED = 'completed', 'Đã hoàn thành'
        CANCELED = 'canceled', 'Đã hủy'

    requester = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='access_requests',
        verbose_name='Người yêu cầu',
        limit_choices_to={'groups__name': 'requester'},
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING_ADMIN,
        verbose_name='Trạng thái',
    )
    reason = models.TextField(
        blank=True,
        verbose_name='Lý do yêu cầu',
    )
    review_note = models.TextField(
        blank=True,
        verbose_name='Ghi chú xử lý (Sub-admin)',
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests',
        verbose_name='Sub-admin xử lý',
        limit_choices_to={'groups__name': 'sub-admin'},
    )
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Thời hạn xử lý',
    )
    dispute_reason = models.TextField(
        blank=True,
        verbose_name='Lý do khiếu nại',
    )
    disputed_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian khiếu nại')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian tạo')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian xử lý')

    class Meta:
        verbose_name = 'Yêu cầu cấp quyền'
        verbose_name_plural = 'Yêu cầu cấp quyền'
        ordering = ['-created_at']

    def __str__(self):
        return f"Request #{self.pk} - {self.requester.email} [{self.get_status_display()}]"


class OwnerBatch(models.Model):
    """Nhóm các RequestItem gửi cho cùng một Owner, có thể chứa items từ nhiều AccessRequest"""

    id = models.CharField(primary_key=True, max_length=40, default=PrefixedIdGenerator('batch'), editable=False)

    class Status(models.TextChoices):
        WAITING = 'waiting', 'Chờ gửi'
        SENT = 'sent', 'Đã gửi cho Owner'

    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_batches',
        verbose_name='Owner',
        limit_choices_to={'groups__name': 'owner'},
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
        verbose_name='Trạng thái',
    )
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian gửi')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian tạo')

    class Meta:
        verbose_name = 'Batch gửi Owner'
        verbose_name_plural = 'Batch gửi Owner'
        ordering = ['-created_at']

    def __str__(self):
        owner_str = self.owner.email if self.owner else 'Không có Owner'
        return f"Batch #{self.pk} → {owner_str} [{self.get_status_display()}]"


class RequestItem(models.Model):
    """Mỗi Application mà Requester yêu cầu cấp quyền trong một AccessRequest"""

    id = models.CharField(primary_key=True, max_length=40, default=PrefixedIdGenerator('item'), editable=False)

    class Status(models.TextChoices):
        WAITING_BATCH = 'waiting_batch', 'Chờ gửi batch'
        PENDING_OWNER = 'pending_owner', 'Chờ Owner xử lý'
        APPROVED = 'approved', 'Đã duyệt'
        REJECTED_BY_OWNER = 'rejected_by_owner', 'Owner từ chối'
        REJECTED_BY_ADMIN = 'rejected_by_admin', 'Sub-admin thu hồi'
        CANCELED = 'canceled', 'Đã hủy'

    access_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Yêu cầu',
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='request_items',
        verbose_name='Ứng dụng',
    )
    batch = models.ForeignKey(
        OwnerBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items',
        verbose_name='Batch',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING_BATCH,
        verbose_name='Trạng thái',
    )
    owner_note = models.TextField(
        blank=True,
        verbose_name='Ghi chú của Owner',
    )

    class Meta:
        verbose_name = 'Mục yêu cầu'
        verbose_name_plural = 'Mục yêu cầu'
        unique_together = ('access_request', 'application')

    def __str__(self):
        return f"Request #{self.access_request_id} → {self.application.code} [{self.get_status_display()}]"
