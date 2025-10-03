# matching/tasks.py
from celery import shared_task
from django.utils import timezone
from rides.models import Pool
from drivers.services import DriverAssignmentService
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@shared_task
def assign_driver_to_pool(pool_id):
    """Assign driver to a filled pool"""
    try:
        pool = Pool.objects.get(id=pool_id, status='filled')
        assignment_service = DriverAssignmentService()
        driver = assignment_service.find_best_driver(pool)
        
        if driver:
            # Create trip and assign driver
            trip = Trip.objects.create(pool=pool, driver=driver)
            pool.status = 'driver_assigned'
            pool.save()
            
            # Notify all pool members via WebSocket
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'pool_{pool.id}',
                {
                    'type': 'driver_assigned',
                    'pool_id': pool.id,
                    'driver_name': driver.user.get_full_name(),
                    'vehicle_type': driver.vehicle_type,
                    'license_plate': driver.license_plate,
                    'eta_minutes': 5,
                    'message': f'Driver {driver.user.get_full_name()} is on the way!'
                })
            
    except Pool.DoesNotExist:
        pass

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
        
        # Notify riders
        notify_pool_expired.delay(pool.id)