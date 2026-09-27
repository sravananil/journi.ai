from datetime import datetime, time, timedelta
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.restaurant import Restaurant
from app.schemas.response import MealSuggestion, TripResponse
from app.schemas.trip import TripRequest
from app.planner.timing import PlannerTiming


class MealSuggestionService:
    MEAL_WINDOWS = (
        ("Lunch", time(12, 30)),
        ("Dinner", time(19, 0)),
    )
    MEAL_DURATION_MINUTES = 60
    ACTIVITY_BUFFER_MINUTES = 15

    @staticmethod
    def enrich(
        response: TripResponse,
        db: Session,
        requested_city: str,
        dietary: List[str] | None = None,
        request: TripRequest | None = None,
    ) -> TripResponse:
        from app.models.city import City

        req_city_lower = requested_city.strip().lower()
        valid_destinations = [req_city_lower]
        db_city = db.query(City).filter(
            (City.name == requested_city)
            | (City.normalized_name == req_city_lower)
        ).first()

        if not db_city:
            for city in db.query(City).all():
                if city.aliases and req_city_lower in [
                    str(alias).lower() for alias in city.aliases
                ]:
                    db_city = city
                    break

        if db_city:
            valid_destinations.extend(
                [db_city.name.lower(), db_city.normalized_name.lower()]
            )
            if db_city.aliases:
                valid_destinations.extend(
                    str(alias).lower() for alias in db_city.aliases
                )

        restaurant_query = db.query(Restaurant).filter(
            func.lower(Restaurant.city).in_(valid_destinations)
        )
        if dietary and "vegetarian" in dietary:
            restaurant_query = restaurant_query.filter(
                Restaurant.is_pure_veg.is_(True)
            )
        available = restaurant_query.order_by(
            Restaurant.rating.desc(), Restaurant.id.asc()
        ).limit(max(20, len(response.days) * len(MealSuggestionService.MEAL_WINDOWS))).all()

        timing = PlannerTiming.from_environment()
        suggestions: List[MealSuggestion] = []
        for day in response.days:
            for meal_name, meal_start in MealSuggestionService.MEAL_WINDOWS:
                if not available:
                    break

                start = datetime.combine(day.date, meal_start)
                end = start + timedelta(
                    minutes=MealSuggestionService.MEAL_DURATION_MINUTES
                )
                if request:
                    day_start = datetime.combine(day.date, request.day_start)
                    if day.day == 1:
                        day_start = timing.earliest_start(request, day_start)
                    if start < day_start or end > timing.latest_end(request, day.day):
                        continue

                buffer = timedelta(
                    minutes=MealSuggestionService.ACTIVITY_BUFFER_MINUTES
                )
                conflicts = any(
                    start < (
                        datetime.combine(day.date, datetime.strptime(
                            activity.end_time, "%H:%M"
                        ).time()) + buffer
                    )
                    and end > (
                        datetime.combine(day.date, datetime.strptime(
                            activity.start_time, "%H:%M"
                        ).time()) - buffer
                    )
                    for activity in day.activities
                )
                if conflicts:
                    continue

                restaurant = available.pop(0)
                has_coordinates = (
                    restaurant.latitude is not None
                    and restaurant.longitude is not None
                )
                suggestions.append(
                    MealSuggestion(
                        meal=f"{meal_name} (Day {day.day})",
                        restaurant=restaurant.name,
                        cuisine=restaurant.cuisine or "Unknown",
                        price=restaurant.cost if restaurant.cost > 0 else None,
                        rating=restaurant.rating,
                        source=restaurant.source or "Unknown",
                        day=day.day,
                        start_time=meal_start.strftime("%H:%M"),
                        end_time=end.time().strftime("%H:%M"),
                        lat=restaurant.latitude if has_coordinates else None,
                        lng=restaurant.longitude if has_coordinates else None,
                        scheduled=True,
                    )
                )

        response.meal_suggestions = suggestions
        return response
