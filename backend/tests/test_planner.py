import pytest
from app.schemas.trip import TripRequest, Location, Dates, Travellers, Pace, Budget, Transport, TimeOfDay, WalkingTolerance
from app.planner.engine import PlanningEngine
from app.db.database import SessionLocal
import datetime

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_family_profile(db_session):
    request = TripRequest(
        origin=Location(city="Bengaluru", country="India", lat=12.9, lng=77.5),
        destination=Location(city="Goa", country="India", lat=15.2, lng=74.1),
        dates=Dates(start=datetime.date(2026, 10, 12), end=datetime.date(2026, 10, 16), nights=4),
        arrival=TimeOfDay.AFTERNOON,
        departure=TimeOfDay.EVENING,
        travellers=Travellers(type="family", adults=2, children=[8], seniors=0),
        interests={"beaches": 1.0, "food": 0.8, "culture": 0.5},
        pace=Pace.BALANCED,
        transport=Transport.CAR,
        budget=Budget.MODERATE,
        dietary=["vegetarian"],
        walking_tolerance=WalkingTolerance.MODERATE,
        avoid=[],
        day_start=datetime.time(9, 0)
    )
    
    engine = PlanningEngine(db_session)
    response = engine.plan_trip(request)
    
    # Assert itinerary is generated
    assert response.validation.passed == True
    assert len(response.days) == 4 or len(response.days) == 5 # 4 nights trip
    
    # Check that family-unsuitable places (like Tito's Lane) are likely not included 
    # (since we seeded Tito's with suitable_for: solo, friends, couple)
    titos_included = False
    for day in response.days:
        for act in day.activities:
            if act.place_id == "p_014": # Tito's lane
                titos_included = True
                
    assert not titos_included, "Family profile should not include Tito's Lane"
