# matching/pool_manager.py
from django.utils import timezone
from rides.models import Pool, PoolMembership
from routing.services import RouteOptimizer

class PoolManager:
    def __init__(self):
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
        # Get current members
        current_members = list(pool.members.all())
        
        # Add new member temporarily for optimization
        all_requests = [member.ride_request for member in current_members] + [ride_request]
        
        # Optimize pickup and dropoff order
        optimized_route = self.route_optimizer.optimize_route(all_requests)
        
        # Update pool members with new optimized order
        self._update_pool_members_order(pool, optimized_route, ride_request)
        
        # Update pool status if full
        if pool.members.count() >= pool.max_riders:
            pool.status = 'filled'
            pool.closed_at = timezone.now()
            pool.save()
            
            # Trigger driver assignment
            from .tasks import assign_driver_to_pool
            assign_driver_to_pool.delay(pool.id)
        
        return pool
    
    def _update_pool_members_order(self, pool, optimized_route, new_ride_request):
        """Update pickup and dropoff order based on optimized route"""
        # Clear existing memberships and recreate with new order
        pool.members.all().delete()
        
        for i, (request, is_pickup) in enumerate(optimized_route['sequence']):
            if request == new_ride_request:
                # This is our new rider
                PoolMembership.objects.create(
                    pool=pool,
                    ride_request=request,
                    pickup_order=optimized_route['pickup_orders'][request.id],
                    dropoff_order=optimized_route['dropoff_orders'][request.id]
                )
            else:
                # Existing rider - find their membership
                PoolMembership.objects.create(
                    pool=pool,
                    ride_request=request,
                    pickup_order=optimized_route['pickup_orders'][request.id],
                    dropoff_order=optimized_route['dropoff_orders'][request.id]
                )