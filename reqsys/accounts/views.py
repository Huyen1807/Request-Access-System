from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from .serializers import CustomTokenObtainPairSerializer, UserCreateSerializer, UserSerializer, UserUpdateSerializer, UserListSerializer
from .permissions import IsSubAdmin

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class OwnerListView(generics.ListAPIView):
    serializer_class = UserListSerializer
    permission_classes = [IsAuthenticated, IsSubAdmin]

    def get_queryset(self):
        return User.objects.filter(groups__name='owner').order_by('last_name', 'first_name')


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSubAdmin]

    def get_queryset(self):
        return User.objects.filter(groups__name__in=['requester', 'owner']).distinct()

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer

    def perform_destroy(self, instance):
        # Soft delete instead of hard delete
        instance.is_active = False
        instance.save()
