from app.schemas.response import TripResponse, ValidationResult, ValidationChecks
from app.schemas.trip import TripRequest
from app.models.place import Place
from typing import List
from datetime import datetime, timedelta
from app.planner.timing import PlannerTiming
from app.services.travel import TravelTimeService

class Validator:
    @staticmethod
    def validate(
        response: TripResponse,
        request: TripRequest,
        valid_candidates: List[Place],
        timing: PlannerTiming | None = None,
    ) -> TripResponse:
        timing = timing or PlannerTiming()
        checks = ValidationChecks(
            dates=True,
            schedule=True,
            opening_hours=False, # Data is missing for most, so we cannot verify it
            geography=True,
            budget=True,
            traveller_suitability=False, # Data is missing for most, cannot verify
            duplicates=True
        )
        
        # 1. Check dates
        if len(response.days) > response.trip.nights + 1:
            checks.dates = False
        expected_dates = {
            request.dates.start + timedelta(days=day_num - 1)
            for day_num in range(1, request.dates.nights + 2)
        }
        for day in response.days:
            if day.date not in expected_dates:
                checks.dates = False
            
        # 2. Check duplicates
        seen_places = set()
        for day in response.days:
            for act in day.activities:
                if act.place_id in seen_places:
                    checks.duplicates = False
                seen_places.add(act.place_id)
                
        # 3. Check schedule order and daily journey windows
        for day in response.days:
            day_start = datetime.combine(day.date, request.day_start)
            latest_end = timing.latest_end(request, day.day)
            previous_end = None
            for act in day.activities:
                start = datetime.combine(day.date, datetime.strptime(act.start_time, "%H:%M").time())
                end = datetime.combine(day.date, datetime.strptime(act.end_time, "%H:%M").time())
                if end <= start or start < day_start or end > latest_end:
                    checks.schedule = False
                if previous_end and start < previous_end + timedelta(
                    minutes=act.travel_minutes + 15
                ):
                    checks.schedule = False
                previous_end = end

                if act.lat is not None and act.lng is not None and TravelTimeService.haversine_distance(
                    request.destination.lat,
                    request.destination.lng,
                    act.lat,
                    act.lng,
                ) > timing.max_place_distance_km:
                    checks.geography = False
                
                # Check opening hours if data exists, but we already set opening_hours=False 
                # as a general limitation. We can still penalize if it blatantly violates known data.
                place_obj = next((p for p in valid_candidates if p.id == act.place_id), None)
                if place_obj and place_obj.opening_hours:
                    open_t = datetime.strptime(place_obj.opening_hours['open'], "%H:%M").time()
                    close_t = datetime.strptime(place_obj.opening_hours['close'], "%H:%M").time()
                    
                    # Also handle rollover for close times like 03:00 AM
                    if start.time() < open_t and not (start.time().hour <= 4 and close_t.hour <= 4):
                        checks.opening_hours = False
                    if end.time() > close_t and close_t.hour > 5:
                        checks.opening_hours = False

            if day.day == 1 and day.activities:
                first_start = datetime.combine(
                    day.date, datetime.strptime(day.activities[0].start_time, "%H:%M").time()
                )
                if first_start < timing.earliest_start(request, day_start):
                    checks.schedule = False

        # Budget Check
        if request.budget.value == "budget" and response.summary.estimated_cost > 15000:
            checks.budget = False
            
        # The itinerary passes if dates, schedule, geography, budget, and duplicates are fine.
        # We don't fail the trip for missing opening hours or suitability because the data is UNKNOWN.
        passed = all([
            checks.dates, checks.schedule, checks.geography, checks.budget, checks.duplicates
        ])
        
        response.validation = ValidationResult(
            passed=passed,
            checks=checks
        )
        
        return response
