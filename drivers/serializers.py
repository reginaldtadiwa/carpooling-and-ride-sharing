# drivers/serializers.py
from rest_framework import serializers
from rides.models import Driver

class DriverSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Driver
        fields = '__all__'
        read_only_fields = ('user', 'rating', 'is_available')

class DriverRegistrationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', write_only=True)
    email = serializers.CharField(source='user.email', write_only=True)
    password = serializers.CharField(source='user.password', write_only=True)
    first_name = serializers.CharField(source='user.first_name', write_only=True)
    last_name = serializers.CharField(source='user.last_name', write_only=True)

    class Meta:
        model = Driver
        fields = [
            'username', 'email', 'password', 'first_name', 'last_name',
            'vehicle_type', 'license_plate', 'max_capacity'
        ]
        extra_kwargs = {
            'vehicle_type': {'required': True},
            'license_plate': {'required': True},
            'max_capacity': {'required': True},
        }

    def create(self, validated_data):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user_data = validated_data.pop('user')
        
        # Create user
        user = User.objects.create_user(
            username=user_data['username'],
            email=user_data['email'],
            password=user_data['password'],
            first_name=user_data.get('first_name', ''),
            last_name=user_data.get('last_name', '')
        )
        
        # Create driver profile
        driver = Driver.objects.create(user=user, **validated_data)
        return driver

    def validate_license_plate(self, value):
        """Validate license plate format"""
        if len(value) < 4:
            raise serializers.ValidationError("License plate seems too short")
        return value

    def validate_max_capacity(self, value):
        """Validate vehicle capacity"""
        if value < 2 or value > 8:
            raise serializers.ValidationError("Vehicle capacity must be between 2 and 8")
        return value