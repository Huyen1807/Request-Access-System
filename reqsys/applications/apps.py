from django.apps import AppConfig


class ApplicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'applications'

    def ready(self):
        import applications.signals  # noqa: F401
        from auditlog.registry import auditlog
        from .models import Department, Domain, Application

        auditlog.register(Department)
        auditlog.register(Domain)
        auditlog.register(Application)
