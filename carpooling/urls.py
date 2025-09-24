# carpooling/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),
    
    # JWT Authentication endpoints
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # API endpoints
    path('api/auth/', include('accounts.urls')),
    path('api/', include('rides.urls')),
    path('api/drivers/', include('drivers.urls')),

     # DRF Spectacular URLs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Add this for Django REST framework API root
from rest_framework import routers
from rides.api import RideRequestViewSet, PoolViewSet
from drivers.api import DriverViewSet

router = routers.DefaultRouter()
router.register(r'ride-requests', RideRequestViewSet, basename='riderequest')
router.register(r'pools', PoolViewSet, basename='pool')
router.register(r'drivers', DriverViewSet, basename='driver')

urlpatterns += [
    path('api/v1/', include(router.urls)),
]