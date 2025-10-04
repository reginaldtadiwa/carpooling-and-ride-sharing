# matching/pool_manager.py
from django.utils import timezone
from rides.models import Pool, PoolMembership
from routing.services import RouteOptimizer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

class PoolManager:
    def __init__(self):
        self.route_optimizer = RouteOptimizer()
        #self.channel_layer = get_channel_layer()

        try:
            self.channel_layer = get_channel_layer()
            print(f"DEBUG: Channel layer initialized: {self.channel_layer is not None}")
        except Exception as e:
            print(f"DEBUG: ERROR initializing channel layer: {e}")
            import traceback
            traceback.print_exc()
            self.channel_layer = None
    
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

        print(f"DEBUG: Before notify_rider_joined - pool {pool.id}, rider {ride_request.id}")

        try:
            # Send WebSocket notification
            self.notify_rider_joined(pool, ride_request)
            print(f"DEBUG: After notify_rider_joined - success")
        except Exception as e:
            print(f"DEBUG: ERROR in notify_rider_joined: {e}")
            import traceback
            traceback.print_exc()

        pool.refresh_from_db()
        
        if pool.members.count() >= pool.max_riders:
            print(f"DEBUG: Pool {pool.id} has {pool.members.count()} members, max is {pool.max_riders}")
            pool.status = 'filled'
            pool.closed_at = timezone.now()
            pool.save()

            print(f"DEBUG: Before notify_pool_filled - pool {pool.id}")
            try:
                self.notify_pool_filled(pool)
                print(f"DEBUG: After notify_pool_filled - success")
            except Exception as e:
                print(f"DEBUG: ERROR in notify_pool_filled: {e}")
                import traceback
                traceback.print_exc()

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
        print(f"DEBUG: Message sent to pool_{pool.id}")

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
    
        # Get unique ride requests (avoid duplicates from pickup/dropoff sequence)
        processed_requests = set()
    
        for i, (request, is_pickup) in enumerate(optimized_route['sequence']):
            if request.id not in processed_requests:
                PoolMembership.objects.create(
                    pool=pool,
                    ride_request=request,
                    pickup_order=optimized_route['pickup_orders'][request.id],
                    dropoff_order=optimized_route['dropoff_orders'][request.id]
            )
                processed_requests.add(request.id)