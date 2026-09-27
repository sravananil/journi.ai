import pytest
from app.db.database import SessionLocal
from app.schemas.trip import TripRequest, Location, Dates, Travellers, Pace, Budget, Transport, TimeOfDay, WalkingTolerance
from app.planner.retrieval import CandidateRetrieval
from app.planner.tracer import PlannerTracer
import datetime

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_request(city_name):
    return TripRequest(
        origin=Location(city="Mumbai", country="India", lat=19.0, lng=72.8),
        destination=Location(city=city_name, country="India", lat=12.9, lng=77.5),
        dates=Dates(start=datetime.date(2026, 10, 1), end=datetime.date(2026, 10, 3), nights=2),
        arrival=TimeOfDay.MORNING,
        departure=TimeOfDay.EVENING,
        travellers=Travellers(type="family", adults=2, children=[10], seniors=0),
        interests={},
        pace=Pace.BALANCED,
        transport=Transport.CAR,
        budget=Budget.MODERATE,
        dietary=[],
        walking_tolerance=WalkingTolerance.MODERATE,
        avoid=[],
        day_start="09:00"
    )

def test_city_resolution_alias(db):
    tracer = PlannerTracer()
    retrieval = CandidateRetrieval(db, tracer)
    
    # Bengaluru should resolve to Bengaluru (canonical) and fetch Bangalore places
    req = create_request("Bengaluru")
    places = retrieval.retrieve(req)
    traces = [t for t in tracer.traces if t['action'] == "City Normalization"]
    assert len(traces) == 1
    assert "Resolved 'Bengaluru' to canonical city 'Bengaluru'" in traces[0]['details']
    assert len(places) > 0

def test_city_resolution_exact(db):
    tracer = PlannerTracer()
    retrieval = CandidateRetrieval(db, tracer)
    
    # Bangalore should resolve to Bengaluru (since Bengaluru is canonical in geolocations, and Bangalore is an alias)
    req = create_request("Bangalore")
    places = retrieval.retrieve(req)
    traces = [t for t in tracer.traces if t['action'] == "City Normalization"]
    assert len(traces) == 1
    assert "Resolved 'Bangalore' to canonical city 'Bengaluru'" in traces[0]['details']
    assert len(places) > 0

def test_city_resolution_unknown(db):
    tracer = PlannerTracer()
    retrieval = CandidateRetrieval(db, tracer)
    
    # Unknown city should return 0 places
    req = create_request("UnknownCity")
    places = retrieval.retrieve(req)
    assert len(places) == 0
    traces = [t for t in tracer.traces if t['action'] == "City Normalization"]
    assert len(traces) == 1
    assert "Could not resolve 'UnknownCity'" in traces[0]['details']
