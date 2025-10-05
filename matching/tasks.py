# matching/tasks.py
from celery import shared_task
from django.utils import timezone
from rides.models import Pool, Trip
from drivers.services import DriverAssignmentService
from datetime import timedelta
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
logger = logging.getLogger(__name__)

@shared_task
def assign_driver_to_pool(pool_id):
    """Assign driver to a filled pool"""
    try:
        pool = Pool.objects.get(id=pool_id, status='filled')
        assignment_service = DriverAssignmentService()
        driver = assignment_service.find_best_driver(pool)

        if driver:
            logger.info(f"Driver '{driver.user.get_full_name()}' (ID: {driver.id}) found and available for Pool ID {pool.id}.")

            # Create trip and assign driver
            trip = Trip.objects.create(pool=pool, driver=driver)
            pool.status = 'driver_assigned'
            pool.save()

            logger.info(f"Driver assigned to Trip ID {trip.id} for Pool ID {pool.id}.")

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

            logger.info(f"WebSocket notification sent to group 'pool_{pool.id}'.")

        else:
            logger.info(f"No available driver found for Pool ID {pool.id}.")

    except Pool.DoesNotExist:
        logger.warning(f"Pool with ID {pool_id} does not exist or is not in 'filled' status.")


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