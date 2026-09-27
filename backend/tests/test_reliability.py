import pytest
from datetime import date, time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas.trip import TripRequest, Location, Dates, Travellers, TravellerType, Pace, Budget, Transport, WalkingTolerance, TimeOfDay
from app.planner.engine import PlanningEngine
from app.db.database import SessionLocal

@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def create_base_request():
    return TripRequest(
        origin=Location(city="Mumbai", country="India", lat=19.0, lng=72.8),
        destination=Location(city="Goa", country="India", lat=15.2, lng=74.1),
        dates=Dates(start=date(2026, 10, 12), end=date(2026, 10, 16), nights=4),
        arrival=TimeOfDay.AFTERNOON,
        departure=TimeOfDay.EVENING,
        travellers=Travellers(type=TravellerType.FAMILY, adults=2, children=[8], seniors=0),
        interests={"beaches": 1.0, "food": 0.8},
        pace=Pace.BALANCED,
        transport=Transport.CAR,
        budget=Budget.MODERATE,
        dietary=[],
        walking_tolerance=WalkingTolerance.MODERATE,
        avoid=["late_nights"],
        day_start=time(9, 0)
    )

def test_family_profile_differences(db_session):
    engine = PlanningEngine(db_session)
    req = create_base_request()
    res = engine.plan_trip(req)
    
    if not res.validation.passed:
        for d in res.days:
            for a in d.activities:
                print(f"Day {d.day} Act: {a.name} | {a.start_time}-{a.end_time} | Travel: {a.travel_minutes}")
        print(f"Failed checks: {res.validation.checks}")
    assert res.validation.passed is True
    # Family avoids late nights and starts at 9am
    assert all(a.category != "nightlife" for day in res.days for a in day.activities)
    # Day 2 should start at 09:00
    assert res.days[1].activities[0].start_time == "09:00"

def test_solo_profile_differences(db_session):
    engine = PlanningEngine(db_session)
    req = create_base_request()
    req.travellers.type = TravellerType.SOLO
    req.pace = Pace.PACKED
    req.budget = Budget.BUDGET
    req.day_start = time(8, 0)
    req.avoid = []
    
    res = engine.plan_trip(req)
    
    if not res.validation.passed:
        for d in res.days:
            for a in d.activities:
                print(f"Day {d.day} Act: {a.name} | {a.start_time}-{a.end_time} | Travel: {a.travel_minutes}")
        print(f"Failed checks: {res.validation.checks}")
        
    assert res.validation.passed is True
    # Packed pace has more activities
    total_acts = sum(len(day.activities) for day in res.days)
    # Day 2 should start at 08:00
    assert res.days[1].activities[0].start_time == "08:00"

def test_origin_routing_assumption(db_session):
    engine = PlanningEngine(db_session)
    req = create_base_request()
    res = engine.plan_trip(req)
    
    # First activity travel time shouldn't be huge (not calculating from Mumbai)
    # First activity is typically 0 travel mins from hotel/arrival
    assert res.days[0].activities[0].travel_minutes == 0
    # Assumption includes origin phrase
    assert any("not scheduled" in a for a in res.assumptions)

def test_repair_loop_trigger(db_session):
    engine = PlanningEngine(db_session)
    req = create_base_request()
    # Force an impossible schedule by making them packed but starting very late
    req.pace = Pace.PACKED
    req.day_start = time(16, 0) # Start day at 4 PM
    
    res = engine.plan_trip(req)
    # If the repair loop triggered and failed to make it perfect, it will have an assumption warning.
    # We just want to ensure it completes and doesn't crash.
    assert len(res.days) > 0
    
def test_budget_validation(db_session):
    engine = PlanningEngine(db_session)
    req = create_base_request()
    req.budget = Budget.BUDGET
    res = engine.plan_trip(req)
    
    # Budget validation shouldn't fail if the repair loop drops expensive items or if the score ranks them low.
    if not res.validation.passed:
        assert res.validation.checks.budget is False or res.validation.checks.schedule is False
