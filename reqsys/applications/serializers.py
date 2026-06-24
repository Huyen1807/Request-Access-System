from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Department, Domain, Application

User = get_user_model()


class DepartmentSerializer(serializers.ModelSerializer):
    domain_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'description', 'domain_count']

    def get_domain_count(self, obj):
        return obj.domains.count()


class DomainManagerSerializer(serializers.ModelSerializer):
    """Serializer đơn giản hiển thị thông tin sub-admin quản lý domain"""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']


class DomainSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    application_count = serializers.SerializerMethodField(read_only=True)
    managers = DomainManagerSerializer(many=True, read_only=True)

    class Meta:
        model = Domain
        fields = ['id', 'name', 'code', 'description', 'department', 'department_name', 'department_code', 'application_count', 'managers']
        extra_kwargs = {
            'department': {'write_only': False}
        }

    def get_application_count(self, obj):
        return obj.applications.count()

    def validate(self, attrs):
        # Kiểm tra unique_together khi create/update
        department = attrs.get('department', getattr(self.instance, 'department', None))
        name = attrs.get('name', getattr(self.instance, 'name', None))

        qs = Domain.objects.filter(name=name, department=department)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"name": f"Domain tên '{name}' đã tồn tại trong phòng ban này."}
            )
        return attrs


class ApplicationOwnerSerializer(serializers.ModelSerializer):
    """Serializer đơn giản hiển thị thông tin owner"""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']


class ApplicationSerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source='domain.name', read_only=True)
    domain_code = serializers.CharField(source='domain.code', read_only=True)
    department_name = serializers.CharField(source='domain.department.name', read_only=True)
    owner_detail = ApplicationOwnerSerializer(source='owner', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'name', 'code', 'description',
            'domain', 'domain_name', 'domain_code', 'department_name',
            'owner', 'owner_detail',
            'is_active'
        ]
        extra_kwargs = {
            'owner': {'required': False, 'allow_null': True}
        }

    def validate(self, attrs):
        # Kiểm tra unique_together khi create/update
        domain = attrs.get('domain', getattr(self.instance, 'domain', None))
        name = attrs.get('name', getattr(self.instance, 'name', None))
        code = attrs.get('code', getattr(self.instance, 'code', None))

        if name:
            qs_name = Application.objects.filter(name=name, domain=domain)
            if self.instance:
                qs_name = qs_name.exclude(pk=self.instance.pk)
            if qs_name.exists():
                raise serializers.ValidationError(
                    {"name": f"Ứng dụng tên '{name}' đã tồn tại trong domain này."}
                )

        if code:
            qs_code = Application.objects.filter(code=code, domain=domain)
            if self.instance:
                qs_code = qs_code.exclude(pk=self.instance.pk)
            if qs_code.exists():
                raise serializers.ValidationError(
                    {"code": f"Ứng dụng mã '{code}' đã tồn tại trong domain này."}
                )

        if self.instance is None:
            request = self.context.get('request')
            if request is not None and domain is not None:
                if not domain.managers.filter(pk=request.user.pk).exists():
                    raise serializers.ValidationError(
                        {"domain": "Bạn không quản lý domain này."}
                    )

        return attrs


class ApplicationAssignOwnerSerializer(serializers.Serializer):
    """Serializer dùng riêng để gán owner cho Application"""
    owner_id = serializers.IntegerField()  # User vẫn dùng integer ID (Django built-in)

    def validate_owner_id(self, value):
        try:
            user = User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Không tìm thấy user với ID này.")

        if not getattr(user.profile, 'is_owner', False):
            raise serializers.ValidationError(
                "User này không có vai trò 'owner'. Chỉ có thể gán owner cho user có vai trò owner."
            )
        return value


class DomainAssignSubAdminSerializer(serializers.Serializer):
    """Serializer dùng riêng để gán sub-admin quản lý domain"""
    subadmin_id = serializers.IntegerField()

    def validate_subadmin_id(self, value):
        try:
            user = User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Không tìm thấy user với ID này.")

        if not getattr(user.profile, 'is_subadmin', False):
            raise serializers.ValidationError(
                "User này không có vai trò 'sub-admin'. Chỉ có thể gán user có vai trò sub-admin."
            )
        return value
