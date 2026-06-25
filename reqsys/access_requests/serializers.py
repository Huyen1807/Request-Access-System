from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from .models import AccessRequest, RequestItem, OwnerBatch
from applications.models import Application

User = get_user_model()


class RequesterSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']


class OwnerSimpleSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'name']

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class RequestItemSerializer(serializers.ModelSerializer):
    application_name = serializers.CharField(source='application.name', read_only=True)
    application_code = serializers.CharField(source='application.code', read_only=True)
    owner_email = serializers.SerializerMethodField()
    access_request_id = serializers.CharField(source='access_request.id', read_only=True)

    class Meta:
        model = RequestItem
        fields = [
            'id', 'access_request_id', 'application', 'application_name', 'application_code',
            'owner_email', 'status', 'owner_note',
        ]

    def get_owner_email(self, obj):
        return obj.application.owner.email if obj.application.owner else None


class OwnerBatchListSerializer(serializers.ModelSerializer):
    owner_email = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = OwnerBatch
        fields = ['id', 'owner', 'owner_email', 'owner_name', 'status', 'item_count', 'sent_at', 'created_at']

    def get_owner_email(self, obj):
        return obj.owner.email if obj.owner else None

    def get_owner_name(self, obj):
        return f"{obj.owner.first_name} {obj.owner.last_name}".strip() if obj.owner else None

    def get_item_count(self, obj):
        return obj.items.count()


class OwnerBatchDetailSerializer(serializers.ModelSerializer):
    owner_detail = OwnerSimpleSerializer(source='owner', read_only=True)
    items = RequestItemSerializer(many=True, read_only=True)

    class Meta:
        model = OwnerBatch
        fields = ['id', 'owner', 'owner_detail', 'status', 'items', 'sent_at', 'created_at']


class AccessRequestListSerializer(serializers.ModelSerializer):
    requester_email = serializers.CharField(source='requester.email', read_only=True)
    requester_name = serializers.SerializerMethodField()
    domain_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    items = RequestItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()
    is_urgent = serializers.SerializerMethodField()

    class Meta:
        model = AccessRequest
        fields = ['id', 'requester', 'requester_email', 'requester_name', 'department_name', 'domain_name', 'status', 'created_at', 'deadline', 'item_count', 'is_urgent', 'items', 'reviewed_at']

    def get_requester_name(self, obj):
        return f"{obj.requester.first_name} {obj.requester.last_name}".strip()

    def get_domain_name(self, obj):
        domains = []
        for item in obj.items.all():
            if item.application and item.application.domain:
                domain = item.application.domain.name
                if domain not in domains:
                    domains.append(domain)
        return ", ".join(domains)

    def get_department_name(self, obj):
        departments = []
        for item in obj.items.all():
            if item.application and item.application.domain and item.application.domain.department:
                dept = item.application.domain.department.name
                if dept not in departments:
                    departments.append(dept)
        return ", ".join(departments)

    def get_item_count(self, obj):
        return obj.items.count()

    def get_is_urgent(self, obj):
        if obj.deadline and obj.status in [AccessRequest.Status.PENDING_ADMIN, AccessRequest.Status.PENDING_OWNER]:
            time_remaining = obj.deadline - timezone.now()
            if timedelta(0) <= time_remaining <= timedelta(hours=24):
                return True
        return False


class AccessRequestDetailSerializer(serializers.ModelSerializer):
    requester_detail = RequesterSimpleSerializer(source='requester', read_only=True)
    domain_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    items = RequestItemSerializer(many=True, read_only=True)
    batches = serializers.SerializerMethodField()
    is_urgent = serializers.SerializerMethodField()
    reviewed_by_email = serializers.CharField(source='reviewed_by.email', read_only=True)

    class Meta:
        model = AccessRequest
        fields = [
            'id', 'requester', 'requester_detail', 'department_name', 'domain_name', 'status', 'reason', 'review_note',
            'reviewed_by', 'reviewed_by_email', 'created_at', 'reviewed_at', 'deadline',
            'is_urgent', 'dispute_reason', 'disputed_at', 'items', 'batches',
        ]

    def get_batches(self, obj):
        batch_ids = obj.items.exclude(batch=None).values_list('batch_id', flat=True).distinct()
        batches = OwnerBatch.objects.filter(id__in=batch_ids).select_related('owner')
        return OwnerBatchListSerializer(batches, many=True).data

    def get_is_urgent(self, obj):
        if obj.deadline and obj.status in [AccessRequest.Status.PENDING_ADMIN, AccessRequest.Status.PENDING_OWNER]:
            time_remaining = obj.deadline - timezone.now()
            if timedelta(0) <= time_remaining <= timedelta(hours=24):
                return True
        return False

    def get_domain_name(self, obj):
        domains = []
        for item in obj.items.all():
            if item.application and item.application.domain:
                domain = item.application.domain.name
                if domain not in domains:
                    domains.append(domain)
        return ", ".join(domains)

    def get_department_name(self, obj):
        departments = []
        for item in obj.items.all():
            if item.application and item.application.domain and item.application.domain.department:
                dept = item.application.domain.department.name
                if dept not in departments:
                    departments.append(dept)
        return ", ".join(departments)


class AccessRequestCreateSerializer(serializers.ModelSerializer):
    application_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        allow_empty=False
    )

    class Meta:
        model = AccessRequest
        fields = ['id', 'reason', 'deadline', 'application_ids']

    def validate_application_ids(self, value):
        applications = Application.objects.filter(id__in=value)
        if applications.count() != len(set(value)):
            raise serializers.ValidationError("Một số Application ID không hợp lệ hoặc không tồn tại.")
        
        # Kiểm tra tất cả ứng dụng phải thuộc cùng 1 domain
        domains = {app.domain_id for app in applications}
        if len(domains) > 1:
            raise serializers.ValidationError("Tất cả các ứng dụng trong một yêu cầu phải thuộc cùng một domain.")
            
        return list(set(value))

    def create(self, validated_data):
        application_ids = set(validated_data.pop('application_ids'))
        request_obj = AccessRequest.objects.create(**validated_data)

        items = [
            RequestItem(access_request=request_obj, application_id=app_id)
            for app_id in application_ids
        ]
        RequestItem.objects.bulk_create(items)

        return request_obj


class AccessRequestReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessRequest
        fields = ['review_note']


class AccessRequestRevertSerializer(serializers.Serializer):
    revert_note = serializers.CharField(
        required=True, 
        allow_blank=False, 
        error_messages={'blank': 'Phải cung cấp lý do khi revert request.', 'required': 'Phải cung cấp lý do khi revert request.'}
    )


class AccessRequestDisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessRequest
        fields = ['dispute_reason']

    def validate_dispute_reason(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Phải cung cấp lý do khiếu nại.")
        return value.strip()


class RequestItemReviewSerializer(serializers.Serializer):
    item_id = serializers.CharField()
    owner_note = serializers.CharField(required=False, allow_blank=True, default='')
