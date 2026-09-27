from datetime import date, datetime, time

import pytest
from pydantic import ValidationError

from app.models.place import Place
from app.planner.constraints import HardConstraintEngine
from app.planner.scheduler import DailyScheduler
from app.planner.timing import PlannerTiming
from app.planner.tracer import PlannerTracer
from app.schemas.response import (
    DailyItinerary,
    TripInfo,
    TripResponse,
    TripSummary,
    ValidationResult,
)
from app.schemas.trip import (
    Budget,
    Dates,
    JourneyDetails,
    Location,
    Pace,
    TimeOfDay,
    Transport,
    TravellerType,
    Travellers,
    TripRequest,
    WalkingTolerance,
)
from app.validation.validator import Validator


def make_request(
    *,
    arrival: TimeOfDay = TimeOfDay.MORNING,
    departure: TimeOfDay = TimeOfDay.EVENING,
    journey: JourneyDetails | None = None,
) -> TripRequest:
    return TripRequest(
        origin=Location(city="Kurnool", country="India", lat=15.82887, lng=78.03602),
        destination=Location(city="Visakhapatnam", country="India", lat=17.68009, lng=83.20161),
        dates=Dates(start=date(2026, 9, 27), end=date(2026, 9, 29), nights=2),
        arrival=arrival,
        departure=departure,
        travellers=Travellers(type=TravellerType.SOLO, adults=1, children=[], seniors=0),
        interests={"nature": 1.0},
        pace=Pace.BALANCED,
        transport=Transport.WALKING_PUBLIC,
        budget=Budget.MODERATE,
        dietary=[],
        walking_tolerance=WalkingTolerance.MODERATE,
        avoid=[],
        day_start=time(9, 0),
        journey=journey,
    )


def make_place(place_id: str = "stop", *, latitude: float = 17.7825201) -> Place:
    return Place(
        id=place_id,
        name=place_id,
        destination="Visakhapatnam",
        latitude=latitude,
        longitude=83.3851154 if latitude > 17 else 79.7399875,
        duration=60,
        estimated_cost=0,
    )


def test_exact_journey_arrival_and_buffer_constrain_first_activity():
    request = make_request(
        journey=JourneyDetails(
            transport="train",
            status="confirmed",
            departure_at=datetime(2026, 9, 26, 20, 0),
            arrival_at=datetime(2026, 9, 27, 9, 0),
        )
    )
    scheduler = DailyScheduler(PlannerTracer(), PlannerTiming(arrival_buffer_minutes=60))

    itinerary = scheduler.schedule(request, {1: [make_place()], 2: [], 3: []})

    assert itinerary[0].activities[0].start_time == "10:00"
    assert itinerary[0].activities[0].end_time == "11:00"
    assert scheduler.skipped_activities == 0


def test_coarse_arrival_uses_conservative_representative_plus_buffer():
    request = make_request(arrival=TimeOfDay.MORNING)
    scheduler = DailyScheduler(PlannerTracer(), PlannerTiming(arrival_buffer_minutes=60))

    itinerary = scheduler.schedule(request, {1: [make_place()]})

    assert itinerary[0].activities[0].start_time == "13:00"


def test_unbooked_journey_without_exact_times_uses_coarse_arrival():
    request = make_request(journey=JourneyDetails(transport="train", status="not_booked"))
    scheduler = DailyScheduler(PlannerTracer(), PlannerTiming(arrival_buffer_minutes=60))

    itinerary = scheduler.schedule(request, {1: [make_place()]})

    assert itinerary[0].activities[0].start_time == "13:00"


def test_final_day_respects_departure_buffer_and_does_not_roll_activity():
    request = make_request(departure=TimeOfDay.MORNING)
    scheduler = DailyScheduler(PlannerTracer(), PlannerTiming(departure_buffer_minutes=60))

    itinerary = scheduler.schedule(request, {3: [make_place()]})

    assert itinerary[0].activities == []
    assert scheduler.skipped_activities == 1


def test_activity_that_would_cross_day_end_is_omitted():
    request = make_request()
    scheduler = DailyScheduler(PlannerTracer(), PlannerTiming(day_end=time(22, 0)))
    distant_place = make_place("distant", latitude=20.0)

    itinerary = scheduler.schedule(request, {2: [make_place(), distant_place]})

    assert [activity.name for activity in itinerary[0].activities] == ["stop"]
    assert scheduler.skipped_activities == 1
    assert all(activity.end_time > activity.start_time for activity in itinerary[0].activities)


def test_place_coordinates_far_from_destination_are_quarantined():
    request = make_request()
    engine = HardConstraintEngine(PlannerTracer(), PlannerTiming(max_place_distance_km=150))
    valid = make_place("near")
    misplaced = Place(
        id="fallback-coordinate",
        name="Misplaced record",
        destination="Visakhapatnam",
        latitude=15.9128998,
        longitude=79.7399875,
    )

    candidates = engine.filter_candidates(request, [valid, misplaced])

    assert [place.id for place in candidates] == ["near"]
    assert engine.excluded_location_count == 1


def test_journey_rejects_arrival_before_departure():
    with pytest.raises(ValidationError, match="Journey arrival must be after departure"):
        JourneyDetails(
            transport="train",
            status="confirmed",
            departure_at=datetime(2026, 9, 27, 9, 0),
            arrival_at=datetime(2026, 9, 26, 20, 0),
        )


def test_confirmed_journey_requires_exact_times():
    with pytest.raises(ValidationError, match="Confirmed or planned journeys require departure and arrival times"):
        JourneyDetails(transport="train", status="confirmed")


def test_validator_marks_overlapping_stops_as_invalid_schedule():
    request = make_request()
    response = TripResponse(
        trip=TripInfo(
            destination="Visakhapatnam",
            start_date=request.dates.start,
            end_date=request.dates.end,
            nights=request.dates.nights,
        ),
        days=[
            DailyItinerary(
                day=1,
                date=request.dates.start,
                theme="Test",
                activities=[
                    {
                        "place_id": "one",
                        "name": "One",
                        "start_time": "09:00",
                        "end_time": "10:00",
                        "duration_minutes": 60,
                        "estimated_cost": 0,
                        "travel_minutes": 0,
                        "reason": "Test",
                        "lat": 17.7825201,
                        "lng": 83.3851154,
                    },
                    {
                        "place_id": "two",
                        "name": "Two",
                        "start_time": "10:10",
                        "end_time": "11:10",
                        "duration_minutes": 60,
                        "estimated_cost": 0,
                        "travel_minutes": 10,
                        "reason": "Test",
                        "lat": 17.765657,
                        "lng": 83.3488338,
                    },
                ],
            )
        ],
        summary=TripSummary(estimated_cost=0, major_activities=2, estimated_travel_time=10),
        assumptions=[],
        validation=ValidationResult(passed=False),
    )

    validated = Validator.validate(response, request, [], PlannerTiming())

    assert validated.validation.checks is not None
    assert validated.validation.checks.schedule is False
    assert validated.validation.passed is False
