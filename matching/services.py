# matching/services.py
from django.utils import timezone
from datetime import timedelta
from rides.models import RideRequest, Pool, PoolMembership
import math
import logging

logger = logging.getLogger(__name__)

class PoolMatchingService:
    def __init__(self):
        self.max_pickup_distance = 3000  # 3km in meters
        self.max_destination_distance = 3000  # 3km in meters
        self.max_detour_percentage = 0.15  # 15%
        self.max_wait_time = timedelta(minutes=10)
    
    def find_matching_pools(self, ride_request):
        """Find suitable pools for a ride request using manual distance calculations"""
        open_pools = Pool.objects.filter(
            status='open',
            created_at__gte=timezone.now() - self.max_wait_time
        ).prefetch_related('members__ride_request')
        
        matching_pools = []
        for pool in open_pools:
            if self._is_valid_match(ride_request, pool):
                matching_pools.append(pool)
        
        return matching_pools
    
    def _is_valid_match(self, ride_request, pool):
        """Check if ride request matches pool criteria"""
        if pool.members.count() == 0:
            return False
        
        if not self._is_pickup_near_pool(ride_request, pool):
            return False
        
        if not self._is_destination_near_pool(ride_request, pool):
            return False
        
        if not self._is_route_compatible(ride_request, pool):
            return False
        
        if not self._is_within_time_window(pool):
            return False
        
        return True
    
    def _is_pickup_near_pool(self, ride_request, pool):
        """Check if pickup is near pool's pickup locations using bounding box optimization"""
        # First, use bounding box for quick filtering
        pool_members = list(pool.members.all())
        if not pool_members:
            return False
        
        # Calculate centroid of pool pickups
        centroid_lat, centroid_lng = self._calculate_centroid([
            (float(member.ride_request.pickup_latitude), 
             float(member.ride_request.pickup_longitude))
            for member in pool_members
        ])
        
        # Calculate distance to centroid
        distance = self._haversine_distance(
            float(ride_request.pickup_latitude),
            float(ride_request.pickup_longitude),
            centroid_lat,
            centroid_lng
        )
        
        return distance <= self.max_pickup_distance
    
    def _is_destination_near_pool(self, ride_request, pool):
        """Check if destination is near pool members' destinations"""
        pool_members = list(pool.members.all())
        if not pool_members:
            return False
        
        # Calculate centroid of pool destinations
        centroid_lat, centroid_lng = self._calculate_centroid([
            (float(member.ride_request.destination_latitude), 
             float(member.ride_request.destination_longitude))
            for member in pool_members
        ])
        
        # Calculate distance to centroid
        distance = self._haversine_distance(
            float(ride_request.destination_latitude),
            float(ride_request.destination_longitude),
            centroid_lat,
            centroid_lng
        )
        
        return distance <= self.max_destination_distance
    
    def _is_route_compatible(self, ride_request, pool):
        """Check if adding this rider maintains reasonable detour limits"""
        pool_members = list(pool.members.all())
        
        # Calculate current optimized route distance for pool
        current_route_distance = self._estimate_pool_route_distance([
            member.ride_request for member in pool_members
        ])
        
        # Calculate new route distance with additional rider
        new_route_distance = self._estimate_pool_route_distance([
            member.ride_request for member in pool_members
        ] + [ride_request])
        
        # Check if detour is acceptable
        if current_route_distance > 0:
            detour_percentage = (new_route_distance - current_route_distance) / current_route_distance
            return detour_percentage <= self.max_detour_percentage
        
        return True
    
    def _estimate_pool_route_distance(self, ride_requests):
        """Estimate total route distance for a set of ride requests"""
        if not ride_requests:
            return 0
        
        # Simple estimation based on straight-line distances
        total_distance = 0
        
        # Start from first pickup
        current_lat = float(ride_requests[0].pickup_latitude)
        current_lng = float(ride_requests[0].pickup_longitude)
        
        for i, rr in enumerate(ride_requests):
            rr_lat = float(rr.pickup_latitude)
            rr_lng = float(rr.pickup_longitude)
            dest_lat = float(rr.destination_latitude)
            dest_lng = float(rr.destination_longitude)
            
            # Distance from current point to this pickup (if not first)
            if i > 0:
                total_distance += self._haversine_distance(
                    current_lat, current_lng, rr_lat, rr_lng
                )
            
            # Distance from pickup to destination
            total_distance += self._haversine_distance(
                rr_lat, rr_lng, dest_lat, dest_lng
            )
            current_lat, current_lng = dest_lat, dest_lng
        
        return total_distance
    
    def _calculate_centroid(self, points):
        """Calculate centroid of multiple points (lat, lng tuples)"""
        if not points:
            return (0, 0)
        
        avg_lat = sum(point[0] for point in points) / len(points)
        avg_lng = sum(point[1] for point in points) / len(points)
        
        return (avg_lat, avg_lng)
    
    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate great-circle distance between two points in meters"""
        R = 6371000  # Earth radius in meters
        
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _is_within_time_window(self, pool):
        """Check if pool is still within waiting window"""
        return timezone.now() - pool.created_at <= self.max_wait_time

class PoolManager:
    def __init__(self):
        from routing.services import RouteOptimizer
        self.route_optimizer = RouteOptimizer()
    
    def create_pool(self, ride_request):
        """Create a new pool for a ride request"""
        pool = Pool.objects.create()
        PoolMembership.objects.create(
            pool=pool,
            ride_request=ride_request,
            pickup_order=1,
            dropoff_order=1
        )
        return pool
    
    def add_to_pool(self, ride_request, pool):
        """Add rider to existing pool with optimized routing"""
        current_members = list(pool.members.all())
        all_requests = [member.ride_request for member in current_members] + [ride_request]
        
        # Optimize pickup and dropoff order
        optimized_route = self.route_optimizer.optimize_route(all_requests)
        
        # Update pool members with new optimized order
        self._update_pool_members_order(pool, optimized_route, ride_request)
        
        if pool.members.count() >= pool.max_riders:
            pool.status = 'filled'
            pool.closed_at = timezone.now()
            pool.save()
            
            from .tasks import assign_driver_to_pool
            assign_driver_to_pool.delay(pool.id)
        
        return pool
    
    def _update_pool_members_order(self, pool, optimized_route, new_ride_request):
        """Update pickup and dropoff order based on optimized route"""
        pool.members.all().delete()
        
        for i, (request, is_pickup) in enumerate(optimized_route['sequence']):
            pickup_order = optimized_route['pickup_orders'][request.id]
            dropoff_order = optimized_route['dropoff_orders'][request.id]
            
            PoolMembership.objects.create(
                pool=pool,
                ride_request=request,
                pickup_order=pickup_order,
                dropoff_order=dropoff_order
            )