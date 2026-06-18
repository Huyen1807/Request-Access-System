from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import UserCreateSerializer, UserSerializer, UserUpdateSerializer, ChangePasswordSerializer
from .permissions import IsSubAdmin, IsNotRequester
from django.contrib.auth import get_user_model

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSubAdmin]

    def get_permissions(self):
        if self.action == 'change_password':
            return [IsAuthenticated(), IsNotRequester()]
        return super().get_permissions()

    def get_queryset(self):
        return User.objects.filter(groups__name__in=['requester', 'owner']).distinct()

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer

    @action(detail=False, methods=['get'], url_path='owners')
    def owners(self, request):
        qs = User.objects.filter(groups__name='owner', is_active=True).order_by('first_name', 'last_name')
        serializer = UserSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"detail": "Đổi mật khẩu thành công."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
