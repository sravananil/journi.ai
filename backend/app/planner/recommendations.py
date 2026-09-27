import os
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Sequence

from app.models.place import Place
from app.planner.scoring import ScoringEngine
from app.planner.timing import PlannerTiming
from app.planner.tracer import PlannerTracer
from app.schemas.response import DailyItinerary, NearbyRecommendation, TripResponse
from app.schemas.trip import TripRequest, Transport
from app.services.travel import TravelTimeService


@dataclass(frozen=True)
class RecommendationSettings:
    car_radius_km: float = 10.0
    evening_car_radius_km: float = 7.0
    taxi_radius_km: float = 12.0
    public_transport_radius_km: float = 8.0
    walking_public_radius_km: float = 5.0
    no_preference_radius_km: float = 8.0
    evening_radius_factor: float = 0.7
    limit: int = 3

    @classmethod
    def from_environment(cls) -> "RecommendationSettings":
        settings = cls(
            car_radius_km=float(os.getenv("JOURNI_RECOMMENDATION_CAR_RADIUS_KM", "10")),
            evening_car_radius_km=float(os.getenv("JOURNI_RECOMMENDATION_EVENING_CAR_RADIUS_KM", "7")),
            taxi_radius_km=float(os.getenv("JOURNI_RECOMMENDATION_TAXI_RADIUS_KM", "12")),
            public_transport_radius_km=float(os.getenv("JOURNI_RECOMMENDATION_PUBLIC_RADIUS_KM", "8")),
            walking_public_radius_km=float(os.getenv("JOURNI_RECOMMENDATION_WALKING_RADIUS_KM", "5")),
            no_preference_radius_km=float(os.getenv("JOURNI_RECOMMENDATION_DEFAULT_RADIUS_KM", "8")),
        )
        if any(value <= 0 for value in (
            settings.car_radius_km,
            settings.evening_car_radius_km,
            settings.taxi_radius_km,
            settings.public_transport_radius_km,
            settings.walking_public_radius_km,
            settings.no_preference_radius_km,
        )):
            raise ValueError("JOURNI recommendation radii must be greater than zero.")
        if settings.evening_car_radius_km > settings.car_radius_km:
            raise ValueError("JOURNI evening recommendation radius cannot exceed the daytime radius.")
        return settings

    def radius_for(self, transport: Transport, current_time: time) -> float:
        if transport in {Transport.CAR, Transport.SCOOTER}:
            base = self.car_radius_km
            return min(base, self.evening_car_radius_km) if time(17, 0) <= current_time < time(19, 0) else base
        if transport == Transport.TAXI:
            base = self.taxi_radius_km
        elif transport == Transport.PUBLIC:
            base = self.public_transport_radius_km
        elif transport == Transport.WALKING_PUBLIC:
            base = self.walking_public_radius_km
        else:
            base = self.no_preference_radius_km
        return base * self.evening_radius_factor if time(17, 0) <= current_time < time(19, 0) else base


def daily_activity_target(request: TripRequest) -> int:
    return {"easy-going": 3, "balanced": 4, "packed": 6}[request.pace.value]


class RecommendationService:
    def __init__(
        self,
        timing: PlannerTiming,
        settings: RecommendationSettings | None = None,
    ):
        self.timing = timing
        self.settings = settings or RecommendationSettings.from_environment()

    @staticmethod
    def _known_opening_hours_fit(place: Place, arrival: datetime, duration: int) -> bool:
        if not place.opening_hours:
            return True
        try:
            opening = time.fromisoformat(place.opening_hours["open"])
            closing = time.fromisoformat(place.opening_hours["close"])
        except (KeyError, TypeError, ValueError):
            return False
        end = arrival + timedelta(minutes=duration)
        if closing <= opening:
            return True
        return arrival.time() >= opening and end.time() <= closing

    def for_day(
        self,
        request: TripRequest,
        itinerary: TripResponse,
        day: DailyItinerary,
        candidates: Sequence[tuple[Place, float]],
        limit: int | None = None,
    ) -> list[NearbyRecommendation]:
        if len(day.activities) >= daily_activity_target(request):
            return []
        day_end = self.timing.latest_end(request, day.day)
        if day.activities:
            last_activity = day.activities[-1]
            if last_activity.lat is not None and last_activity.lng is not None:
                anchor = (last_activity.lat, last_activity.lng)
            else:
                anchor = (request.destination.lat, request.destination.lng)
            current_time = datetime.combine(
                day.date, time.fromisoformat(last_activity.end_time)
            ) + timedelta(minutes=15)
        else:
            anchor = (request.destination.lat, request.destination.lng)
            current_time = datetime.combine(day.date, request.day_start)
            if day.day == 1:
                current_time = self.timing.earliest_start(request, current_time)

        visited_ids = {
            activity.place_id
            for planned_day in itinerary.days
            for activity in planned_day.activities
        }
        recommendations: list[tuple[float, float, NearbyRecommendation]] = []
        desired_limit = self.settings.limit if limit is None else limit

        for place, score in candidates:
            if place.id in visited_ids or place.latitude is None or place.longitude is None:
                continue
            if (
                request.budget.value == "budget"
                and itinerary.summary.estimated_cost + (place.estimated_cost or 0) > 15000
            ):
                continue
            distance = TravelTimeService.haversine_distance(
                anchor[0], anchor[1], place.latitude, place.longitude
            )
            travel_minutes = TravelTimeService.estimate_travel_time(
                anchor[0], anchor[1], place.latitude, place.longitude, request.transport.value
            )
            arrival = current_time + timedelta(minutes=travel_minutes)
            radius_time = current_time.time()
            if not (time(17, 0) <= radius_time < time(19, 0)) and (
                time(17, 0) <= arrival.time() < time(19, 0)
            ):
                radius_time = arrival.time()
            radius = self.settings.radius_for(request.transport, radius_time)
            if distance > radius:
                continue

            duration = max(30, place.duration or 60)
            return_minutes = TravelTimeService.estimate_travel_time(
                place.latitude, place.longitude, anchor[0], anchor[1], request.transport.value
            )
            if (
                arrival + timedelta(minutes=duration + return_minutes + 15) > day_end
                or not self._known_opening_hours_fit(place, arrival, duration)
            ):
                continue

            matched_interests = [
                interest for interest in (place.interests or [])
                if interest in request.interests
            ]
            reason = (
                f"Matches your {', '.join(matched_interests[:2])} interests."
                if matched_interests
                else "A nearby JOURNI dataset place that fits the remaining day."
            )
            recommendation = NearbyRecommendation(
                place_id=place.id,
                name=place.name,
                category=place.category,
                distance_km=round(distance, 1),
                travel_minutes=travel_minutes,
                reason=reason,
                source=place.source,
            )
            distance_penalty = distance * 0.1
            recommendations.append((score - distance_penalty, distance, recommendation))

        recommendations.sort(key=lambda item: (-item[0], item[1], item[2].place_id))
        return [item[2] for item in recommendations[:desired_limit]]


def rank_candidates(
    request: TripRequest,
    candidates: Sequence[Place],
    tracer: PlannerTracer,
) -> list[tuple[Place, float]]:
    return ScoringEngine(tracer).score_candidates(request, list(candidates))
