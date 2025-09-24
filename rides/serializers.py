# rides/serializers.py
from rest_framework import serializers
from .models import RideRequest, Pool, Trip, PoolMembership

class RideRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideRequest
        fields = '__all__'
        read_only_fields = ('rider', 'status', 'created_at', 'updated_at')

class PoolMembershipSerializer(serializers.ModelSerializer):
    rider_name = serializers.CharField(source='ride_request.rider.get_full_name', read_only=True)
    
    class Meta:
        model = PoolMembership
        fields = ('id', 'rider_name', 'pickup_order', 'dropoff_order', 'joined_at')

class PoolSerializer(serializers.ModelSerializer):
    members = PoolMembershipSerializer(many=True, read_only=True)
    current_riders = serializers.SerializerMethodField()

    class Meta:
        model = Pool
        fields = '__all__'

    def get_current_riders(self, obj):
        return obj.members.count()

class TripSerializer(serializers.ModelSerializer):
    pool_details = PoolSerializer(source='pool', read_only=True)
    driver_name = serializers.CharField(source='driver.user.get_full_name', read_only=True)

    class Meta:
        model = Trip
        fields = '__all__'