import pytest
from app.db.database import SessionLocal
from app.schemas.trip import TripRequest, Location, Dates, Travellers, Pace, Budget, Transport, TimeOfDay, WalkingTolerance
from app.schemas.response import Activity, TripResponse, TripInfo, TripSummary, ValidationResult, DailyItinerary
from app.planner.meal_service import MealSuggestionService
import datetime

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_mock_response():
    return TripResponse(
        trip=TripInfo(
            destination="Delhi",
            start_date=datetime.date(2026, 10, 1),
            end_date=datetime.date(2026, 10, 3),
            nights=2
        ),
        days=[
            DailyItinerary(day=1, date=datetime.date(2026, 10, 1), theme="Test", activities=[]),
            DailyItinerary(day=2, date=datetime.date(2026, 10, 2), theme="Test", activities=[])
        ],
        summary=TripSummary(estimated_cost=0, major_activities=0, estimated_travel_time=0),
        assumptions=[],
        validation=ValidationResult(passed=True),
        meal_suggestions=[]
    )

def test_restaurant_enrichment_valid(db):
    response = create_mock_response()
    enriched = MealSuggestionService.enrich(response, db, "Delhi")
    assert len(enriched.meal_suggestions) == 4 # 2 meals per day * 2 days
    
    # Check fields
    for meal in enriched.meal_suggestions:
        assert meal.meal.startswith("Lunch") or meal.meal.startswith("Dinner")
        assert meal.restaurant is not None
        assert meal.source is not None
        assert meal.scheduled
        assert meal.start_time and meal.end_time
        assert meal.day in (1, 2)

    second = MealSuggestionService.enrich(create_mock_response(), db, "Delhi")
    assert [
        (meal.day, meal.meal, meal.restaurant)
        for meal in enriched.meal_suggestions
    ] == [
        (meal.day, meal.meal, meal.restaurant)
        for meal in second.meal_suggestions
    ]


def test_restaurant_meal_window_is_skipped_when_it_overlaps_an_activity(db):
    response = create_mock_response()
    response.days[0].activities = [
        Activity(
            place_id="lunch-stop",
            name="Lunch-hour activity",
            start_time="12:00",
            end_time="14:00",
            duration_minutes=120,
            estimated_cost=0,
            travel_minutes=0,
            reason="Test activity",
        )
    ]

    enriched = MealSuggestionService.enrich(response, db, "Delhi")

    assert not any(
        meal.day == 1 and meal.meal.startswith("Lunch")
        for meal in enriched.meal_suggestions
    )
        
def test_restaurant_enrichment_unknown_city(db):
    response = create_mock_response()
    enriched = MealSuggestionService.enrich(response, db, "UnknownCityDoesNotExist")
    assert len(enriched.meal_suggestions) == 0
