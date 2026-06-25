from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django.contrib.contenttypes.models import ContentType
from auditlog.models import LogEntry

from accounts.permissions import IsSubAdmin
from .audit_serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Xem lịch sử audit log. Chỉ dành cho Sub-admin.

    Hỗ trợ filter:
      - ?model=applications.domain          → lọc theo loại model (app_label.model_name)
      - ?object_id=<pk>                     → lọc theo ID của object cụ thể
      - ?action=0|1|2                       → 0=CREATE, 1=UPDATE, 2=DELETE
      - ?actor_id=<user_pk>                 → lọc theo người thực hiện
      - ?search=<keyword>                   → tìm trong object_repr và actor email
      - ?ordering=timestamp|-timestamp      → sắp xếp
    """

    permission_classes = [IsAuthenticated, IsSubAdmin]
    serializer_class = AuditLogSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['object_repr', 'actor__email']
    ordering_fields = ['timestamp', 'action']
    ordering = ['-timestamp']

    def get_queryset(self):
        qs = (
            LogEntry.objects
            .select_related('content_type', 'actor')
            .all()
        )

        # Filter by model (e.g., ?model=applications.domain)
        model_param = self.request.query_params.get('model')
        if model_param:
            try:
                app_label, model_name = model_param.lower().split('.')
                ct = ContentType.objects.get(app_label=app_label, model=model_name)
                qs = qs.filter(content_type=ct)
            except (ValueError, ContentType.DoesNotExist):
                return qs.none()

        # Filter by specific object
        object_id = self.request.query_params.get('object_id')
        if object_id:
            qs = qs.filter(object_pk=str(object_id))

        # Filter by action: 0=CREATE, 1=UPDATE, 2=DELETE
        action = self.request.query_params.get('action')
        if action is not None:
            qs = qs.filter(action=action)

        # Filter by actor
        actor_id = self.request.query_params.get('actor_id')
        if actor_id:
            qs = qs.filter(actor_id=actor_id)

        return qs
