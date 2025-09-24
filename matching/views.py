# matching/views.py
from time import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rides.models import RideRequest
from .services import PoolMatchingService
from rides.serializers import RideRequestSerializer

class MatchPreviewView(APIView):
    """Preview potential matches for a ride request"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RideRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create temporary ride request for matching preview
        temp_ride_request = RideRequest(
            pickup_latitude=serializer.validated_data['pickup_latitude'],
            pickup_longitude=serializer.validated_data['pickup_longitude'],
            destination_latitude=serializer.validated_data['destination_latitude'],
            destination_longitude=serializer.validated_data['destination_longitude'],
        )
        
        matching_service = PoolMatchingService()
        matching_pools = matching_service.find_matching_pools(temp_ride_request)
        
        preview_data = {
            'total_matching_pools': len(matching_pools),
            'estimated_wait_time': '2-5 minutes' if matching_pools else '5-10 minutes',
            'estimated_fare_savings': '40-60%' if matching_pools else '20-40%',
            'matching_pools': []
        }
        
        for pool in matching_pools[:3]:  # Show top 3 matches
            preview_data['matching_pools'].append({
                'pool_id': pool.id,
                'current_riders': pool.members.count(),
                'time_elapsed_minutes': (timezone.now() - pool.created_at).total_seconds() / 60,
                'estimated_detour_minutes': 5  # Simplified estimation
            })
        
        return Response(preview_data)