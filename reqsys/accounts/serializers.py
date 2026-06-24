from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db import IntegrityError

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # We replace username with email
        self.fields['email'] = serializers.EmailField()
        if 'username' in self.fields:
            del self.fields['username']

    def validate(self, attrs):
        # We need to map email back to username so the parent validate method
        # can authenticate properly using our custom backend, which expects
        # either 'username' containing the email or 'email' keyword arg.
        # TokenObtainPairSerializer's validate() expects self.user to be set via
        # authenticate(username=..., password=...)

        password = attrs.get('password')
        email = attrs.get('email')

        # Use our custom backend implicitly via authenticate
        user = authenticate(request=self.context.get('request'), username=email, password=password)

        if not user:
            raise serializers.ValidationError('No active account found with the given credentials')

        self.user = user

        # We can then call super().validate by injecting username into attrs
        # to satisfy the parent class validation logic which checks for username
        attrs['username'] = email
        data = super().validate(attrs)

        roles = ['requester']
        profile = getattr(user, 'profile', None)
        if profile and profile.is_subadmin:
            roles.append('sub-admin')
        if profile and profile.is_owner:
            roles.append('owner')
        data['roles'] = roles
        data['email'] = user.email
        data['first_name'] = user.first_name
        data['last_name'] = user.last_name
        return data

from django.contrib.auth import get_user_model

User = get_user_model()

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    is_subadmin = serializers.BooleanField(write_only=True, required=False, default=False)
    is_owner = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'is_subadmin', 'is_owner')

    def create(self, validated_data):
        is_subadmin = validated_data.pop('is_subadmin', False)
        is_owner = validated_data.pop('is_owner', False)

        # In Django default user model, username is required. We will use email as username.
        validated_data['username'] = validated_data['email']

        try:
            user = User.objects.create_user(**validated_data)
        except IntegrityError:
            raise serializers.ValidationError("Tài khoản với email này đã tồn tại.")

        user.profile.is_subadmin = is_subadmin
        user.profile.is_owner = is_owner
        user.profile.save()

        roles = ['requester']
        if is_subadmin:
            roles.append('sub-admin')
        if is_owner:
            roles.append('owner')

        # Send email to the newly created user
        from django.core.mail import send_mail
        from django.conf import settings

        subject = 'Thông tin đăng nhập hệ thống Request Access System'
        message = (
            f"Xin chào {user.first_name} {user.last_name},\n\n"
            f"Tài khoản của bạn đã được tạo thành công với vai trò: {', '.join(roles)}.\n\n"
            f"Thông tin đăng nhập:\n"
            f"- Email: {user.email}\n"
            f"- Mật khẩu: {validated_data.get('password')}\n\n"
            f"Vui lòng đổi mật khẩu sau khi đăng nhập (nếu hệ thống yêu cầu).\n\n"
            f"Trân trọng,\nBan Quản trị"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
        )

        return user

class UserSerializer(serializers.ModelSerializer):
    is_subadmin = serializers.BooleanField(source='profile.is_subadmin', read_only=True)
    is_owner = serializers.BooleanField(source='profile.is_owner', read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'is_active', 'is_subadmin', 'is_owner')
        read_only_fields = ('id', 'email')


class UserUpdateSerializer(serializers.ModelSerializer):
    is_subadmin = serializers.BooleanField(required=False)
    is_owner = serializers.BooleanField(required=False)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'is_active', 'is_subadmin', 'is_owner')

    def update(self, instance, validated_data):
        is_subadmin = validated_data.pop('is_subadmin', None)
        is_owner = validated_data.pop('is_owner', None)
        instance = super().update(instance, validated_data)

        if is_subadmin is not None or is_owner is not None:
            profile = instance.profile
            if is_subadmin is not None:
                profile.is_subadmin = is_subadmin
            if is_owner is not None:
                profile.is_owner = is_owner
            profile.save()

        return instance

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Mật khẩu cũ không đúng.")
        return value

