from django.db import models
from django.contrib.auth import get_user_model
from utils import PrefixedIdGenerator

User = get_user_model()


class Department(models.Model):
    """PNL trong tập đoàn"""
    id = models.CharField(primary_key=True, max_length=40, default=PrefixedIdGenerator('dept'), editable=False)
    name = models.CharField(max_length=255, unique=True, verbose_name="Tên phòng ban")
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã phòng ban")
    description = models.TextField(blank=True, verbose_name="Mô tả")

    class Meta:
        verbose_name = "PNL"
        verbose_name_plural = "PNL"
        ordering = ['name']

    def __str__(self):
        return f"[{self.code}] {self.name}"


class Domain(models.Model):
    """Domain thuộc một phòng ban"""
    id = models.CharField(primary_key=True, max_length=40, default=PrefixedIdGenerator('dom'), editable=False)
    name = models.CharField(max_length=255, verbose_name="Tên domain")
    code = models.CharField(max_length=50, unique=True, verbose_name="Mã domain")
    description = models.TextField(blank=True, verbose_name="Mô tả")
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='domains',
        verbose_name="Phòng ban"
    )

    class Meta:
        verbose_name = "Domain"
        verbose_name_plural = "Domain"
        ordering = ['department', 'name']
        unique_together = ('name', 'department')  # Không trùng tên trong cùng 1 PNL

    def __str__(self):
        return f"[{self.code}] {self.name} ({self.department.code})"


class Application(models.Model):
    """Ứng dụng thuộc một domain, được quản lý bởi một owner"""
    id = models.CharField(primary_key=True, max_length=40, default=PrefixedIdGenerator('app'), editable=False)
    name = models.CharField(max_length=255, verbose_name="Tên ứng dụng")
    code = models.CharField(max_length=100, verbose_name="Mã ứng dụng")
    description = models.TextField(blank=True, verbose_name="Mô tả")
    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        related_name='applications',
        verbose_name="Domain"
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_applications',
        verbose_name="Owner",
        limit_choices_to={'groups__name': 'owner'}
    )
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động")

    class Meta:
        verbose_name = "Ứng dụng"
        verbose_name_plural = "Ứng dụng"
        ordering = ['domain', 'name']
        unique_together = [('name', 'domain'), ('code', 'domain')]  # Không trùng tên và mã trong cùng domain

    def __str__(self):
        owner_str = self.owner.email if self.owner else "Chưa có owner"
        return f"[{self.code}] {self.name} - {self.domain.code} ({owner_str})"
