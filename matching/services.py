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

        logger.info(f"Searching through {open_pools.count()} open pools for ride request {ride_request.id}")
        
        matching_pools = []
        for pool in open_pools:
            logger.info(f"--- Testing Pool {pool.id} ---")         
            if self._is_valid_match(ride_request, pool):
                matching_pools.append(pool)
                logger.info(f"Added Pool {pool.id} to matching pools")
            else:
                logger.info(f"Pool {pool.id} is NOT a valid match")
            logger.info(f"--- End Pool {pool.id} Test ---")

        logger.info(f"Found {len(matching_pools)} matching pools total")
        return matching_pools
    
    def _is_valid_match(self, ride_request, pool):
        """Check if ride request matches pool criteria"""
        if pool.members.count() == 0:
            logger.info(f"Pool {pool.id} has no members - invalid")
            return False
        
        logger.info(f"Testing pool {pool.id} with {pool.members.count()} members")
        
        if not self._is_pickup_near_pool(ride_request, pool):
            logger.info(f"Pool {pool.id} failed PICKUP proximity check")
            return False
        else:
            logger.info(f"Pool {pool.id} passed PICKUP proximity check")
        
        if not self._is_destination_near_pool(ride_request, pool):
            logger.info(f"Pool {pool.id} failed DESTINATION proximity check")
            return False
        else:
            logger.info(f"Pool {pool.id} passed DESTINATION proximity check")
        
        if not self._is_route_compatible(ride_request, pool):
            logger.info(f"Pool {pool.id} failed ROUTE compatibility check")
            return False
        else:
            logger.info(f"Pool {pool.id} passed ROUTE compatibility check")
        
        if not self._is_within_time_window(pool):
            logger.info(f"Pool {pool.id} failed TIME WINDOW check")
            return False
        else:
            logger.info(f"Pool {pool.id} passed TIME WINDOW check")
        
        logger.info(f"Pool {pool.id} passed ALL checks - VALID MATCH!")
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

        logger.info(f"=== ROUTE COMPATIBILITY CHECK ===")
        logger.info(f"Pool has {len(pool_members)} members")

        for i, member in enumerate(pool_members):
            rr = member.ride_request
            logger.info(f"Pool member {i}: Pickup({rr.pickup_latitude}, {rr.pickup_longitude}) -> Dest({rr.destination_latitude}, {rr.destination_longitude})")
        
        logger.info(f"New request: Pickup({ride_request.pickup_latitude}, {ride_request.pickup_longitude}) -> Dest({ride_request.destination_latitude}, {ride_request.destination_longitude})")
        
        # Calculate current optimized route distance for pool
        current_route_distance = self._estimate_pool_route_distance([
            member.ride_request for member in pool_members
        ])
        logger.info(f"Current route distance: {current_route_distance:.2f}m")

        # Calculate new route distance with additional rider
        new_route_distance = self._estimate_pool_route_distance([
            member.ride_request for member in pool_members
        ] + [ride_request])

        logger.info(f"New route distance: {new_route_distance:.2f}m")
        
        # Check if detour is acceptable
        if current_route_distance > 0:
            detour_distance = new_route_distance - current_route_distance
            detour_percentage = (detour_distance) / current_route_distance
           
            logger.info(f"Detour distance: {detour_distance:.2f}m")
            logger.info(f"Detour percentage: {detour_percentage:.4f} ({detour_percentage:.2%})")
            logger.info(f" Max allowed detour: {self.max_detour_percentage:.4f} ({self.max_detour_percentage:.2%})")

            is_compatible = detour_percentage <= self.max_detour_percentage
            logger.info(f" Route compatible: {is_compatible}")
            logger.info(f"=== END ROUTE COMPATIBILITY CHECK ===")

            return is_compatible
        
        logger.info(" First rider in pool - no detour calculation needed")
        logger.info(f"=== END ROUTE COMPATIBILITY CHECK ===")
        return True
    
    def _estimate_pool_route_distance(self, ride_requests):
        """Estimate total route distance for a set of ride requests"""
        if not ride_requests:
            logger.info("No ride requests - distance 0m")
            return 0
        
        logger.info(f"Calculating route for {len(ride_requests)} requests")

        # Check if all requests are identical
        if self._all_requests_identical(ride_requests):
            logger.info("All requests are identical")
            # For identical requests, distance = single trip (shared ride)
            rr = ride_requests[0]
            single_trip_distance = self._haversine_distance(
                float(rr.pickup_latitude), float(rr.pickup_longitude),
                float(rr.destination_latitude), float(rr.destination_longitude)
            )
            total_distance = single_trip_distance  # Shared ride; no duplication
            logger.info(f"Identical route distance: {total_distance:.2f}m")
            return total_distance
        
        # For non-identical requests, use the original logic
        total_distance = 0
        current_lat = float(ride_requests[0].pickup_latitude)
        current_lng = float(ride_requests[0].pickup_longitude)

        logger.info(f"🏁 Starting at: ({current_lat}, {current_lng})")
        
        for i, rr in enumerate(ride_requests):
            rr_lat = float(rr.pickup_latitude)
            rr_lng = float(rr.pickup_longitude)
            dest_lat = float(rr.destination_latitude)
            dest_lng = float(rr.destination_longitude)

            logger.info(f"Request {i}: Pickup({rr_lat}, {rr_lng}) -> Dest({dest_lat}, {dest_lng})")

            # Distance to pickup (if not already there)
            if i > 0 and (current_lat != rr_lat or current_lng != rr_lng):
                pickup_dist = self._haversine_distance(current_lat, current_lng, rr_lat, rr_lng)
                total_distance += pickup_dist
                logger.info(f"To pickup: {pickup_dist:.2f}m")

            else:
                logger.info("Already at pickup")

            leg_dist = self._haversine_distance(rr_lat, rr_lng, dest_lat, dest_lng)
            total_distance += leg_dist
            logger.info(f"Pickup to dest: {leg_dist:.2f}m")

            current_lat, current_lng = dest_lat, dest_lng
            logger.info(f"Now at: ({current_lat}, {current_lng})")
            logger.info(f"Subtotal: {total_distance:.2f}m")

        logger.info(f"📏 Total distance: {total_distance:.2f}m")
        return total_distance
    

    def _all_requests_identical(self, ride_requests):
        """Check if all ride requests have identical pickup and destination"""
        if len(ride_requests) <= 1:
            return True
        
        first_rr = ride_requests[0]
        first_pickup = (float(first_rr.pickup_latitude), float(first_rr.pickup_longitude))
        first_dest = (float(first_rr.destination_latitude), float(first_rr.destination_longitude))

        for rr in ride_requests[1:]:
            current_pickup = (float(rr.pickup_latitude), float(rr.pickup_longitude))
            current_dest = (float(rr.destination_latitude), float(rr.destination_longitude))

            # Use a tolerance for floating point comparison
            pickup_match = (
                abs(first_pickup[0] - current_pickup[0]) < 0.0001 and
                abs(first_pickup[1] - current_pickup[1]) < 0.0001
            )
            dest_match = (
                abs(first_dest[0] - current_dest[0]) < 0.0001 and
                abs(first_dest[1] - current_dest[1]) < 0.0001
                )
            
            if not (pickup_match and dest_match):
                logger.info(f"Requests not identical: {first_pickup} vs {current_pickup}")
                return False
            
        logger.info("All requests are identical")
        return True
    
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

        """Update pool members based on optimized route - FIXED VERSION"""
        logger.info(f"_update_pool_members_order started for pool {pool.id}")
    
        # Clear existing members
        deleted_count, _ = PoolMembership.objects.filter(pool=pool).delete()
        logger.info(f"Deleted {deleted_count} existing members")

        sequence = optimized_route.get('sequence', [])
        pickup_orders = optimized_route.get('pickup_orders', {})
        dropoff_orders = optimized_route.get('dropoff_orders', {})
    
        logger.info(f"Sequence length: {len(sequence)}")
        logger.info(f"Pickup orders: {pickup_orders}")
        logger.info(f"Dropoff orders: {dropoff_orders}")

        # Extract unique ride requests from sequence
        unique_requests = []
        seen_ids = set()

        for item in sequence:
            if isinstance(item, tuple) and len(item) == 2:
                ride_request_obj, is_pickup = item
                if hasattr(ride_request_obj, 'id') and ride_request_obj.id not in seen_ids:
                    seen_ids.add(ride_request_obj.id)
                    unique_requests.append(ride_request_obj)
                    logger.info(f"Found ride request: {ride_request_obj.id}")

        logger.info(f"Unique ride requests: {[rr.id for rr in unique_requests]}")

        # If no unique requests found, use the new ride request
        # If no unique requests found, use the new ride request
        if not unique_requests:
            logger.warning("No ride requests found in sequence, using new_ride_request")
            unique_requests = [new_ride_request]

        # Create memberships
        for ride_request in unique_requests:
            pickup_order = pickup_orders.get(ride_request.id, 1)
            dropoff_order = dropoff_orders.get(ride_request.id, 1)
        
            logger.info(f"Creating membership for {ride_request.id}: "
                   f"pickup_order={pickup_order}, dropoff_order={dropoff_order}")
            
            PoolMembership.objects.create(
                pool=pool,
                ride_request=ride_request,
                pickup_order=pickup_order,
                dropoff_order=dropoff_order

            )
        
        final_count = PoolMembership.objects.filter(pool=pool).count()
        logger.info(f"Final member count: {final_count}")
    






