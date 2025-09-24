# rides/models.py
from django.db import models
from django.contrib.auth import get_user_model
import math

User = get_user_model()

class RideRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('matched', 'Matched'),
        ('driver_assigned', 'Driver Assigned'),
        ('picked_up', 'Picked Up'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    rider = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # REPLACED PointField with separate lat/lng fields
    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_address = models.TextField()
    
    destination_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    destination_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    destination_address = models.TextField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    fare_estimate = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['pickup_latitude', 'pickup_longitude']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def distance_to(self, other_lat, other_lng):
        """Calculate distance to another point using Haversine formula"""
        return self.haversine_distance(
            float(self.pickup_latitude), 
            float(self.pickup_longitude),
            float(other_lat),
            float(other_lng)
        )
    
    @staticmethod
    def haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate great-circle distance between two points"""
        R = 6371000  # Earth radius in meters
        
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

class Pool(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('filled', 'Filled'),
        ('driver_assigned', 'Driver Assigned'),
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    max_riders = models.IntegerField(default=4)
    max_wait_time = models.IntegerField(default=10)  # minutes
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True)
    estimated_fare = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    
    # REMOVED: optimized_route = models.LineStringField

class PoolMembership(models.Model):
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name='members')
    ride_request = models.ForeignKey(RideRequest, on_delete=models.CASCADE)
    pickup_order = models.IntegerField(default=0)
    dropoff_order = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

class Driver(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    vehicle_type = models.CharField(max_length=50)
    license_plate = models.CharField(max_length=20)
    max_capacity = models.IntegerField(default=4)
    is_available = models.BooleanField(default=False)
    
    # REPLACED PointField with separate lat/lng
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.0)

class Trip(models.Model):
    pool = models.OneToOneField(Pool, on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE)
    start_time = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True)
    actual_fare = models.DecimalField(max_digits=8, decimal_places=2, null=True)