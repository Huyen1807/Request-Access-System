from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from . import signals  # noqa: F401
        from auditlog.registry import auditlog
        from .models import UserProfile

        auditlog.register(UserProfile)
