import pytest
import datetime
from app.db.database import SessionLocal
from app.schemas.trip import (
    TripRequest, Location, Dates, Travellers, Pace, Budget,
    Transport, TimeOfDay, WalkingTolerance, RefineRequest
)
from app.schemas.response import TripResponse
from app.llm.refiner import LLMRefiner, RefinementCommand, MultiRefinementCommand
from app.api.trips import _apply_refinement_commands


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def base_request(city="Goa", nights=4) -> TripRequest:
    start = datetime.date(2026, 12, 1)
    end = start + datetime.timedelta(days=nights)
    return TripRequest(
        origin=Location(city="Mumbai", country="India", lat=19.0, lng=72.8),
        destination=Location(city=city, country="India", lat=15.29, lng=74.12),
        dates=Dates(start=start, end=end, nights=nights),
        arrival=TimeOfDay.MORNING,
        departure=TimeOfDay.EVENING,
        travellers=Travellers(type="family", adults=2, children=[10], seniors=0),
        interests={"culture": 0.7, "nature": 0.8, "food": 0.6},
        pace=Pace.BALANCED,
        transport=Transport.CAR,
        budget=Budget.MODERATE,
        dietary=[],
        walking_tolerance=WalkingTolerance.MODERATE,
        avoid=[],
        day_start="09:00"
    )


# ─── RefinementCommand Validation ──────────────────────────────────────────────

def test_refinement_command_valid_actions():
    cmd = RefinementCommand(action="change_pace", day=0, target_value="easy-going")
    assert cmd.action == "change_pace"


def test_refinement_command_invalid_action():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        RefinementCommand(action="invent_places", day=0)


def test_refinement_command_days_delta_bounds():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        RefinementCommand(action="increase_trip_days", day=0, days_delta=99)
    with pytest.raises(ValidationError):
        RefinementCommand(action="decrease_trip_days", day=0, days_delta=-99)


def test_refinement_command_valid_days_delta():
    cmd = RefinementCommand(action="increase_trip_days", day=0, days_delta=2)
    assert cmd.days_delta == 2


# ─── Duration Expansion ────────────────────────────────────────────────────────

def test_increase_trip_days():
    """Add 2 days: nights 4 → 6."""
    req = base_request(nights=4)
    cmd = RefinementCommand(action="increase_trip_days", day=0, days_delta=2)
    mutated, _ = _apply_refinement_commands(req, [cmd])
    assert mutated.dates.nights == 6
    # end date must be consistent
    expected_end = mutated.dates.start + datetime.timedelta(days=6)
    assert mutated.dates.end == expected_end


def test_increase_trip_days_clamped_at_7():
    """delta > 7 is clamped."""
    req = base_request(nights=3)
    cmd = RefinementCommand(action="increase_trip_days", day=0, days_delta=14)
    mutated, _ = _apply_refinement_commands(req, [cmd])
    # capped at +7
    assert mutated.dates.nights == 3 + 7


# ─── Duration Reduction ────────────────────────────────────────────────────────

def test_decrease_trip_days():
    """Remove 2 days: nights 4 → 2."""
    req = base_request(nights=4)
    cmd = RefinementCommand(action="decrease_trip_days", day=0, days_delta=-2)
    mutated, _ = _apply_refinement_commands(req, [cmd])
    assert mutated.dates.nights == 2
    expected_end = mutated.dates.start + datetime.timedelta(days=2)
    assert mutated.dates.end == expected_end


def test_decrease_trip_days_clamps_to_minimum():
    """Cannot go below 1 night."""
    req = base_request(nights=2)
    cmd = RefinementCommand(action="decrease_trip_days", day=0, days_delta=-5)
    mutated, _ = _apply_refinement_commands(req, [cmd])
    assert mutated.dates.nights >= 1


# ─── Multi-action Refinement ──────────────────────────────────────────────────

def test_multi_action_refinement_add_days_and_interest():
    """Add 2 days AND change interest to adventure."""
    req = base_request(nights=5)
    original_adventure = req.interests.get("adventure", 0.0)
    commands = [
        RefinementCommand(action="increase_trip_days", day=0, days_delta=2),
        RefinementCommand(action="change_interest_focus", day=0, target_value="adventure"),
    ]
    mutated, _ = _apply_refinement_commands(req, commands)
    assert mutated.dates.nights == 7
    # adventure interest was boosted
    assert mutated.interests.get("adventure", 0.0) > original_adventure


def test_multi_action_pace_and_density():
    req = base_request()
    commands = [
        RefinementCommand(action="change_pace", day=0, target_value="easy-going"),
        RefinementCommand(action="reduce_day_density", day=2),
    ]
    mutated, repair_context = _apply_refinement_commands(req, commands)
    assert mutated.pace.value == "easy-going"
    assert repair_context["reduce_density"] is True
    assert repair_context["target_day"] == 2


# ─── End-to-End Planner Refinement ────────────────────────────────────────────

def test_e2e_increase_days_goa(db):
    """Full planner E2E: Goa 2-day → 4-day after refinement."""
    from app.planner.engine import PlanningEngine
    req = base_request(city="Goa", nights=2)

    engine = PlanningEngine(db)
    original_response = engine.plan_trip(req)
    original_day_count = len(original_response.days)

    # Apply increase_trip_days
    cmd = RefinementCommand(action="increase_trip_days", day=0, days_delta=2)
    mutated_req, repair_context = _apply_refinement_commands(req, [cmd])

    refined_response = engine.plan_trip(mutated_req, refinement_context=repair_context)
    
    # The refined trip must have more days
    assert len(refined_response.days) > original_day_count
    assert refined_response.trip.nights == 4


def test_e2e_decrease_days_goa(db):
    """Full planner E2E: Goa 4-day → 2-day after refinement."""
    from app.planner.engine import PlanningEngine
    req = base_request(city="Goa", nights=4)

    engine = PlanningEngine(db)
    original_response = engine.plan_trip(req)

    # Apply decrease_trip_days
    cmd = RefinementCommand(action="decrease_trip_days", day=0, days_delta=-2)
    mutated_req, repair_context = _apply_refinement_commands(req, [cmd])

    refined_response = engine.plan_trip(mutated_req, refinement_context=repair_context)
    assert refined_response.trip.nights == 2


def test_e2e_change_pace(db):
    """Full planner E2E: changing pace produces a valid response."""
    from app.planner.engine import PlanningEngine
    req = base_request(city="Goa", nights=3)
    engine = PlanningEngine(db)

    cmd = RefinementCommand(action="change_pace", day=0, target_value="packed")
    mutated_req, repair_context = _apply_refinement_commands(req, [cmd])
    assert mutated_req.pace.value == "packed"
    response = engine.plan_trip(mutated_req, refinement_context=repair_context)
    assert response is not None


def test_e2e_avoid_category(db):
    """Avoiding a category should not add it back into the itinerary."""
    from app.planner.engine import PlanningEngine
    req = base_request(city="Goa", nights=3)

    cmd = RefinementCommand(action="avoid_category", day=0, target_value="Religious & Spiritual Pilgrimages")
    mutated_req, repair_context = _apply_refinement_commands(req, [cmd])
    assert "Religious & Spiritual Pilgrimages" in mutated_req.avoid
    
    engine = PlanningEngine(db)
    response = engine.plan_trip(mutated_req, refinement_context=repair_context)
    # No activity should be in an avoided category
    for day in response.days:
        for act in day.activities:
            assert act.category != "Religious & Spiritual Pilgrimages", \
                f"Found avoided category in activity: {act.name}"


# ─── Gemini Unavailable Fallback ──────────────────────────────────────────────

def test_gemini_unavailable_refiner_returns_none(monkeypatch):
    """When Gemini client is None, refiner returns None gracefully."""
    from app.llm import client as llm_client
    
    original_instance = llm_client.LLMClient._instance
    
    # Simulate no-API-key state
    null_client = llm_client.LLMClient.__new__(llm_client.LLMClient)
    null_client.client = None
    null_client.api_key = None
    llm_client.LLMClient._instance = null_client
    
    try:
        result = LLMRefiner.interpret("Add 2 more days.")
        assert result is None
    finally:
        llm_client.LLMClient._instance = original_instance


def test_deterministic_fallback_parses_add_days():
    """Deterministic regex fallback correctly identifies 'Add 2 more days'."""
    import re
    prompt_lower = "add 2 more days and make it adventurous"
    
    add_match = re.search(r'add\s+(\d+)\s+(more\s+)?day', prompt_lower)
    assert add_match is not None
    assert int(add_match.group(1)) == 2


def test_deterministic_fallback_parses_reduce_days():
    """Deterministic regex fallback correctly identifies 'remove 2 days'."""
    import re
    prompt_lower = "reduce the trip by 2 days"
    
    remove_match = re.search(r'(remove|reduce|cut).*?(\d+)\s+day', prompt_lower)
    assert remove_match is not None
    assert int(remove_match.group(2)) == 2


# ─── Dataset-Backed Activities Verification ───────────────────────────────────

def test_activities_come_from_database(db):
    """Verify place_ids in the refined response come from the canonical places table."""
    from app.planner.engine import PlanningEngine
    from app.models.place import Place
    
    req = base_request(city="Goa", nights=3)
    engine = PlanningEngine(db)
    response = engine.plan_trip(req)
    
    all_place_ids = {p.id for p in db.query(Place).all()}
    
    for day in response.days:
        for act in day.activities:
            assert act.place_id in all_place_ids, \
                f"Activity '{act.name}' has place_id '{act.place_id}' not found in database!"


# ─── Dates/Nights Consistency ─────────────────────────────────────────────────

def test_dates_nights_consistency_after_increase():
    """After increasing days, nights count and end date must be consistent."""
    req = base_request(nights=3)
    cmd = RefinementCommand(action="increase_trip_days", day=0, days_delta=3)
    mutated, _ = _apply_refinement_commands(req, [cmd])
    
    expected_end = mutated.dates.start + datetime.timedelta(days=mutated.dates.nights)
    assert mutated.dates.end == expected_end, \
        f"Inconsistent: nights={mutated.dates.nights} but end={mutated.dates.end}, expected={expected_end}"


def test_dates_nights_consistency_after_decrease():
    req = base_request(nights=5)
    cmd = RefinementCommand(action="decrease_trip_days", day=0, days_delta=-2)
    mutated, _ = _apply_refinement_commands(req, [cmd])

    expected_end = mutated.dates.start + datetime.timedelta(days=mutated.dates.nights)
    assert mutated.dates.end == expected_end
