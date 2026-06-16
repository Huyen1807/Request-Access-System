from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AccessRequestViewSet,
    RequesterAccessRequestViewSet,
    SubAdminBatchViewSet,
    OwnerBatchViewSet,
)

router = DefaultRouter()
router.register(r'access-requests', AccessRequestViewSet, basename='access-request')
router.register(r'my-requests', RequesterAccessRequestViewSet, basename='my-request')
router.register(r'batches', SubAdminBatchViewSet, basename='batch')
router.register(r'owner-batches', OwnerBatchViewSet, basename='owner-batch')

urlpatterns = [
    path('', include(router.urls)),
]
