import pytest
from app.models.place import Place
from app.schemas.trip import TripRequest, Location, Dates, Travellers, Pace, Budget, Transport, TimeOfDay, WalkingTolerance, JourneyDetails
from app.planner.engine import PlanningEngine
from app.planner.tracer import PlannerTracer
from app.planner.constraints import HardConstraintEngine
from app.planner.scoring import ScoringEngine
from app.planner.scheduler import DailyScheduler
from app.planner.geography import GeographicPlanner
import datetime

@pytest.fixture
def base_request():
    return TripRequest(
        origin=Location(city="Delhi", country="India", lat=28.6, lng=77.2),
        destination=Location(city="TestCity", country="India", lat=0, lng=0),
        dates=Dates(start=datetime.date(2026, 1, 1), end=datetime.date(2026, 1, 3), nights=2),
        arrival=TimeOfDay.MORNING,
        departure=TimeOfDay.EVENING,
        travellers=Travellers(type="family", adults=2, children=[8], seniors=0),
        interests={"culture": 1.0},
        pace=Pace.BALANCED,
        transport=Transport.CAR,
        budget=Budget.MODERATE,
        dietary=[],
        walking_tolerance=WalkingTolerance.MODERATE,
        avoid=[],
        day_start=datetime.time(9, 0)
    )

def test_null_suitable_for(base_request):
    tracer = PlannerTracer()
    engine = HardConstraintEngine(tracer)
    
    place = Place(id="1", name="Test", suitable_for=None)
    # Should not crash and should not filter out
    valid = engine.filter_candidates(base_request, [place])
    assert len(valid) == 1

def test_null_interests(base_request):
    tracer = PlannerTracer()
    engine = ScoringEngine(tracer)
    
    place = Place(id="1", name="Test", interests=None, confidence=1.0)
    # Should not crash
    scored = engine.score_candidates(base_request, [place])
    assert len(scored) == 1
    assert scored[0][1] == 1.0  # Base confidence

def test_null_confidence(base_request):
    tracer = PlannerTracer()
    engine = ScoringEngine(tracer)
    
    place = Place(id="1", name="Test", interests=[], confidence=None)
    # Should not crash
    scored = engine.score_candidates(base_request, [place])
    assert len(scored) == 1
    assert scored[0][1] == 0.0

def test_null_area(base_request):
    tracer = PlannerTracer()
    engine = DailyScheduler(tracer)
    
    place1 = Place(id="1", name="Test 1", area=None)
    place2 = Place(id="2", name="Test 2", area=None)
    
    clusters = {1: [place1, place2]}
    # Should not crash building theme_str
    itineraries = engine.schedule(base_request, clusters)
    assert len(itineraries) == 1
    assert itineraries[0].theme == "Exploring "

def test_null_coordinates(base_request):
    tracer = PlannerTracer()
    engine = GeographicPlanner(tracer)
    
    place1 = Place(id="1", name="Test 1", latitude=None, longitude=None)
    place2 = Place(id="2", name="Test 2", latitude=10.0, longitude=20.0)
    
    # Should not crash on haversine distance. Without coords, they won't cluster together.
    clusters = engine.cluster_places_for_days(base_request, [(place1, 1.0), (place2, 0.5)], num_days=2)
    assert len(clusters) == 2
    assert len(clusters[1]) == 1

def test_null_opening_hours(base_request):
    tracer = PlannerTracer()
    engine = DailyScheduler(tracer)
    
    place = Place(id="1", name="Test 1", opening_hours=None, duration=60)
    clusters = {1: [place]}
    
    exact_arrival_request = base_request.model_copy(update={
        "journey": JourneyDetails(
            transport="train",
            status="confirmed",
            departure_at=datetime.datetime(2025, 12, 31, 20, 0),
            arrival_at=datetime.datetime(2026, 1, 1, 8, 0),
        )
    })
    itineraries = engine.schedule(exact_arrival_request, clusters)
    assert len(itineraries) == 1
    assert len(itineraries[0].activities) == 1
    # Activity should start exactly at 9:00 AM since it's not restricted by opening hours
    assert itineraries[0].activities[0].start_time == "09:00"
