# drivers/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import DriverViewSet

router = DefaultRouter()
router.register(r'', DriverViewSet, basename='driver')

urlpatterns = [
    path('', include(router.urls)),
    path('<int:pk>/availability/', 
         DriverViewSet.as_view({'post': 'update_availability'}), 
         name='driver-availability'),
    path('<int:pk>/location/', 
         DriverViewSet.as_view({'post': 'update_location'}), 
         name='driver-location'),
]