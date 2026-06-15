from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AccessRequestViewSet, RequesterAccessRequestViewSet

router = DefaultRouter()
router.register(r'access-requests', AccessRequestViewSet, basename='access-request')
router.register(r'my-requests', RequesterAccessRequestViewSet, basename='my-request')

urlpatterns = [
    path('', include(router.urls)),
]
