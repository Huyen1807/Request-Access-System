from rest_framework import serializers
from auditlog.models import LogEntry


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()
    action_display = serializers.SerializerMethodField()
    content_type_label = serializers.SerializerMethodField()

    class Meta:
        model = LogEntry
        fields = [
            'id',
            'content_type_label',
            'object_pk',
            'object_repr',
            'action',
            'action_display',
            'changes',
            'actor',
            'actor_email',
            'remote_addr',
            'timestamp',
        ]

    def get_actor_email(self, obj):
        if obj.actor:
            return obj.actor.email
        return None

    def get_action_display(self, obj):
        return obj.get_action_display()

    def get_content_type_label(self, obj):
        if obj.content_type:
            return f"{obj.content_type.app_label}.{obj.content_type.model}"
        return None
