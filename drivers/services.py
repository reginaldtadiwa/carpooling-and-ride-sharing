# drivers/services.py
import math
from django.utils import timezone
from rides.models import Driver
from rides.models import Pool, Trip
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

class DriverAssignmentService:
    def __init__(self):
        self.max_assignment_distance = 10000  # 10km in meters
        self.assignment_timeout = 60  # seconds for drivers to respond
    
    def find_available_drivers_near_pool(self, pool):
        """Find all available drivers near the pool"""
        pool_centroid = self._calculate_pool_centroid(pool)
        if not pool_centroid:
            return []
        
        # Find available drivers with sufficient capacity
        available_drivers = Driver.objects.filter(
            is_available=True,
            max_capacity__gte=pool.members.count()
        )
        
        nearby_drivers = []
        for driver in available_drivers:
            if driver.current_latitude and driver.current_longitude:
                distance = self._calculate_distance(
                    pool_centroid[0], pool_centroid[1],
                    float(driver.current_latitude), float(driver.current_longitude)
                )
                
                if distance <= self.max_assignment_distance:
                    nearby_drivers.append({
                        'driver': driver,
                        'distance': distance
                    })
        
        # Sort by distance (closest first)
        nearby_drivers.sort(key=lambda x: x['distance'])
        return [item['driver'] for item in nearby_drivers]
    
    def notify_drivers_of_pool(self, pool, drivers):
        """Notify multiple drivers about the available pool"""
        channel_layer = get_channel_layer()
        
        for driver in drivers:
            # Send WebSocket notification to each driver
            async_to_sync(channel_layer.group_send)(
                f'driver_{driver.id}',
                {
                    'type': 'pool_assignment',
                    'pool_id': pool.id,
                    'pool_size': pool.members.count(),
                    'estimated_fare': pool.estimated_fare,
                    'pickup_sequence': self._get_pickup_sequence(pool),
                    'timeout_seconds': self.assignment_timeout,
                    'message': f'New pool available with {pool.members.count()} riders'
                }
            )
    
    def assign_driver_to_pool(self, pool, driver):
        """Assign a specific driver to the pool"""
        # Create trip and assign driver
        trip = Trip.objects.create(pool=pool, driver=driver)
        pool.status = 'driver_assigned'
        pool.save()
        
        # Mark driver as unavailable
        driver.is_available = False
        driver.save()
        
        # Notify all pool members
        self._notify_pool_members_driver_assigned(pool, driver)
        
        # Notify the assigned driver with route details
        self._notify_driver_with_route(pool, driver)
        
        return trip
    
    def _get_pickup_sequence(self, pool):
        """Get the optimized pickup sequence for the pool"""
        members = pool.members.all().order_by('pickup_order')
        sequence = []
        
        for membership in members:
            ride_request = membership.ride_request
            sequence.append({
                'rider_name': ride_request.rider.get_full_name(),
                'pickup_address': ride_request.pickup_address,
                'latitude': float(ride_request.pickup_latitude),
                'longitude': float(ride_request.pickup_longitude),
                'order': membership.pickup_order
            })
        
        return sequence
    
    def _notify_pool_members_driver_assigned(self, pool, driver):
        """Notify pool members that a driver has been assigned"""
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
            }
        )
    
    def _notify_driver_with_route(self, pool, driver):
        """Notify the assigned driver with the complete route"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'driver_{driver.id}',
            {
                'type': 'assignment_confirmed',
                'pool_id': pool.id,
                'pickup_sequence': self._get_pickup_sequence(pool),
                'dropoff_sequence': self._get_dropoff_sequence(pool),
                'total_riders': pool.members.count(),
                'message': 'Pool assignment confirmed! Navigate to first pickup.'
            }
        )
    
    def _get_dropoff_sequence(self, pool):
        """Get the optimized dropoff sequence for the pool"""
        members = pool.members.all().order_by('dropoff_order')
        sequence = []
        
        for membership in members:
            ride_request = membership.ride_request
            sequence.append({
                'rider_name': ride_request.rider.get_full_name(),
                'destination_address': ride_request.destination_address,
                'latitude': float(ride_request.destination_latitude),
                'longitude': float(ride_request.destination_longitude),
                'order': membership.dropoff_order
            })
        
        return sequence
    
    # Keep your existing helper methods:
    def _calculate_pool_centroid(self, pool):
        """Calculate the centroid (average) of all pickup locations in the pool"""
        members = pool.members.all()
        if not members:
            return None
        
        total_lat = 0
        total_lng = 0
        count = 0
        
        for membership in members:
            ride_request = membership.ride_request
            total_lat += float(ride_request.pickup_latitude)
            total_lng += float(ride_request.pickup_longitude)
            count += 1
        
        return (total_lat / count, total_lng / count)
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula"""
        R = 6371000  # Earth radius in meters
        
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c