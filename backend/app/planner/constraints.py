from typing import List
from app.models.place import Place
from app.schemas.trip import TripRequest
from app.planner.tracer import PlannerTracer
from app.planner.timing import PlannerTiming
from app.services.travel import TravelTimeService

class HardConstraintEngine:
    def __init__(self, tracer: PlannerTracer, timing: PlannerTiming | None = None):
        self.tracer = tracer
        self.timing = timing or PlannerTiming()
        self.excluded_location_count = 0
        self.unknown_location_count = 0

    def filter_candidates(self, request: TripRequest, candidates: List[Place]) -> List[Place]:
        self.excluded_location_count = 0
        self.unknown_location_count = 0
        valid_candidates = []
        rejected = []

        for place in candidates:
            # 1. Traveller suitability constraint
            if place.suitable_for is not None and request.travellers.type.value not in place.suitable_for:
                rejected.append({"id": place.id, "reason": "Traveller type not suitable"})
                continue
                
            # 2. Avoid constraints
            # e.g., if "late_nights" is in avoid and place category is nightlife
            if "late_nights" in request.avoid and place.category == "nightlife":
                rejected.append({"id": place.id, "reason": "User avoids late nights"})
                continue
            
            # Reject if place category is in avoid list
            if place.category in request.avoid:
                rejected.append({"id": place.id, "reason": f"User avoids category: {place.category}"})
                continue
            
            # 3. Walking tolerance
            if request.walking_tolerance.value == "low" and place.walking_level == "high":
                rejected.append({"id": place.id, "reason": "Walking level too high"})
                continue

            # Unlocated and distant records cannot support a reliable local route.
            if place.latitude is None or place.longitude is None:
                self.unknown_location_count += 1
                valid_candidates.append(place)
                continue

            if not (6.0 <= place.latitude <= 36.0) or not (68.0 <= place.longitude <= 98.0):
                place.latitude = None
                place.longitude = None
                self.unknown_location_count += 1
                valid_candidates.append(place)
                continue

            distance_from_destination = TravelTimeService.haversine_distance(
                request.destination.lat,
                request.destination.lng,
                place.latitude,
                place.longitude,
            )
            if distance_from_destination > self.timing.max_place_distance_km:
                self.excluded_location_count += 1
                rejected.append({"id": place.id, "reason": "Outside destination planning area"})
                continue

            valid_candidates.append(place)

        self.tracer.add_trace(
            stage="Hard Constraints",
            action="Filter candidates",
            details=f"Retained {len(valid_candidates)}, rejected {len(rejected)}. Rejections: {rejected}"
        )
        return valid_candidates
