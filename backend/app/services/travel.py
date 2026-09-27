import math
from typing import Tuple

class TravelTimeService:
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great circle distance in kilometers between two points 
        on the earth (specified in decimal degrees)
        """
        # convert decimal degrees to radians 
        lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

        # haversine formula 
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a)) 
        r = 6371 # Radius of earth in kilometers
        return c * r

    @staticmethod
    def estimate_travel_time(lat1: float, lon1: float, lat2: float, lon2: float, mode: str = "car") -> int:
        """
        Estimates travel time in minutes based on distance and mode.
        Using a heuristic approach for the MVP.
        """
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return 0
            
        distance_km = TravelTimeService.haversine_distance(lat1, lon1, lat2, lon2)
        
        if distance_km < 0.1: # Less than 100m is essentially 0 mins travel
            return 0
            
        # Average speeds in km/h based on Goa traffic
        speeds = {
            "car": 30,
            "taxi": 30,
            "scooter/bike": 35, # slightly faster in traffic
            "walking + public transport": 15,
            "no preference": 30
        }
        
        speed_kmh = speeds.get(mode, 30)
        
        # Calculate base time
        time_hours = distance_km / speed_kmh
        time_minutes = math.ceil(time_hours * 60)
        
        # Add a fixed overhead for parking, getting out, etc. (e.g., 5 mins)
        overhead_minutes = 5
        
        return time_minutes + overhead_minutes
