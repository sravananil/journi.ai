from sqlalchemy.orm import Session
from app.schemas.trip import TripRequest
from app.schemas.response import TripResponse, TripInfo, TripSummary, JourneySummary, ValidationResult, ValidationChecks
from app.planner.tracer import PlannerTracer
from app.planner.retrieval import CandidateRetrieval
from app.planner.constraints import HardConstraintEngine
from app.planner.scoring import ScoringEngine
from app.planner.geography import GeographicPlanner
from app.planner.scheduler import DailyScheduler
from app.planner.timing import PlannerTiming
from app.planner.recommendations import RecommendationService, RecommendationSettings, daily_activity_target
from app.validation.validator import Validator

class PlanningEngine:
    def __init__(self, db: Session):
        self.db = db
        self.tracer = PlannerTracer()
        self.timing = PlannerTiming.from_environment()
        
        self.retrieval = CandidateRetrieval(db, self.tracer)
        self.constraints = HardConstraintEngine(self.tracer, self.timing)
        self.scoring = ScoringEngine(self.tracer)
        self.geography = GeographicPlanner(self.tracer)
        self.scheduler = DailyScheduler(self.tracer, self.timing)
        self.recommendation_settings = RecommendationSettings.from_environment()
        self.recommendations = RecommendationService(self.timing, self.recommendation_settings)

    def plan_trip(self, request: TripRequest, refinement_context: dict = None) -> TripResponse:
        self.tracer.add_trace("Engine", "Start", f"Planning trip to {request.destination.city}")
        
        # 1. Retrieval
        candidates = self.retrieval.retrieve(request)
        
        # 2. Hard Constraints
        valid_candidates = self.constraints.filter_candidates(request, candidates)
        
        # 3. Scoring & Ranking
        scored_candidates = self.scoring.score_candidates(request, valid_candidates)
        
        # Bounded Repair Loop
        max_attempts = 3
        repair_context = {"reduce_density": False, "reduce_distance": False}
        if refinement_context and refinement_context.get("action") == "reduce_day_density":
            repair_context["reduce_density"] = True
            
        best_response = None
        
        for attempt in range(max_attempts):
            self.tracer.add_trace("Engine", "Attempt", f"Planning attempt {attempt + 1}")
            
            # 4. Geographic Planning
            num_days = request.dates.nights + 1
            daily_clusters = self.geography.cluster_places_for_days(request, scored_candidates, num_days, repair_context)
            if refinement_context and refinement_context.get("action") == "add_recommendation":
                target_day = int(refinement_context["target_day"])
                target_place_id = str(refinement_context["place_id"])
                target_place = next(
                    (place for place in valid_candidates if place.id == target_place_id),
                    None,
                )
                if target_place is None:
                    raise ValueError("The selected recommendation is not available in the JOURNI dataset.")
                for clustered_places in daily_clusters.values():
                    clustered_places[:] = [
                        place for place in clustered_places if place.id != target_place_id
                    ]
                daily_clusters[target_day].append(target_place)
            
            # 5. Scheduling
            itineraries = self.scheduler.schedule(request, daily_clusters)
            
            # Calculate summary
            total_cost = 0
            total_travel_mins = 0
            major_activities = 0
            
            for day in itineraries:
                for act in day.activities:
                    total_cost += act.estimated_cost
                    total_travel_mins += act.travel_minutes
                    major_activities += 1
                    
            summary = TripSummary(
                estimated_cost=total_cost,
                major_activities=major_activities,
                estimated_travel_time=total_travel_mins
            )
            
            trip_info = TripInfo(
                destination=request.destination.city,
                start_date=request.dates.start,
                end_date=request.dates.end,
                nights=request.dates.nights
            )
            
            response = TripResponse(
                trip=trip_info,
                days=itineraries,
                summary=summary,
                    assumptions=[
                        "Local travel estimates exclude the intercity journey and the first leg from assumed lodging each day.",
                        "Travel times within the destination are straight-line distance heuristics, not live routes or transit schedules.",
                ],
                evidence=[
                    {"label": "Attraction names & categories", "value": "FACT", "source": "Dataset", "notes": "Verified from database."},
                    {"label": "Destination & Coordinates", "value": "FACT", "source": "Dataset", "notes": "Used for map placement."},
                    {"label": "Travel distance & duration", "value": "DERIVED", "source": "Calculated", "notes": "Estimated travel time based on geographic distance; live traffic and routing are not available."},
                    {"label": "Itinerary grouping", "value": "DERIVED", "source": "Calculated", "notes": "Grouped by geographic proximity."},
                    {"label": "Total estimated cost", "value": "DERIVED", "source": "Calculated", "notes": "Aggregated from individual place cost estimates."},
                    {"label": "Opening hours", "value": "UNKNOWN", "source": "None", "notes": "Structured opening hours are not reliably available; not verified."},
                    {"label": "Traveller suitability", "value": "UNKNOWN", "source": "None", "notes": "Per-attraction suitability for demographics is not reliably available."},
                    {"label": "Accessibility & walking", "value": "UNKNOWN", "source": "None", "notes": "Walking difficulty and accessibility are not verified."},
                    {"label": "Live traffic & transit", "value": "UNKNOWN", "source": "None", "notes": "No live routing or transit data connected."},
                    {"label": "Hotel & flight availability", "value": "UNKNOWN", "source": "None", "notes": "No live hotel or flight inventory connected."},
                    {"label": "Restaurant availability", "value": "UNKNOWN", "source": "None", "notes": "Dataset does not provide real-time availability or open status."}
                ],
                validation=ValidationResult(passed=False)
            )

            if request.journey:
                journey_minutes = None
                if request.journey.departure_at and request.journey.arrival_at:
                    journey_minutes = int(
                        (request.journey.arrival_at - request.journey.departure_at).total_seconds() // 60
                    )
                response.journey = JourneySummary(
                    transport=request.journey.transport.value,
                    status=request.journey.status.value,
                    departure_at=request.journey.departure_at,
                    arrival_at=request.journey.arrival_at,
                    duration_minutes=journey_minutes,
                )
                response.assumptions.append(
                    "The intercity journey is kept separate from local itinerary activities; user-provided journey times are unchanged."
                )
                if request.journey.arrival_at:
                    response.assumptions.append(
                        f"The first activity starts no earlier than the provided arrival plus the {self.timing.arrival_buffer_minutes}-minute planning buffer."
                    )
                    response.assumptions.append(
                        "No independent intercity route estimate is available for comparison with the user-entered journey duration."
                    )
            if not request.journey or not request.journey.arrival_at:
                response.assumptions.append(
                    f"The intercity journey from {request.origin.city} to {request.destination.city} is not scheduled as a local activity. No exact outbound journey times were provided; the {request.arrival.value} arrival period is conservatively assumed to end at {self.timing.describe_arrival_assumption(request.arrival)}, followed by a {self.timing.arrival_buffer_minutes}-minute buffer."
                )
            response.assumptions.append(
                f"No exact return journey was provided. The final day's {request.departure.value} departure period is conservatively planned from {self.timing.describe_departure_assumption(request.departure)}, with a {self.timing.departure_buffer_minutes}-minute buffer."
            )
            if self.constraints.excluded_location_count:
                response.assumptions.append(
                    f"{self.constraints.excluded_location_count} places more than {self.timing.max_place_distance_km:g} km from the destination center were excluded from local planning."
                )
            if self.constraints.unknown_location_count:
                response.assumptions.append(
                    f"{self.constraints.unknown_location_count} places have no usable coordinates; their local travel cannot be estimated or mapped."
                )
            # 6. Validation
            response = Validator.validate(response, request, valid_candidates, self.timing)
            
            best_response = response
            if response.validation.passed:
                self.tracer.add_trace("Engine", "Complete", f"Trip validated successfully on attempt {attempt + 1}")
                break
            else:
                self.tracer.add_trace("Engine", "Repair", f"Validation failed on attempt {attempt + 1}. Applying repair strategies.")
                if not response.validation.checks.schedule:
                    repair_context["reduce_density"] = True
                if not response.validation.checks.geography:
                    repair_context["reduce_distance"] = True
                
                response.assumptions.append(f"Itinerary degraded: Validation failed on attempt {attempt + 1}.")
        # 7. Restaurant Enrichment
        from app.planner.meal_service import MealSuggestionService
        best_response = MealSuggestionService.enrich(
            best_response, self.db, request.destination.city, request.dietary, request
        )
        best_response.summary.meal_cost = sum(
            meal.price or 0 for meal in best_response.meal_suggestions
        )
        best_response.summary.estimated_known_total = (
            best_response.summary.estimated_cost + best_response.summary.meal_cost
        )
        if best_response.meal_suggestions and not any(
            meal.lat is not None and meal.lng is not None
            for meal in best_response.meal_suggestions
        ):
            best_response.assumptions.append(
                "Restaurant suggestions have no coordinates in the dataset; their travel time and map location are unknown and are not included in the activity route."
            )
            best_response.evidence.append(
                {
                    "label": "Restaurant location and travel",
                    "value": "UNKNOWN",
                    "source": "Restaurant dataset",
                    "notes": "No restaurant coordinates are available, so local travel and map positions are not inferred.",
                }
            )
        if best_response.meal_suggestions:
            best_response.assumptions.append(
                "Restaurant cost estimates are shown as supplied by the dataset; serving basis and real-time prices are not verified."
            )
            best_response.evidence.append(
                {
                    "label": "Suggested restaurant cost",
                    "value": "DERIVED",
                    "source": "Restaurant dataset",
                    "notes": "The known restaurant cost records are summed as displayed estimates; serving basis and current prices are unverified.",
                }
            )
        unverified_dietary = [
            preference for preference in request.dietary
            if preference != "vegetarian"
        ]
        if unverified_dietary:
            best_response.assumptions.append(
                f"Dietary preferences {', '.join(unverified_dietary)} are recorded, but restaurant dataset fields cannot verify them."
            )
        if self.scheduler.skipped_activities:
            best_response.assumptions.append(
                f"{self.scheduler.skipped_activities} stops were omitted because travel and activity time did not fit within the daily planning windows."
            )

        target_per_day = daily_activity_target(request)
        place_shortage = len(valid_candidates) < len(best_response.days) * target_per_day
        for day in best_response.days:
            day.limited_activities = (
                place_shortage and len(day.activities) < target_per_day
            )
            day.recommendations = self.recommendations.for_day(
                request, best_response, day, scored_candidates
            )
        if place_shortage:
            best_response.assumptions.append(
                f"The destination dataset has {len(valid_candidates)} suitable places for a trip paced at about {target_per_day} activities per day across {len(best_response.days)} days. Some days may have limited suitable options; no places were invented or duplicated."
            )
        
        return best_response

    def recommendations_for_day(
        self,
        request: TripRequest,
        response: TripResponse,
        day_number: int,
    ):
        candidates = self.retrieval.retrieve(request)
        valid_candidates = self.constraints.filter_candidates(request, candidates)
        scored_candidates = self.scoring.score_candidates(request, valid_candidates)
        day = next((item for item in response.days if item.day == day_number), None)
        if day is None:
            raise ValueError("The requested itinerary day does not exist.")
        return self.recommendations.for_day(request, response, day, scored_candidates)
