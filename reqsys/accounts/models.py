from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        primary_key=True,
    )
    is_subadmin = models.BooleanField(default=False, verbose_name="Sub-admin")
    is_owner = models.BooleanField(default=False, verbose_name="Owner")

    def __str__(self):
        return f"Profile({self.user.email})"
