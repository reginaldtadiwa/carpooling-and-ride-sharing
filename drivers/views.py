# drivers/views.py
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from rides.models import Driver
from .serializers import DriverSerializer, DriverRegistrationSerializer
from rides.models import Trip


class DriverViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Drivers can only see their own profile
        if hasattr(self.request.user, 'driver'):
            return self.queryset.filter(user=self.request.user)
        return Driver.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def my_profile(self, request):
        """Get current driver's profile"""
        try:
            driver = Driver.objects.get(user=request.user)
            serializer = self.get_serializer(driver)
            return Response(serializer.data)
        except Driver.DoesNotExist:
            return Response({'error': 'Driver profile not found'}, 
                           status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def update_availability(self, request, pk=None):
        """Update driver availability"""
        driver = self.get_object()
        
        is_available = request.data.get('is_available', driver.is_available)
        current_latitude = request.data.get('current_latitude')
        current_longitude = request.data.get('current_longitude')

        driver.is_available = is_available
        if current_latitude is not None:
            driver.current_latitude = current_latitude
        if current_longitude is not None:
            driver.current_longitude = current_longitude        
        driver.save()
        
        return Response({
            'status': 'availability_updated', 
            'is_available': is_available
        })

    @action(detail=True, methods=['post'])
    def update_location(self, request, pk=None):
        """Update driver's current location"""
        driver = self.get_object()
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if latitude is not None and longitude is not None:
            driver.current_latitude = latitude
            driver.current_longitude = longitude
            driver.save()
            
            return Response({'status': 'location_updated'})
        
        return Response({'error': 'Invalid coordinates'}, 
                       status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def available_trips(self, request):
        """Get available trips for drivers"""
        if not hasattr(request.user, 'driver'):
            return Response({'error': 'Driver profile required'}, 
                           status=status.HTTP_403_FORBIDDEN)
        
        driver = request.user.driver
        
        # Find trips that need a driver and match vehicle capacity
        available_trips = Trip.objects.filter(
            driver__isnull=True,  # No driver assigned yet
            pool__status='filled',  # Pool is ready
            pool__members__count__lte=driver.max_capacity  # Fits in vehicle
        ).distinct()
        
        trip_data = []
        for trip in available_trips:
            trip_data.append({
                'trip_id': trip.id,
                'pool_size': trip.pool.members.count(),
                'estimated_fare': trip.pool.estimated_fare,
                'created_at': trip.pool.created_at
            })
        
        return Response({'available_trips': trip_data})

    @action(detail=True, methods=['post'])
    def accept_trip(self, request, pk=None):
        """Accept a trip assignment"""
        driver = self.get_object()
        trip_id = request.data.get('trip_id')
        
        try:
            trip = Trip.objects.get(id=trip_id, driver__isnull=True)
            trip.driver = driver
            trip.save()
            
            # Update pool status
            trip.pool.status = 'driver_assigned'
            trip.pool.save()
            
            return Response({'status': 'trip_accepted', 'trip_id': trip.id})
        
        except Trip.DoesNotExist:
            return Response({'error': 'Trip not available'}, 
                           status=status.HTTP_400_BAD_REQUEST)

class DriverRegistrationView(generics.CreateAPIView):
    """View for drivers to register their vehicle"""
    queryset = Driver.objects.all()
    serializer_class = DriverRegistrationSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)