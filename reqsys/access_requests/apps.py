from django.apps import AppConfig


class AccessRequestsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'access_requests'

    def ready(self):
        from auditlog.registry import auditlog
        from .models import AccessRequest, RequestItem, OwnerBatch

        auditlog.register(AccessRequest)
        auditlog.register(RequestItem)
        auditlog.register(OwnerBatch)
