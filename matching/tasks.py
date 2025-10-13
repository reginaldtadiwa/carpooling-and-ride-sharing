# matching/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from rides.models import Pool, Trip
from drivers.services import DriverAssignmentService
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@shared_task
def assign_driver_to_pool(pool_id):
    """Notify nearby drivers about the pool and wait for acceptance"""
    try:
        pool = Pool.objects.get(id=pool_id, status='filled')
        assignment_service = DriverAssignmentService()
        
        # Find all nearby drivers
        nearby_drivers = assignment_service.find_available_drivers_near_pool(pool)
        
        if nearby_drivers:
            # Notify all nearby drivers
            assignment_service.notify_drivers_of_pool(pool, nearby_drivers)
            print(f"DEBUG: Notified {len(nearby_drivers)} drivers about pool {pool.id}")
            
            # Set a timeout task to reassign if no driver accepts
            wait_for_driver_acceptance.apply_async(
                args=[pool_id], 
                countdown=assignment_service.assignment_timeout
            )
        else:
            print(f"DEBUG: No available drivers found near pool {pool.id}")
           
            
    except Pool.DoesNotExist:
        print(f"DEBUG: Pool {pool_id} not found or not filled")

@shared_task
def wait_for_driver_acceptance(pool_id):
    """Check if any driver accepted the pool, if not, reassign or expire"""
    try:
        pool = Pool.objects.get(id=pool_id)
        
        # Check if pool already has a driver assigned
        if pool.status != 'driver_assigned':
            print(f"DEBUG: No driver accepted pool {pool_id} within timeout")
    except Pool.DoesNotExist:
        print(f"DEBUG: Pool {pool_id} not found during acceptance check")

@shared_task
def driver_accept_pool(driver_id, pool_id):
    """Handle driver accepting a pool assignment"""
    try:
        from rides.models import Driver
        driver = Driver.objects.get(id=driver_id)
        pool = Pool.objects.get(id=pool_id, status='filled')
        
        assignment_service = DriverAssignmentService()
        trip = assignment_service.assign_driver_to_pool(pool, driver)
        
        print(f"DEBUG: Driver {driver_id} accepted pool {pool_id}")
        return trip.id
        
    except (Driver.DoesNotExist, Pool.DoesNotExist) as e:
        print(f"DEBUG: Error in driver acceptance: {e}")
        return None
    
@shared_task
def notify_pool_expired(pool_id):
    """Notify pool members that the pool has expired"""
    try:
        pool = Pool.objects.get(id=pool_id, status='expired')
        
        # Notify all pool members via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'pool_{pool.id}',
            {
                'type': 'pool_expired',
                'pool_id': pool.id,
                'message': 'Pool expired. No more riders joined. Please request a new ride.',
                'status': 'expired'
            }
        )
        print(f"DEBUG: Pool {pool.id} expiration notified to members")
        
    except Pool.DoesNotExist:
        print(f"DEBUG: Pool {pool_id} not found for expiration notification")

@shared_task  
def close_expired_pools():
    """Close pools that have expired waiting time"""
    expired_pools = Pool.objects.filter(
        status='open',
        created_at__lte=timezone.now() - timedelta(minutes=10)
    )
    
    for pool in expired_pools:
        pool.status = 'expired'
        pool.save()
        print(f"DEBUG: Pool {pool.id} expired")
        
        # Notify riders
        notify_pool_expired.delay(pool.id)