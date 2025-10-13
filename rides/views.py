# rides/views.py
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import RideRequest, Pool, Trip
from .serializers import RideRequestSerializer, PoolSerializer, TripSerializer
from matching.services import PoolMatchingService, PoolManager

logger = logging.getLogger(__name__)

class RideRequestViewSet(viewsets.ModelViewSet):
    queryset = RideRequest.objects.all()
    serializer_class = RideRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own ride requests
        return self.queryset.filter(rider=self.request.user)

    def perform_create(self, serializer):
        serializer.save(rider=self.request.user)

    @action(detail=False, methods=['post'])
    def request_ride(self, request):
        """Create a new ride request and match with pools"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create the ride request
        ride_request = serializer.save(rider=request.user)

        # DEBUG: Log the ride request details
        logger.info(f"New ride request: {ride_request.id}")
        logger.info(f"Pickup: {ride_request.pickup_latitude}, {ride_request.pickup_longitude}")
        logger.info(f"Destination: {ride_request.destination_latitude}, {ride_request.destination_longitude}")
        
        # Find matching pools
        matching_service = PoolMatchingService()
        matching_pools = matching_service.find_matching_pools(ride_request)

        # DEBUG: Log matching results
        logger.info(f"Found {len(matching_pools)} matching pools")
        for pool in matching_pools:
            logger.info(f"Pool {pool.id} has {pool.members.count()} members")
        
        if matching_pools:
            # Join the best matching pool
            pool_manager = PoolManager()
            pool = matching_pools[0]  
            pool_manager.add_to_pool(ride_request, pool)

            # Update pool estimated fare
            if ride_request.fare_estimate:
                pool.estimated_fare = (pool.estimated_fare or 0) + ride_request.fare_estimate
                pool.save()

            pool.refresh_from_db()
            rider_count = pool.members.count()
       
            return Response({
                'status': 'joined_pool',
                'pool_id': pool.id,
                'current_riders': rider_count,
                'message': f'Joined pool with {rider_count} riders'
            }, status=status.HTTP_201_CREATED)
        else:
            # Create new pool
            pool_manager = PoolManager()
            pool = pool_manager.create_pool(ride_request)

            # Set the initial estimated_fare for the new pool
            if ride_request.fare_estimate:
                pool.estimated_fare = ride_request.fare_estimate
                pool.save()

            # DEBUG: Log new pool creation
            logger.info(f"Created new pool: {pool.id}")
            
            return Response({
                'status': 'new_pool_created',
                'pool_id': pool.id,
                'message': 'New pool created. Waiting for other riders...'
            }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def cancel_ride(self, request, pk=None):
        """Cancel a ride request"""
        ride_request = self.get_object()
        
        # Check if ride can be cancelled
        if ride_request.status not in ['completed', 'cancelled']:
            ride_request.status = 'cancelled'
            ride_request.save()
            
            # Handle pool logic if in pool
            membership = PoolMembership.objects.filter(ride_request=ride_request).first()
            if membership:
                pool = membership.pool
                if pool.members.count() == 1:
                    # Last rider in pool, cancel the pool
                    pool.status = 'cancelled'
                    pool.save()
                else:
                    # Remove rider from pool
                    membership.delete()
            
            return Response({'status': 'cancelled'})
        
        return Response({'error': 'Ride cannot be cancelled'}, 
                       status=status.HTTP_400_BAD_REQUEST)

class PoolViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Pool.objects.all()
    serializer_class = PoolSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see pools they're part of
        return Pool.objects.filter(
            members__ride_request__rider=self.request.user
        ).distinct()

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get detailed pool status"""
        pool = self.get_object()
        serializer = self.get_serializer(pool)
        
        # Calculate time elapsed
        time_elapsed = (timezone.now() - pool.created_at).total_seconds() / 60
        
        response_data = serializer.data
        response_data.update({
            'current_riders': pool.members.count(),
            'max_riders': pool.max_riders,
            'time_elapsed_minutes': round(time_elapsed, 1),
            'time_remaining_minutes': max(0, pool.max_wait_time - time_elapsed),
            'is_full': pool.members.count() >= pool.max_riders
        })
        
        return Response(response_data)

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """Get detailed information about pool members"""
        pool = self.get_object()
        members = pool.members.all()
        
        member_data = []
        for membership in members:
            member_data.append({
                'rider_name': membership.ride_request.rider.get_full_name(),
                'pickup_address': membership.ride_request.pickup_address,
                'destination_address': membership.ride_request.destination_address,
                'pickup_order': membership.pickup_order,
                'dropoff_order': membership.dropoff_order
            })
        
        return Response({'members': member_data})

class TripViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see trips they're part of
        return Trip.objects.filter(
            pool__members__ride_request__rider=self.request.user
        ).distinct()

    @action(detail=True, methods=['get'])
    def route(self, request, pk=None):
        """Get trip route details"""
        trip = self.get_object()
        
        # Get pickup and dropoff points in order
        route_points = []
        memberships = trip.pool.members.all().order_by('pickup_order')
        
        for membership in memberships:
            route_points.append({
                'type': 'pickup',
                'rider_name': membership.ride_request.rider.get_full_name(),
                'address': membership.ride_request.pickup_address,
                'latitude': float(membership.ride_request.pickup_latitude),
                'longitude': float(membership.ride_request.pickup_longitude),
                'order': membership.pickup_order
            })
        
        memberships = trip.pool.members.all().order_by('dropoff_order')
        for membership in memberships:
            route_points.append({
                'type': 'dropoff',
                'rider_name': membership.ride_request.rider.get_full_name(),
                'address': membership.ride_request.destination_address,
                'latitude': float(membership.ride_request.destination_latitude),
                'longitude': float(membership.ride_request.destination_longitude),
                'order': membership.dropoff_order
            })
        
        return Response({'route': sorted(route_points, key=lambda x: x['order'])})