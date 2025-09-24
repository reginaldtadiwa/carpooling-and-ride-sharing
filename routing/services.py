# routing/services.py
import math

class RouteOptimizer:
    def __init__(self):
        self.max_detour_factor = 1.15
    
    def optimize_route(self, ride_requests):
        """
        Optimize pickup and dropoff sequence without GIS dependencies
        """
        if len(ride_requests) == 1:
            return self._simple_route(ride_requests[0])
        
        # Simplified route optimization
        # In production, integrate with external routing API
        sequence = self._generate_feasible_sequence(ride_requests)
        
        return self._assign_orders(sequence, ride_requests)
    
    def _generate_feasible_sequence(self, ride_requests):
        """Generate basic feasible sequence (pickup before dropoff)"""
        sequence = []
        for rr in ride_requests:
            sequence.append(('pickup', rr))
        for rr in ride_requests:
            sequence.append(('dropoff', rr))
        return sequence
    
    def _assign_orders(self, sequence, ride_requests):
        """Assign pickup and dropoff orders"""
        pickup_orders = {}
        dropoff_orders = {}
        
        pickup_counter = 1
        dropoff_counter = 1
        
        for action, ride_request in sequence:
            if action == 'pickup':
                pickup_orders[ride_request.id] = pickup_counter
                pickup_counter += 1
            else:
                dropoff_orders[ride_request.id] = dropoff_counter
                dropoff_counter += 1
        
        return {
            'sequence': sequence,
            'pickup_orders': pickup_orders,
            'dropoff_orders': dropoff_orders
        }
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points"""
        return self._haversine_distance(lat1, lon1, lat2, lon2)
    
    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Haversine distance calculation"""
        R = 6371000
        
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _simple_route(self, ride_request):
        """Simple route for single rider"""
        return {
            'sequence': [('pickup', ride_request), ('dropoff', ride_request)],
            'pickup_orders': {ride_request.id: 1},
            'dropoff_orders': {ride_request.id: 1}
        }