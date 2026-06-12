from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DepartmentViewSet, DomainViewSet, ApplicationViewSet

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'domains', DomainViewSet, basename='domain')
router.register(r'applications', ApplicationViewSet, basename='application')

urlpatterns = [
    path('', include(router.urls)),
]
