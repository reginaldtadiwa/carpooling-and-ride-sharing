# matching/pool_manager.py
from django.utils import timezone
from rides.models import Pool, PoolMembership
from routing.services import RouteOptimizer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

class PoolManager:
    def __init__(self):
        self.route_optimizer = RouteOptimizer()
        self.channel_layer = get_channel_layer()
    
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

        # Send WebSocket notification
        self.notify_rider_joined(pool, ride_request)
        
        # Update pool status if full
        if pool.members.count() >= pool.max_riders:
            pool.status = 'filled'
            pool.closed_at = timezone.now()
            pool.save()

            # Notify pool is full
            self.notify_pool_filled(pool)
            
            # Trigger driver assignment
            from .tasks import assign_driver_to_pool
            assign_driver_to_pool.delay(pool.id)
        
        return pool
    
    def notify_rider_joined(self, pool, new_rider):
        """Notify all pool members that a new rider has joined"""
        async_to_sync(self.channel_layer.group_send)(
            f'pool_{pool.id}',
            {
                'type': 'rider_joined',
                'pool_id': pool.id,
                'new_rider_name': new_rider.rider.get_full_name(),
                'current_riders': pool.members.count(),
                'max_riders': pool.max_riders,
                'message': f'{new_rider.rider.get_full_name()} joined the pool'
            }
        )

    def notify_pool_filled(self, pool):
        """Notify all pool members that the pool is filled"""
        async_to_sync(self.channel_layer.group_send)(
            f'pool_{pool.id}',
            {
                'type': 'pool_filled',
                'pool_id': pool.id,
                'message': 'Pool is full! Looking for driver...',
                'status': 'filled'
            }
        )

    def notify_driver_assigned(self, pool, driver):
        """Notify all pool members that driver is assigned"""
        async_to_sync(self.channel_layer.group_send)(
            f'pool_{pool.id}',
            {
                'type': 'driver_assigned',
                'pool_id': pool.id,
                'driver_name': driver.user.get_full_name(),
                'vehicle_type': driver.vehicle_type,
                'license_plate': driver.license_plate,
                'message': f'Driver {driver.user.get_full_name()} assigned to your pool'
            }
        )
       
    
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