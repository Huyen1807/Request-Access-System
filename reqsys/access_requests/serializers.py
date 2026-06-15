from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from .models import AccessRequest, RequestItem
from applications.models import Application

User = get_user_model()

class RequesterSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']


class RequestItemSerializer(serializers.ModelSerializer):
    application_name = serializers.CharField(source='application.name', read_only=True)
    application_code = serializers.CharField(source='application.code', read_only=True)
    domain_name = serializers.CharField(source='application.domain.name', read_only=True)
    department_name = serializers.CharField(source='application.domain.department.name', read_only=True)

    class Meta:
        model = RequestItem
        fields = ['id', 'application', 'application_name', 'application_code', 'domain_name', 'department_name']


class AccessRequestListSerializer(serializers.ModelSerializer):
    requester_email = serializers.CharField(source='requester.email', read_only=True)
    item_count = serializers.SerializerMethodField()
    is_urgent = serializers.SerializerMethodField()

    class Meta:
        model = AccessRequest
        fields = ['id', 'requester', 'requester_email', 'status', 'created_at', 'deadline', 'item_count', 'is_urgent']

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
    items = RequestItemSerializer(many=True, read_only=True)
    is_urgent = serializers.SerializerMethodField()
    reviewed_by_email = serializers.CharField(source='reviewed_by.email', read_only=True)

    class Meta:
        model = AccessRequest
        fields = [
            'id', 'requester', 'requester_detail', 'status', 'reason', 'review_note',
            'reviewed_by', 'reviewed_by_email', 'created_at', 'reviewed_at', 'deadline',
            'is_urgent', 'items'
        ]

    def get_is_urgent(self, obj):
        if obj.deadline and obj.status in [AccessRequest.Status.PENDING_ADMIN, AccessRequest.Status.PENDING_OWNER]:
            time_remaining = obj.deadline - timezone.now()
            if timedelta(0) <= time_remaining <= timedelta(hours=24):
                return True
        return False


class AccessRequestCreateSerializer(serializers.ModelSerializer):
    application_ids = serializers.ListField(
        child=serializers.IntegerField(),
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
        return value

    def create(self, validated_data):
        application_ids = set(validated_data.pop('application_ids'))
        request_obj = AccessRequest.objects.create(**validated_data)
        
        # Create RequestItems
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
