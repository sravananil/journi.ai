from typing import List, Dict
from datetime import datetime, timedelta
from app.models.place import Place
from app.schemas.trip import TripRequest
from app.schemas.response import DailyItinerary, Activity
from app.services.travel import TravelTimeService
from app.planner.tracer import PlannerTracer
from app.planner.timing import PlannerTiming

class DailyScheduler:
    def __init__(self, tracer: PlannerTracer, timing: PlannerTiming | None = None):
        self.tracer = tracer
        self.timing = timing or PlannerTiming()
        self.skipped_activities = 0

    def schedule(
        self, 
        request: TripRequest, 
        daily_clusters: Dict[int, List[Place]]
    ) -> List[DailyItinerary]:
        
        itineraries = []
        trip_start_date = request.dates.start
        self.skipped_activities = 0
        
        for day_num, places in daily_clusters.items():
            current_date = trip_start_date + timedelta(days=day_num - 1)
            current_time = datetime.combine(current_date, request.day_start)
            if day_num == 1:
                current_time = self.timing.earliest_start(request, current_time)
            latest_end = self.timing.latest_end(request, day_num)
            activities = []
            last_location = None
            
            for place in places:
                travel_mins = 0
                if last_location:
                    travel_mins = TravelTimeService.estimate_travel_time(
                        last_location[0], last_location[1], 
                        place.latitude, place.longitude, 
                        request.transport.value
                    )
                proposed_start = current_time + timedelta(minutes=travel_mins)
                duration = place.duration or 60
                if place.opening_hours:
                    open_t = datetime.strptime(place.opening_hours['open'], "%H:%M").time()
                    close_t = datetime.strptime(place.opening_hours['close'], "%H:%M").time()
                    if proposed_start.time() < open_t:
                        proposed_start = proposed_start.replace(
                            hour=open_t.hour, minute=open_t.minute, second=0, microsecond=0
                        )
                    if close_t.hour > 5 and (
                        proposed_start + timedelta(minutes=duration)
                    ).time() > close_t:
                        self.skipped_activities += 1
                        continue

                proposed_end = proposed_start + timedelta(minutes=duration)
                if proposed_start.date() != current_date or proposed_end > latest_end:
                    self.skipped_activities += 1
                    continue

                start_time_str = proposed_start.strftime("%H:%M")
                end_time_str = proposed_end.strftime("%H:%M")
                
                activities.append(Activity(
                    place_id=place.id,
                    name=place.name,
                    start_time=start_time_str,
                    end_time=end_time_str,
                    duration_minutes=duration,
                    category=place.category,
                    estimated_cost=place.estimated_cost or 0,
                    travel_minutes=travel_mins,
                    reason=f"Selected for its {place.category} matching your profile.",
                    image_url=None,
                    lat=place.latitude,
                    lng=place.longitude,
                    source=place.source
                ))
                
                last_location = (place.latitude, place.longitude)
                current_time = proposed_end + timedelta(minutes=15)
                
            theme_str = ", ".join(list(set(p.area for p in places if p.area)))
            
            itineraries.append(DailyItinerary(
                day=day_num,
                date=current_date,
                theme=f"Exploring {theme_str}",
                activities=activities
            ))
            
        self.tracer.add_trace(
            stage="Scheduler",
            action="Build Timeline",
            details=(
                f"Scheduled {len(itineraries)} days; "
                f"omitted {self.skipped_activities} stops outside the available daily window."
            )
        )
        return itineraries
