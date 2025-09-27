# routing/services.py
import math
import logging

logger = logging.getLogger(__name__)

class RouteOptimizer:
    def __init__(self):
        self.max_detour_factor = 1.15
    
    def optimize_route(self, ride_requests):
        """
        Optimize pickup and dropoff sequence without GIS dependencies
        """
        logger.info(f"optimize_route called with {len(ride_requests)} requests")
        
        if len(ride_requests) == 1:
            result = self._simple_route(ride_requests[0])
            logger.info(f"_simple_route result: {result}")
            return result
        
        # Simplified route optimization
        sequence = self._generate_feasible_sequence(ride_requests)
        logger.info(f"_generate_feasible_sequence result: {sequence}")
        
        result = self._assign_orders(sequence, ride_requests)
        logger.info(f"inal optimize_route result: {result}")
        return result
    
    def _generate_feasible_sequence(self, ride_requests):
        """Generate basic feasible sequence (pickup before dropoff)"""
        logger.info(f"_generate_feasible_sequence for {len(ride_requests)} requests")
        sequence = []
        
        # Add all pickups first
        for rr in ride_requests:
            sequence.append((rr, True))   # (RideRequest, is_pickup=True)
            logger.info(f"Added pickup for request {rr.id}")
        
        # Then add all dropoffs
        for rr in ride_requests:
            sequence.append((rr, False))  # (RideRequest, is_pickup=False)
            logger.info(f"Added dropoff for request {rr.id}")
        
        logger.info(f"Sequence length: {len(sequence)}")
        return sequence
    
    def _assign_orders(self, sequence, ride_requests):
        """Assign pickup and dropoff orders"""
        logger.info(f"_assign_orders for {len(ride_requests)} requests")
        
        pickup_orders = {}
        dropoff_orders = {}
        
        pickup_counter = 1
        dropoff_counter = 1
        
        # Count unique ride requests for ordering
        for ride_request in ride_requests:
            pickup_orders[ride_request.id] = pickup_counter
            dropoff_orders[ride_request.id] = dropoff_counter
            pickup_counter += 1
            dropoff_counter += 1
        
        result = {
            'sequence': sequence,
            'pickup_orders': pickup_orders,
            'dropoff_orders': dropoff_orders,
            'total_distance': self._calculate_total_distance(ride_requests)
        }
        logger.info(f"_assign_orders returning: {result}")
        return result
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points"""
        return self._haversine_distance(lat1, lon1, lat2, lon2)
    
    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Haversine distance calculation"""
        R = 6371000  # Earth radius in meters
        
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _calculate_total_distance(self, ride_requests):
        """Calculate total distance for multiple ride requests"""
        if not ride_requests:
            return 0
        
        # Simple estimation: use the distance of the first request
        # In production, this would use proper route optimization
        rr = ride_requests[0]
        distance = self._haversine_distance(
            float(rr.pickup_latitude), float(rr.pickup_longitude),
            float(rr.destination_latitude), float(rr.destination_longitude)
        )
        
        logger.info(f"Estimated total distance: {distance:.2f}m")
        return distance
    
    def _simple_route(self, ride_request):
        """Simple route for single rider"""
        logger.info(f"_simple_route for request {ride_request.id}")
        
        result = {
            'sequence': [
                (ride_request, True),   # Pickup
                (ride_request, False)   # Dropoff
            ],
            'pickup_orders': {ride_request.id: 1},
            'dropoff_orders': {ride_request.id: 1},
            'total_distance': self._calculate_single_distance(ride_request)
        }
        logger.info(f"_simple_route returning: {result}")
        return result
    
    def _calculate_single_distance(self, ride_request):
        """Calculate distance for a single ride request"""
        distance = self._haversine_distance(
            float(ride_request.pickup_latitude), float(ride_request.pickup_longitude),
            float(ride_request.destination_latitude), float(ride_request.destination_longitude)
        )
        logger.info(f"Single ride distance: {distance:.2f}m")
        return distance