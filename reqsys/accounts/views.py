from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import UserCreateSerializer, UserSerializer, UserUpdateSerializer, ChangePasswordSerializer
from .permissions import IsSubAdmin
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSubAdmin]

    def get_permissions(self):
        if self.action == 'change_password':
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        return User.objects.select_related('profile').all()

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer

    @extend_schema(responses=UserSerializer(many=True))
    @action(detail=False, methods=['get'], url_path='owners')
    def owners(self, request):
        qs = User.objects.filter(profile__is_owner=True, is_active=True).order_by('first_name', 'last_name')
        serializer = UserSerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(responses=UserSerializer(many=True))
    @action(detail=False, methods=['get'], url_path='subadmins')
    def subadmins(self, request):
        qs = User.objects.filter(profile__is_subadmin=True, is_active=True).order_by('first_name', 'last_name')
        serializer = UserSerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(request=ChangePasswordSerializer, responses={200: None})
    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"detail": "Đổi mật khẩu thành công."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
