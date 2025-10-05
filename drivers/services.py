# drivers/services.py
import math
from django.utils import timezone
from rides.models import Pool, Driver 

class DriverAssignmentService:
    def __init__(self):
        self.max_assignment_distance = 10000  # 10km in meters
    
    def find_best_driver(self, pool):
        """Find the nearest available driver for a pool"""
        # Get pool's centroid (average of all pickup locations)
        pool_centroid = self._calculate_pool_centroid(pool)
        if not pool_centroid:
            return None
        
        # Find available drivers with sufficient capacity
        available_drivers = Driver.objects.filter(
            is_available=True,
            max_capacity__gte=pool.members.count()
        )
        
        if not available_drivers:
            return None
        
        # Find the closest driver
        best_driver = None
        min_distance = float('inf')
        
        for driver in available_drivers:
            if driver.current_latitude and driver.current_longitude:
                distance = self._calculate_distance(
                    pool_centroid[0], pool_centroid[1],
                    float(driver.current_latitude), float(driver.current_longitude)
                )
                
                if distance < min_distance and distance <= self.max_assignment_distance:
                    min_distance = distance
                    best_driver = driver
        
        return best_driver
    
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