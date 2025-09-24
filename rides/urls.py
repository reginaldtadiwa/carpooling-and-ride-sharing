# rides/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import RideRequestViewSet, PoolViewSet, TripViewSet

router = DefaultRouter()
router.register(r'ride-requests', RideRequestViewSet, basename='riderequest')
router.register(r'pools', PoolViewSet, basename='pool')
router.register(r'trips', TripViewSet, basename='trip')

urlpatterns = [
    path('', include(router.urls)),
    
    # Additional custom endpoints
    path('ride-requests/<int:pk>/cancel/', 
         RideRequestViewSet.as_view({'post': 'cancel_ride'}), 
         name='ride-request-cancel'),
    
    path('pools/<int:pk>/status/', 
         PoolViewSet.as_view({'get': 'status'}), 
         name='pool-status'),
]