from typing import List, Dict, Tuple
from app.models.place import Place
from app.schemas.trip import TripRequest
from app.services.travel import TravelTimeService
from app.planner.tracer import PlannerTracer
from app.planner.recommendations import daily_activity_target

class GeographicPlanner:
    def __init__(self, tracer: PlannerTracer):
        self.tracer = tracer

    def cluster_places_for_days(
        self, 
        request: TripRequest, 
        scored_candidates: List[Tuple[Place, float]], 
        num_days: int,
        repair_context: Dict[str, bool] = None
    ) -> Dict[int, List[Place]]:
        """
        Groups places into daily clusters based on coordinate distance.
        Uses a greedy approach starting from the highest scored places.
        """
        daily_clusters: Dict[int, List[Place]] = {day: [] for day in range(1, num_days + 1)}
        
        # We need to select enough places for the trip.
        # Say, average 3-5 places per day depending on pace
        target_places_per_day = daily_activity_target(request)
            
        if repair_context and repair_context.get("reduce_density"):
            target_places_per_day = max(2, target_places_per_day - 1)
            
        total_places_needed = min(num_days * target_places_per_day, len(scored_candidates))
        selected_places = [p for p, _ in scored_candidates[:total_places_needed]]
        
        if not selected_places:
            return daily_clusters

        unassigned = list(selected_places)
        
        for day in range(1, num_days + 1):
            if not unassigned:
                break
                
            # Start the day's cluster with the highest scored unassigned place
            seed_place = unassigned.pop(0)
            cluster = [seed_place]
            
            # Find closest places to fill the day
            places_to_find = min(target_places_per_day - 1, len(unassigned))
            
            for _ in range(places_to_find):
                if not unassigned:
                    break
                    
                # Find the closest unassigned place to the LAST place in the current cluster
                last_place = cluster[-1]
                closest_place = None
                min_distance = float('inf')
                
                for candidate in unassigned:
                    if last_place.latitude is None or last_place.longitude is None or candidate.latitude is None or candidate.longitude is None:
                        dist = float('inf')
                    else:
                        dist = TravelTimeService.haversine_distance(
                            last_place.latitude, last_place.longitude,
                            candidate.latitude, candidate.longitude
                        )
                    
                    # Area acts as a tie-breaker or slight distance reducer heuristic
                    if last_place.area == candidate.area:
                        dist *= 0.8 # 20% penalty reduction if in same area
                        
                    if dist < min_distance:
                        min_distance = dist
                        closest_place = candidate
                        
                if closest_place:
                    cluster.append(closest_place)
                    unassigned.remove(closest_place)
                    
            daily_clusters[day] = cluster
            
        self.tracer.add_trace(
            stage="Geographic Planning",
            action="Cluster by distance",
            details=f"Formed {num_days} clusters. Day 1 has {len(daily_clusters.get(1, []))} places."
        )
        return daily_clusters
