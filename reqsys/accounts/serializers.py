from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import authenticate

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
        return super().validate(attrs)

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()

class UserCreateSerializer(serializers.ModelSerializer):
    group_name = serializers.ChoiceField(choices=['requester', 'owner'], write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'group_name')

    def create(self, validated_data):
        group_name = validated_data.pop('group_name')
        
        # In Django default user model, username is required. We will use email as username.
        validated_data['username'] = validated_data['email']
        
        user = User.objects.create_user(**validated_data)
        
        try:
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
        except Group.DoesNotExist:
            pass # Or raise validation error if you prefer strict checking, but ChoiceField already checked it.
            
        return user
